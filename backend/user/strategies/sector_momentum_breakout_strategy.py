import csv
import os
import time
import threading
import logging
import random
import requests
import json
import pandas as pd
import pandas_ta as pd_ta
import numpy as np
import pytz
from datetime import datetime, timedelta, date
from urllib.parse import quote
from django.utils import timezone

logger = logging.getLogger("strategy_log")

IST = pytz.timezone("Asia/Kolkata")

# ===============================
# FIXED SCHEMAS
# ===============================
SECTOR_COLS = ["scan_time", "sector", "sector_change", "url", "status"]
STOCK_COLS  = [
    "scan_time", "Sector", "Sector Change %",
    "Symbol", "Price", "Stock Change %", "OI Change", "Volume", "status",
]


class SectorMomentumBreakoutStrategy:

    STRATEGY_NAME = "Sector Momentum Breakout"

    # ------------------------------------------------------------------
    # DEFAULT PHASE TIMES  — single source of truth
    # ------------------------------------------------------------------
    PHASE1_START_TIME = "09:20"
    PHASE1_END_TIME   = "09:30"
    PHASE2_START_TIME = "09:30"
    PHASE2_END_TIME   = "15:30"

    PHASE2_SCAN_INTERVAL_MINUTES = 15

    def __init__(self, angel, settings, data, user_profile, stop_event=None, **kwargs):
        logger.info("[INIT] SectorMomentumBreakoutStrategy initializing")
        self.angel        = angel
        self.settings     = settings
        self.user_profile = user_profile

        self.watchlist      = []
        self.watchlist_csv  = "watchlist.csv"
        self.watchlist2     = []
        self.watchlist_csv2 = "watchlist2.csv"

        self.trades_today       = 0
        self.max_trades_per_day = int(settings.get("trades_per_day", 5))
        logger.info(f"[INIT] Max trades per day: {self.max_trades_per_day}")

        self._initialize_csv_headers()
        self._initialize_csv_headers_for_watchlist2()

        self.stop_event = stop_event or threading.Event()

        self.websocket_manager = kwargs.get("websocket_manager", None)
        self.order_manager     = kwargs.get("order_manager", None)

        # ---- Resolve effective phase times ----
        self._phase1_start = self._parse_time(
            settings.get("phase1_start_time") or self.PHASE1_START_TIME
        )
        self._phase1_end = self._parse_time(
            settings.get("phase1_end_time") or self.PHASE1_END_TIME
        )
        self._phase2_start = self._parse_time(
            settings.get("phase2_start_time") or self.PHASE2_START_TIME
        )
        self._phase2_end = self._parse_time(
            settings.get("phase2_end_time") or self.PHASE2_END_TIME
        )

        logger.info(
            f"[INIT] Phase times — "
            f"P1: {self._phase1_start.strftime('%H:%M')}–{self._phase1_end.strftime('%H:%M')} | "
            f"P2: {self._phase2_start.strftime('%H:%M')}–{self._phase2_end.strftime('%H:%M')}"
        )

        # WS started flags (per-day guards)
        self._ws_phase1_started = False
        self._ws_phase2_started = False

        t = threading.Thread(
            target=self.scheduler_loop,
            args=(angel, settings, user_profile),
            daemon=True,
        )
        t.start()
        logger.info("[BOT] Scheduler thread started")

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_time(time_str):
        return datetime.strptime(time_str, "%H:%M").time()

    @staticmethod
    def _now_ist():
        return datetime.now(IST)

    def _is_stop_requested(self):
        return self.stop_event is not None and self.stop_event.is_set()

    def _get_ws_credentials(self):
        """
        Extract WebSocket credentials from the angel session object.
        Returns dict with jwt_token, feed_token, client_code, api_key.
        Falls back to django settings if angel object doesn't have them.
        """
        creds = {
            "jwt_token":   None,
            "feed_token":  None,
            "client_code": None,
            "api_key":     None,
        }
        # Try angel object attributes first (most reliable)
        try:
            if hasattr(self.angel, 'access_token') and self.angel.access_token:
                creds["jwt_token"] = self.angel.access_token
            if hasattr(self.angel, 'feed_token') and self.angel.feed_token:
                creds["feed_token"] = self.angel.feed_token
            if hasattr(self.angel, 'clientCode') and self.angel.clientCode:
                creds["client_code"] = self.angel.clientCode
            if hasattr(self.angel, 'api_key') and self.angel.api_key:
                creds["api_key"] = self.angel.api_key
        except Exception:
            logger.exception("[CREDS] Error extracting credentials from angel object")

        # Fallback to django settings for any missing values
        missing = [k for k, v in creds.items() if not v]
        if missing:
            try:
                from django.conf import settings as django_settings
                mapping = {
                    "jwt_token":   "ANGEL_JWT_TOKEN",
                    "feed_token":  "ANGEL_FEED_TOKEN",
                    "client_code": "ANGEL_CLIENT_CODE",
                    "api_key":     "ANGEL_API_KEY",
                }
                for key in missing:
                    val = getattr(django_settings, mapping[key], None)
                    if val:
                        creds[key] = val
                        logger.info(f"[CREDS] {key} resolved from django settings")
            except Exception:
                logger.exception("[CREDS] Error reading django settings for WS creds")

        logger.info(f"[CREDS] jwt_token={'set' if creds['jwt_token'] else 'MISSING'} | "
                    f"feed_token={'set' if creds['feed_token'] else 'MISSING'} | "
                    f"client_code={creds['client_code']} | "
                    f"api_key={'set' if creds['api_key'] else 'MISSING'}")
        return creds

    # ===============================
    # CSV INIT
    # ===============================

    def _initialize_csv_headers(self):
        if not os.path.exists(self.watchlist_csv):
            headers = [
                "timestamp", "option_symbol", "stock_symbol", "option_type",
                "previous_day_high","previous_day_date",
                "five_min_high", "five_min_low", "five_min_close",
                "five_min_volume", "avg_volume_20", "entry_signal",
                "status", "stoploss",
            ]
            try:
                with open(self.watchlist_csv, "w", newline="") as f:
                    csv.DictWriter(f, fieldnames=headers).writeheader()
                logger.info(f"[INIT] Created watchlist CSV: {self.watchlist_csv}")
            except Exception:
                logger.exception(f"[INIT] Failed to create {self.watchlist_csv}")

    def _initialize_csv_headers_for_watchlist2(self):
        if not os.path.exists(self.watchlist_csv2):
            headers = [
                "timestamp", "option_symbol", "stock_symbol", "option_type",
                "five_min_high", "five_min_low", "five_min_close",
                "five_min_volume", "avg_volume_20", "vwap", "wma_9",
                "entry_signal", "status", "limit_price", "stoploss",
            ]
            try:
                with open(self.watchlist_csv2, "w", newline="") as f:
                    csv.DictWriter(f, fieldnames=headers).writeheader()
                logger.info(f"[INIT] Created watchlist2 CSV: {self.watchlist_csv2}")
            except Exception:
                logger.exception(f"[INIT] Failed to create {self.watchlist_csv2}")

    # ===============================
    # CLEAN OLD CSV DATA
    # ===============================

    def clean_old_csv_data(self):
        today = self._now_ist().date()
        for csv_path in ("sectors_filtered.csv", "sectorwise_stocks_filtered.csv"):
            try:
                if not os.path.exists(csv_path):
                    continue
                df = pd.read_csv(csv_path)
                if "scan_time" in df.columns:
                    df["scan_time"] = pd.to_datetime(df["scan_time"], errors="coerce")
                    df = df[df["scan_time"].dt.date == today]
                df.to_csv(csv_path, index=False)
                logger.info(f"[CLEAN] {csv_path} cleaned, {len(df)} rows kept from today")
            except Exception:
                logger.exception(f"[CLEAN] Error cleaning {csv_path}")

    # ===============================
    # EXPIRY HELPERS
    # ===============================

    def get_last_day_of_month_fut(self, date_val):
        next_month = date_val.replace(day=28) + timedelta(days=4)
        return next_month - timedelta(days=next_month.day)

    def find_last_expiry_of_month(self, expiry_dates, month_date):
        last_expiry = None
        for expiry_date in expiry_dates:
            if expiry_date.month == month_date.month and expiry_date.year == month_date.year:
                if last_expiry is None or expiry_date > last_expiry:
                    last_expiry = expiry_date
        return last_expiry

    def getExpiryDateFut(self, index, setting, exchange, symboldf):
        try:
            df = symboldf.copy()
            df = df[
                (df.name == index) &
                (df.instrumenttype == "OPTSTK") &
                (df.exch_seg == exchange)
            ].copy()

            df["expiry"] = pd.to_datetime(df["expiry"], format="%d%b%Y", errors="coerce")
            today = pd.to_datetime(timezone.localtime(timezone.now()).date())
            df = df[df.expiry >= today].reset_index(drop=True)

            expiry_dates = pd.to_datetime(
                pd.Series(df["expiry"].dropna().unique().tolist()).sort_values()
            ).reset_index(drop=True)

            current_date           = timezone.localtime(timezone.now()).date()
            last_day_current_month = self.get_last_day_of_month_fut(current_date)
            last_expiry_this_month = self.find_last_expiry_of_month(expiry_dates, last_day_current_month)

            if last_expiry_this_month is None:
                next_month = current_date.replace(day=28) + timedelta(days=4)
                nm_expiry  = self.find_last_expiry_of_month(expiry_dates, next_month)
                if nm_expiry:
                    return nm_expiry

            if setting.get("expiry_date") == "next_month":
                next_month = current_date.replace(day=28) + timedelta(days=4)
                nm_expiry  = self.find_last_expiry_of_month(expiry_dates, next_month)
                if nm_expiry:
                    return nm_expiry

            if setting.get("expiry_date") == "far_month":
                far_month = current_date.replace(day=28) + timedelta(days=35)
                fm_expiry = self.find_last_expiry_of_month(expiry_dates, far_month)
                if fm_expiry:
                    return fm_expiry

            if last_expiry_this_month and last_expiry_this_month >= today:
                return last_expiry_this_month

            return None
        except Exception:
            logger.exception(f"[EXPIRY] Error getting expiry for {index}")
            return None

    def get_monthly_expiry_fut(self, index, setting, exchange, symboldf):
        expiry_date = self.getExpiryDateFut(index, setting, exchange, symboldf)
        if expiry_date is None:
            logger.error(f"[EXPIRY] Could not find expiry date for {index}")
            fallback_date = self.get_last_day_of_month_fut(datetime.now().date()) + timedelta(days=7)
            fallback_str  = fallback_date.strftime("%d%b%y").upper()
            logger.warning(f"[EXPIRY] Using fallback expiry: {fallback_str}")
            return fallback_str
        return expiry_date.strftime("%d%b%y").upper()

    def get_inst_fut(self, index, setting, exchange, symboldf):
        expiry_code = self.get_monthly_expiry_fut(index, setting, exchange, symboldf)
        if not expiry_code:
            logger.error(f"[INST] Failed to get expiry code for {index}")
            return None
        return expiry_code[:-2] + expiry_code[-2:]

    # ===============================
    # STRIKE PRICE HELPERS
    # ===============================

    def get_correct_strike_price(self, ltp, ce_pe, strike_prices, strike_multiplier):
        try:
            higher_strikes = [s for s in strike_prices if s >= ltp]
            lower_strikes  = [s for s in strike_prices if s < ltp]

            if ce_pe == "CE":
                strike_price = (
                    higher_strikes[strike_multiplier - 1]
                    if len(higher_strikes) >= strike_multiplier
                    else higher_strikes[-1]
                )
            else:
                strike_price = (
                    lower_strikes[-strike_multiplier]
                    if len(lower_strikes) >= strike_multiplier
                    else lower_strikes[0]
                )
            return strike_price
        except Exception:
            logger.exception(f"[STRIKE] Error computing strike price ltp={ltp} ce_pe={ce_pe}")
            return None

    def angel_fetch_symbol(self, obj, symbol, index, ce_pe, setting, instrument_list, symboldf):
        """
        Fetch option symbol.
        If the generated symbol token is None, tries ATM strike and ±1 strikes
        before giving up.
        Returns None on complete failure.
        """
        try:
            expiry = self.get_inst_fut(index, setting, "NFO", symboldf)
            if not expiry:
                logger.error(f"[STRIKE] Could not get expiry for {symbol}")
                return None
            expiry = expiry.upper()

            # Fetch LTP with retries
            ltp = None
            for attempt in range(3):
                try:
                    ltp_resp = self.order_manager.get_ltp(obj, instrument_list, symbol, "NSE")
                    if ltp_resp and ltp_resp.get("status") and "data" in ltp_resp:
                        ltp = ltp_resp["data"]["ltp"]
                        logger.info(f"[STRIKE] LTP fetched on attempt {attempt + 1}: {ltp}")
                        break
                except Exception:
                    logger.exception(f"[STRIKE] LTP fetch error on attempt {attempt + 1} for {symbol}")
                time.sleep(1)

            if ltp is None:
                logger.error(f"[STRIKE] Could not fetch LTP for {symbol} after 3 attempts")
                return None

            # Get strike prices from symboldf
            filtered = symboldf[
                (symboldf["name"] == index) &
                (symboldf["instrumenttype"] == "OPTSTK")
            ]
            if filtered.empty:
                logger.error(f"[STRIKE] No option data found for {index}")
                return None

            strike_prices = sorted(filtered["strike"].unique())
            strike_prices = [
                round(float(p) / 100, 1) if float(p) % 100 != 0 else int(float(p) / 100)
                for p in strike_prices
            ]

            strike_multiplier = int(setting.get("strike_price", 1))
            correct_strike = self.get_correct_strike_price(ltp, ce_pe, strike_prices, strike_multiplier)
            if correct_strike is None:
                logger.error(f"[STRIKE] Could not determine correct strike for {symbol}")
                return None

            # Try primary strike first, then fallback to adjacent strikes if token not found
            candidates = [correct_strike]
            idx = strike_prices.index(correct_strike) if correct_strike in strike_prices else -1
            if idx >= 0:
                if idx + 1 < len(strike_prices):
                    candidates.append(strike_prices[idx + 1])
                if idx - 1 >= 0:
                    candidates.append(strike_prices[idx - 1])

            for strike in candidates:
                option_symbol = f"{index}{expiry}{strike}{ce_pe}"
                # Quick token validation
                test_token = self.order_manager.token_lookup(option_symbol, instrument_list, exchange="NFO")
                if test_token:
                    logger.info(f"[STRIKE] Generated option symbol: {option_symbol} (token={test_token})")
                    return option_symbol
                else:
                    logger.warning(f"[STRIKE] No token for {option_symbol}, trying next strike")

            logger.error(f"[STRIKE] No valid option symbol found for {symbol} near strike {correct_strike}")
            return None

        except Exception:
            logger.exception(f"[STRIKE] Error in angel_fetch_symbol for {symbol}")
            return None

    # ===============================
    # OHLC DATA FETCH  (with exponential backoff + jitter)
    # FIX: todate now uses self._now_ist() to get actual current IST time,
    #      preventing the "No today candles" issue caused by UTC offset.
    # ===============================

    def get_todays_ohlc_data_(self, obj, opt_symbol, interval, instrument_list,
                               exchange="NFO", retries=3):
        """
        Fetch OHLC candle data for opt_symbol.
        Uses exponential backoff with jitter to handle rate-limit errors.
        Returns a DataFrame or None on complete failure.

        KEY FIX: todate uses self._now_ist() (pytz IST) not timezone.now()
        which could produce UTC-formatted strings sent to the Angel API,
        causing all of today's candles to appear missing.
        """
        if interval in ("5", 5):
            interval = "FIVE_MINUTE"

        # Use pytz IST datetime to guarantee correct local time strings
        now_ist   = self._now_ist()
        today_str = now_ist.strftime("%Y-%m-%d %H:%M")

        thirty_five_days_ago = (
            now_ist - timedelta(days=35)
        ).replace(
            hour=9,
            minute=15,
            second=0,
            microsecond=0
        )

        fromdate = thirty_five_days_ago.strftime("%Y-%m-%d %H:%M")

        token = None
        try:
            token = self.order_manager.token_lookup(opt_symbol, instrument_list, exchange=exchange)
            logger.info(f"[TOKEN CHECK] {opt_symbol} -> token={token}")
        except Exception:
            logger.exception(f"[OHLC] Token lookup failed for {opt_symbol}")
            return None

        if not token:
            logger.warning(f"[OHLC] No token found for {opt_symbol}")
            return None

        params = {
            "exchange":    exchange,
            "symboltoken": token,
            "interval":    interval,
            "fromdate": fromdate,
            "todate":      today_str,
        }

        logger.info(
            f"[OHLC PARAMS] "
            f"symbol={opt_symbol} "
            f"token={token} "
            f"from={fromdate} "
            f"to={today_str} "
            f"interval={interval}"
        )

        for attempt in range(retries):
            # Exponential backoff: 2s, 4s, 8s — plus random jitter 0–1s
            base_delay = (2 ** (attempt + 1)) + random.uniform(0, 1)
            if attempt > 0:
                logger.info(
                    f"[OHLC] Waiting {base_delay:.1f}s before attempt "
                    f"{attempt + 1}/{retries} for {opt_symbol}"
                )
                time.sleep(base_delay)
            else:
                # Small initial delay to avoid immediate rate-limit
                time.sleep(0.5 + random.uniform(0, 0.5))

            logger.info(f"[OHLC] Attempt {attempt + 1}/{retries} for {opt_symbol}")
            try:
                hist = obj.getCandleData(params)

                if hist is None:
                    logger.warning(f"[OHLC] None response on attempt {attempt + 1} for {opt_symbol}")
                    continue

                if isinstance(hist, dict) and hist.get("data"):
                    df = pd.DataFrame(
                        hist["data"],
                        columns=["Timestamp", "open", "high", "low", "close", "volume"],
                    )
                    if not df.empty:
                        logger.info(f"[OHLC] {len(df)} candles fetched for {opt_symbol}")
                        logger.info(f"[OHLC RAW FIRST] {opt_symbol} {df.iloc[0].to_dict()}")
                        logger.info(f"[OHLC RAW LAST] {opt_symbol} {df.iloc[-1].to_dict()}")
                        logger.info(f"[OHLC RAW LAST5] {opt_symbol} {df.tail(5).to_dict('records')}")
                        return df.reset_index(drop=True)
                    logger.warning(
                        f"[OHLC] Empty DataFrame on attempt {attempt + 1} for {opt_symbol}"
                    )
                else:
                    logger.warning(
                        f"[OHLC] No 'data' key on attempt {attempt + 1} for {opt_symbol}: {hist}"
                    )

            except Exception as e:
                err_str = str(e)
                if "exceeding access rate" in err_str.lower():
                    logger.warning(
                        f"[OHLC] Rate limit on attempt {attempt + 1} for {opt_symbol} — backing off"
                    )
                elif "couldn't parse" in err_str.lower() or "b''" in err_str:
                    logger.warning(
                        f"[OHLC] Empty/unparseable response on attempt {attempt + 1} for {opt_symbol}"
                    )
                else:
                    logger.exception(
                        f"[OHLC] Unexpected error on attempt {attempt + 1} for {opt_symbol}"
                    )

        logger.error(f"[OHLC] All {retries} attempts failed for {opt_symbol}")
        return None

    # ===============================
    # CSV OPERATIONS
    # ===============================

    def mark_stock_inactive_in_sector_csv(self, symbol):
        try:
            csv_path = "sectorwise_stocks_filtered.csv"
            if not os.path.exists(csv_path):
                return
            df   = pd.read_csv(csv_path)
            mask = (df["Symbol"] == symbol) & (df["status"] == "ACTIVE")
            if mask.any():
                df.loc[mask, "status"] = "INACTIVE"
                df.to_csv(csv_path, index=False)
                logger.info(f"[SECTOR CSV] Marked {symbol} as INACTIVE")
        except Exception:
            logger.exception(f"[SECTOR CSV] Failed to mark inactive for {symbol}")

    def update_csv_with_status(self, csv_path, new_df, cols):
        if new_df.empty:
            logger.warning(f"[CSV] No data to write for {csv_path}")
            return
        try:
            for col in cols:
                if col not in new_df.columns:
                    new_df[col] = ""
            new_df = new_df[cols]

            if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                try:
                    old_df = pd.read_csv(csv_path)
                    if "status" in old_df.columns:
                        old_df["status"] = "INACTIVE"
                    final_df = pd.concat([old_df, new_df], ignore_index=True)
                    final_df = final_df.drop_duplicates(
                        subset=[c for c in cols if c != "status"], keep="last"
                    )
                    final_df.to_csv(csv_path, index=False)
                except (pd.errors.EmptyDataError, pd.errors.ParserError):
                    new_df.to_csv(csv_path, index=False)
            else:
                new_df.to_csv(csv_path, index=False)

            logger.info(f"[CSV] Updated {csv_path}")
        except Exception:
            logger.exception(f"[CSV] Failed to update {csv_path}")

    def save_watchlist_to_csv(self):
        if not self.watchlist:
            return
        today   = datetime.now().date()
        headers = [
            "timestamp", "option_symbol", "stock_symbol", "option_type",
            "previous_day_high","previous_day_date",
            "five_min_high", "five_min_low", "five_min_close",
            "five_min_volume", "avg_volume_20", "entry_signal", "status", "stoploss",
        ]
        try:
            todays = [e for e in self.watchlist if e["timestamp"].date() == today]
            if not todays:
                self.watchlist.clear()
                return

            df = (
                pd.read_csv(self.watchlist_csv)
                if os.path.exists(self.watchlist_csv)
                else pd.DataFrame(columns=headers)
            )
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df = df[df["timestamp"].dt.date == today]

            new_df = pd.DataFrame(todays)
            new_df["timestamp"] = new_df["timestamp"].apply(
                lambda ts: ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else ts
            )
            pd.concat([df, new_df], ignore_index=True).to_csv(self.watchlist_csv, index=False)
            logger.info(f"[SAVE] {len(new_df)} entries saved to {self.watchlist_csv}")
        except Exception:
            logger.exception("[SAVE] Failed to save watchlist CSV")
        finally:
            self.watchlist.clear()

    def save_watchlist2_to_csv(self):
        if not self.watchlist2:
            return
        today   = datetime.now().date()
        headers = [
            "timestamp", "option_symbol", "stock_symbol", "option_type",
            "five_min_high", "five_min_low", "five_min_close",
            "five_min_volume", "avg_volume_20", "vwap", "wma_9",
            "entry_signal", "status", "limit_price", "stoploss",
        ]
        try:
            todays = [e for e in self.watchlist2 if e["timestamp"].date() == today]
            if not todays:
                self.watchlist2.clear()
                return

            df = (
                pd.read_csv(self.watchlist_csv2)
                if os.path.exists(self.watchlist_csv2)
                else pd.DataFrame(columns=headers)
            )
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df = df[df["timestamp"].dt.date == today]

            new_df = pd.DataFrame(todays)
            new_df["timestamp"] = new_df["timestamp"].apply(
                lambda ts: ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else ts
            )
            pd.concat([df, new_df], ignore_index=True).to_csv(self.watchlist_csv2, index=False)
            logger.info(f"[SAVE] {len(new_df)} entries saved to {self.watchlist_csv2}")
        except Exception:
            logger.exception("[SAVE] Failed to save watchlist2 CSV")
        finally:
            self.watchlist2.clear()

    def deactivate_watchlist1(self):
        logger.info("[RESET W1] Deactivating all Phase 1 watchlist entries")
        try:
            if os.path.exists(self.watchlist_csv):
                df = pd.read_csv(self.watchlist_csv)
                if not df.empty:
                    df["status"] = "INACTIVE"
                    df.to_csv(self.watchlist_csv, index=False)
                    logger.info(f"[RESET W1] {len(df)} entries marked INACTIVE")
        except Exception:
            logger.exception("[RESET W1] Error deactivating watchlist1")
        self.watchlist.clear()

    def deactivate_watchlist2(self):
        logger.info("[RESET W2] Deactivating all Phase 2 watchlist entries")
        try:
            if os.path.exists(self.watchlist_csv2):
                df = pd.read_csv(self.watchlist_csv2)
                if not df.empty:
                    df["status"] = "INACTIVE"
                    df.to_csv(self.watchlist_csv2, index=False)
                    logger.info(f"[RESET W2] {len(df)} entries marked INACTIVE")
        except Exception:
            logger.exception("[RESET W2] Error deactivating watchlist2")
        self.watchlist2.clear()

        if self.websocket_manager:
            try:
                self.websocket_manager.unsubscribe_all()
            except Exception:
                logger.exception("[RESET W2] Error unsubscribing WS tokens")

    # ===============================
    # SECTOR SCAN  (NSE API)
    # ===============================

    def run_scrap_sector(self, settings):
        try:
            SECTOR_SCAN_LIMIT = int(settings.get("sectors_scan", 3))
            STOCK_SCAN_LIMIT  = int(settings.get("stocks_scan", 3))

            logger.info(f"[SECTOR_SCAN] Sector limit: {SECTOR_SCAN_LIMIT}, Stock limit: {STOCK_SCAN_LIMIT}")

            scan_time = self._now_ist().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[SECTOR_SCAN] Started at {scan_time}")

            fno_symbols = {
                "GMRAIRPORT", "KFINTECH", "TORNTPHARM", "POWERGRID", "ADANIGREEN", "COALINDIA",
                "IREDA", "DIXON", "AUROPHARMA", "HDFCBANK", "ABCAPITAL", "KALYANKJIL", "PFC",
                "LTF", "KPITTECH", "JSWENERGY", "ASTRAL", "JINDALSTEL", "CUMMINSIND", "NHPC",
                "DLF", "CANBK", "ADANIENT", "SBICARD", "VBL", "OFSS", "BAJAJHLDNG", "BANKINDIA",
                "MAXHEALTH", "GLENMARK", "AXISBANK", "INDUSTOWER", "SIEMENS", "IDEA", "ABB",
                "NYKAA", "NTPC", "NBCC", "LODHA", "GAIL", "ALKEM", "KAYNES", "BHEL", "ONGC",
                "POWERINDIA", "TATAPOWER", "ADANIPORTS", "CAMS", "CIPLA", "SWIGGY", "MARICO",
                "HAVELLS", "CGPOWER", "BRITANNIA", "SHRIRAMFIN", "BANKBARODA", "GODREJCP", "OIL",
                "BANDHANBNK", "IDFCFIRSTB", "MANKIND", "CDSL", "ASIANPAINT", "BAJAJFINSV", "MFSL",
                "ADANIENSOL", "ITC", "LUPIN", "PNBHOUSING", "POLYCAB", "OBEROIRLTY", "SUPREMEIND",
                "GODREJPROP", "UPL", "PHOENIXLTD", "RECLTD", "PGEL", "PIDILITIND", "SUZLON",
                "AUBANK", "HDFCAMC", "TATASTEEL", "AMBUJACEM", "HDFCLIFE", "ETERNAL", "JSWSTEEL",
                "NESTLEIND", "EXIDEIND", "SBILIFE", "BHARTIARTL", "GRASIM", "SHREECEM", "CONCOR",
                "PREMIERENE", "BIOCON", "INDIGO", "MOTHERSON", "PERSISTENT", "RVNL", "SYNGENE",
                "INDIANB", "TATACONSUM", "DIVISLAB", "PNB", "DABUR", "CROMPTON", "HINDUNILVR",
                "BDL", "WAAREEENER", "ZYDUSLIFE", "VEDL", "SAMMAANCAP", "TIINDIA", "PETRONET",
                "PRESTIGE", "APOLLOHOSP", "INDUSINDBK", "SRF", "RELIANCE", "AMBER", "KOTAKBANK",
                "IRFC", "COFORGE", "SOLARINDS", "DRREDDY", "YESBANK", "NMDC", "BEL", "LAURUSLABS",
                "LT", "HAL", "JUBLFOOD", "LTIM", "SUNPHARMA", "IEX", "LICHSGFIN", "TORNTPOWER",
                "VOLTAS", "UNIONBANK", "TCS", "360ONE", "BHARATFORG", "FEDERALBNK", "ICICIBANK",
                "HCLTECH", "UNITDSPR", "PATANJALI", "ICICIGI", "TRENT", "HINDZINC", "PPLPHARMA",
                "PAGEIND", "MAZDOCK", "SBIN", "DELHIVERY", "LICI", "COLPAL", "TITAN", "MANAPPURAM",
                "ASHOKLEY", "APLAPOLLO", "TATATECH", "DALBHARAT", "BAJAJ-AUTO", "NUVAMA",
                "EICHERMOT", "ULTRACEMCO", "FORTIS", "RBLBANK", "HINDALCO", "HUDCO", "PAYTM",
                "MPHASIS", "HINDPETRO", "ICICIPRULI", "BPCL", "TATAELXSI", "SAIL", "BOSCHLTD",
                "TVSMOTOR", "TMPV", "CHOLAFIN", "IRCTC", "BAJFINANCE", "SONACOMS", "M&M",
                "NATIONALUM", "JIOFIN", "DMART", "MCX", "WIPRO", "MARUTI", "POLICYBZR", "NAUKRI",
                "INDHOTEL", "BLUESTARCO", "IOC", "INFY", "KEI", "TECHM", "UNOMINDA", "HEROMOTOCO",
                "INOXWIND", "MUTHOOTFIN", "PIIND", "ANGELONE", "BSE",
            }

            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept":     "application/json",
                "Referer":    "https://www.nseindia.com/",
            })

            try:
                session.get("https://www.nseindia.com", timeout=10)
            except Exception:
                logger.warning("[SECTOR_SCAN] NSE homepage pre-request failed, continuing anyway")

            try:
                res = session.get(
                    "https://www.nseindia.com/api/heatmap-index?type=Sectoral%20Indices",
                    timeout=10,
                ).json()
            except Exception:
                logger.exception("[SECTOR_SCAN] Failed to fetch sector index list")
                return

            sectors = []
            for item in res:
                try:
                    sectors.append({
                        "scan_time":     scan_time,
                        "sector":        item["index"],
                        "sector_change": float(item["pChange"]),
                        "status":        "ACTIVE",
                    })
                except (KeyError, ValueError) as e:
                    logger.warning(f"[SECTOR_SCAN] Skipping malformed sector item: {e}")

            if not sectors:
                logger.warning("[SECTOR_SCAN] No sectors found")
                return

            sectors = sorted(sectors, key=lambda x: abs(x["sector_change"]), reverse=True)[:SECTOR_SCAN_LIMIT]
            logger.info(f"[SECTOR_SCAN] Top {len(sectors)} sectors selected")

            all_stocks    = []
            total_scanned = fno_reject = dir_reject = selected = 0

            for sector in sectors:
                try:
                    sector_name = sector["sector"]
                    formatted   = quote(sector_name)
                    url = (
                        f"https://www.nseindia.com/api/heatmap-symbols"
                        f"?type=Sectoral%20Indices&indices={formatted}"
                    )
                    logger.info(f"[SECTOR_SCAN] Sector: {sector_name}")
                    logger.info(f"[SECTOR_SCAN] Fetching stocks using URL: {url}")

                    try:
                        stocks = session.get(url, timeout=10).json()
                    except Exception:
                        logger.exception(f"[SECTOR_SCAN] Failed to fetch stocks for {sector_name}")
                        continue

                    for stock in stocks:
                        try:
                            if stock.get("symbol") == sector_name:
                                continue

                            total_scanned += 1
                            symbol = stock["symbol"].upper()

                            if symbol not in fno_symbols:
                                logger.info(
                                    f"[FNO_FILTER] Rejected {symbol} "
                                    f"(Sector: {sector_name}) - Not present in F&O universe"
                                )
                                fno_reject += 1
                                continue

                            stock_change = float(stock["pChange"])

                            if sector["sector_change"] > 0 and stock_change < 0.5:
                                dir_reject += 1
                                continue
                            if sector["sector_change"] < 0 and stock_change > -0.5:
                                dir_reject += 1
                                continue

                            all_stocks.append({
                                "scan_time":       scan_time,
                                "Sector":          sector_name,
                                "Sector Change %": sector["sector_change"],
                                "Symbol":          symbol,
                                "Price":           float(stock["lastPrice"]),
                                "Stock Change %":  stock_change,
                                "status":          "ACTIVE",
                            })
                            selected += 1
                        except Exception:
                            logger.exception(f"[SECTOR_SCAN] Error processing stock in {sector_name}")

                except Exception:
                    logger.exception(f"[SECTOR_SCAN] Failed processing sector {sector.get('sector')}")

            if not all_stocks:
                logger.warning("[SECTOR_SCAN] No stocks matched criteria")
                return

            stocks_df     = pd.DataFrame(all_stocks)
            filtered_rows = []
            for sector_name, group in stocks_df.groupby("Sector"):
                sc  = group["Sector Change %"].iloc[0]
                top = (
                    group.sort_values("Stock Change %", ascending=False).head(STOCK_SCAN_LIMIT)
                    if sc > 0
                    else group.sort_values("Stock Change %", ascending=True).head(STOCK_SCAN_LIMIT)
                )
                filtered_rows.append(top)

            stocks_df               = pd.concat(filtered_rows, ignore_index=True)
            stocks_df["abs_sector"] = stocks_df["Sector Change %"].abs()
            stocks_df["abs_stock"]  = stocks_df["Stock Change %"].abs()
            stocks_df = stocks_df.sort_values(
                by=["abs_sector", "abs_stock"], ascending=[False, False]
            ).drop(columns=["abs_sector", "abs_stock"])
            stocks_df = stocks_df.drop_duplicates(subset=["Symbol"], keep="first")

            self.update_csv_with_status(
                "sectors_filtered.csv",
                pd.DataFrame(sectors),
                ["scan_time", "sector", "sector_change", "status"],
            )
            self.update_csv_with_status(
                "sectorwise_stocks_filtered.csv",
                stocks_df,
                ["scan_time", "Sector", "Sector Change %", "Symbol", "Price", "Stock Change %", "status"],
            )

            logger.info(
                f"[STOCK_FILTER] Scanned: {total_scanned} | "
                f"FNO rejected: {fno_reject} | "
                f"Direction rejected: {dir_reject} | "
                f"Selected: {selected}"
            )
            logger.info(f"[SECTOR_SCAN] Completed at {self._now_ist().strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception:
            logger.exception("[SECTOR_SCAN] Fatal error in run_scrap_sector")

    # ===============================
    # SCHEDULER LOOP
    # ===============================

    def scheduler_loop(self, angel, settings, user_profile):
        logger.info(f"[BOT] Scheduler Started For User {user_profile.id}")
        logger.info("[BOT] Bot ACTIVE and waiting for Phase-1 start time")

        phase1_executed       = False
        phase2_active         = False
        last_phase2_scan_slot = -1

        current_day = self._now_ist().date()
        csv_cleaned = False

        while not self._is_stop_requested():
            try:
                now          = self._now_ist()
                today        = now.date()
                current_time = now.time()

                # ---- Day rollover ----
                if today != current_day:
                    logger.info(f"[SCHEDULER] New trading day: {today}. Resetting flags.")
                    current_day           = today
                    phase1_executed       = False
                    phase2_active         = False
                    last_phase2_scan_slot = -1
                    csv_cleaned           = False
                    self._ws_phase1_started = False
                    self._ws_phase2_started = False
                    self.trades_today     = 0
                    if self.websocket_manager:
                        try:
                            self.websocket_manager.close_connection()
                        except Exception:
                            logger.exception("[SCHEDULER] Error closing WS on day rollover")

                # ---- Clean CSVs once per day ----
                if not csv_cleaned:
                    self.clean_old_csv_data()
                    csv_cleaned = True

                # ================================================
                # PHASE 1  — executes ONCE
                # ================================================
                if (self._phase1_start <= current_time <= self._phase1_end
                        and not phase1_executed):

                    logger.info(f"[PHASE1] Started at {now.strftime('%H:%M:%S')}")
                    try:
                        self._run_phase1(angel, settings, user_profile)
                    except Exception:
                        logger.exception("[PHASE1] Unhandled error in _run_phase1")

                    phase1_executed = True
                    logger.info("[PHASE1] Completed — will not re-run today")
                    time.sleep(2)
                    continue

                # ================================================
                # PHASE 2  — runs with 15-min scan intervals
                # ================================================
                elif self._phase2_start <= current_time <= self._phase2_end:

                    if not self._ws_phase2_started:
                        logger.info("[PHASE2] Starting WebSocket for Phase 2")
                        if self.websocket_manager:
                            try:
                                creds = self._get_ws_credentials()
                                self.websocket_manager.start(
                                    angel        = angel,
                                    settings     = settings,
                                    user_profile = user_profile,
                                    order_manager= self.order_manager,
                                    strategy     = self,
                                    **creds,
                                )
                            except Exception:
                                logger.exception("[PHASE2] Error starting WebSocket")
                        self._ws_phase2_started = True
                        phase2_active = True

                    interval_minutes  = self.PHASE2_SCAN_INTERVAL_MINUTES
                    current_slot      = (now.hour * 60 + now.minute) // interval_minutes

                    if now.second == 0 and current_slot != last_phase2_scan_slot:
                        last_phase2_scan_slot = current_slot
                        logger.info(
                            f"[PHASE2] Running {interval_minutes}-min interval scan "
                            f"at {now.strftime('%H:%M')}"
                        )
                        try:
                            self._run_phase2_scan(angel, settings, user_profile, now)
                        except Exception:
                            logger.exception("[PHASE2] Error in interval scan")

                    time.sleep(1)

                # ================================================
                # AFTER MARKET HOURS
                # ================================================
                elif current_time > self._phase2_end:
                    if phase2_active:
                        logger.info("[PHASE2] Market closed. Cleaning up.")
                        phase2_active = False
                        if self.websocket_manager:
                            try:
                                self.websocket_manager.unsubscribe_all()
                            except Exception:
                                logger.exception("[SCHEDULER] Error unsubscribing on market close")
                    time.sleep(60)

                else:
                    # Pre-market waiting
                    time.sleep(5)

            except Exception:
                logger.exception("[SCHEDULER ERROR] Unexpected error in scheduler loop")
                time.sleep(10)

    # ===============================
    # PHASE 1  — scan + build watchlist + start 1-min signal checker
    # ===============================

    def _run_phase1(self, angel, settings, user_profile):
        logger.info("[DEBUG] _run_phase1() called")
        logger.info("[PHASE1] Starting Phase 1 sector scan")

        self.deactivate_watchlist1()

        # ---- Sector scan with retry ----
        all_stocks = None
        for attempt in range(3):
            if self._is_stop_requested():
                return
            self.run_scrap_sector(settings)
            try:
                df = pd.read_csv("sectorwise_stocks_filtered.csv")
                today = self._now_ist().date()
                df["scan_time"] = pd.to_datetime(df["scan_time"], errors="coerce")
                df_today = df[df["scan_time"].dt.date == today]
                if not df_today.empty:
                    all_stocks = df_today
                    logger.info(f"[PHASE1] Found {len(all_stocks)} stocks on attempt {attempt + 1}")
                    break
            except Exception:
                logger.exception("[PHASE1] Error reading sectorwise_stocks_filtered.csv")

            if attempt < 2:
                logger.warning(f"[PHASE1] No stocks found. Retry {attempt + 2}/3")
                time.sleep(3)

        if all_stocks is None or all_stocks.empty:
            logger.warning("[PHASE1] No stocks found after all retries — skipping Phase 1")
            return

        logger.info(f"[PHASE1] {len(all_stocks)} stocks found. Processing for watchlist.")
        self.process_stocks_for_monitoring(angel, settings, all_stocks, user_profile)

        logger.info(f"[PHASE1] Watchlist size: {len(self.watchlist)}")

        # ---- Start 1-min signal checker thread for Phase 1 watchlist ----
        if os.path.exists(self.watchlist_csv):
            try:
                wl_df = pd.read_csv(self.watchlist_csv)
                active = wl_df[wl_df["status"] == "ACTIVE"]
                if not active.empty:
                    logger.info(
                        f"[PHASE1] Starting 1-min signal checker for "
                        f"{len(active)} active watchlist entries"
                    )
                    t = threading.Thread(
                        target=self._phase1_signal_checker,
                        args=(angel, settings, user_profile),
                        daemon=True,
                    )
                    t.start()
                else:
                    logger.info("[PHASE1] No active watchlist entries — signal checker not started")
            except Exception:
                logger.exception("[PHASE1] Error reading watchlist before starting signal checker")

    # ===============================
    # PHASE 1 — 1-MIN SIGNAL CHECKER
    # Polls option symbol 1-min candles.
    # Trigger: latest completed 1-min close > stored five_min_high (option's 5-min candle high)
    # ===============================

    def _phase1_signal_checker(self, angel, settings, user_profile):
        """
        Runs as a daemon thread after Phase 1 watchlist is built.

        For each ACTIVE entry in watchlist.csv:
          - Fetches 1-minute candles for the OPTION SYMBOL (not stock symbol)
          - Trigger condition: latest completed 1-min candle close > five_min_high
            (where five_min_high was stored from the option's own 5-min candle
             at watchlist creation time)
          - On trigger: calls order_manager to place order, marks entry INACTIVE

        Polling interval: 60 seconds (aligned to 1-min candle close rhythm).
        Stops when Phase 2 start time is reached, stop is requested, or
        no active entries remain.
        """
        logger.info("[PHASE1 CHECKER] 1-min signal checker thread started")

        instrument_list = self.order_manager.instrument_list

        while not self._is_stop_requested():
            now          = self._now_ist()
            current_time = now.time()

            # Stop checker once Phase 2 begins
            if current_time >= self._phase2_start:
                logger.info("[PHASE1 CHECKER] Phase 2 start reached — stopping signal checker")
                break

            try:
                if not os.path.exists(self.watchlist_csv):
                    logger.info("[PHASE1 CHECKER] watchlist.csv not found — sleeping")
                    time.sleep(60)
                    continue

                wl_df = pd.read_csv(self.watchlist_csv)
                active = wl_df[wl_df["status"] == "ACTIVE"]

                if active.empty:
                    logger.info("[PHASE1 CHECKER] No active entries remaining — stopping")
                    break

                logger.info(
                    f"[PHASE1 CHECKER] Checking {len(active)} active entries "
                    f"at {now.strftime('%H:%M:%S')}"
                )

                for idx, (_, entry) in enumerate(active.iterrows()):
                    if self._is_stop_requested():
                        break

                    option_symbol = entry["option_symbol"]
                    five_min_high = float(entry["five_min_high"])

                    # Inter-symbol delay to avoid burst rate-limiting
                    if idx > 0:
                        time.sleep(1)

                    logger.info(
                        f"[PHASE1 CHECKER] Fetching 1-min candles for option: {option_symbol} | "
                        f"five_min_high (option 5-min high)={five_min_high}"
                    )

                    one_min_data = self.get_todays_ohlc_data_(
                        angel,
                        option_symbol,
                        interval="ONE_MINUTE",
                        instrument_list=instrument_list,
                        exchange="NFO",
                    )

                    if one_min_data is None or one_min_data.empty:
                        logger.info(
                            f"[PHASE1 CHECKER] No 1-min data for {option_symbol}, skipping"
                        )
                        continue

                    try:
                        one_min_data["Timestamp"] = pd.to_datetime(
                            one_min_data["Timestamp"], utc=True
                        )
                        one_min_data["Timestamp"] = one_min_data["Timestamp"].dt.tz_convert(IST)
                        one_min_data = one_min_data.sort_values("Timestamp").reset_index(drop=True)

                        today_date    = now.date()
                        today_candles = one_min_data[
                            one_min_data["Timestamp"].dt.date == today_date
                        ]

                        if today_candles.empty:
                            logger.info(
                                f"[PHASE1 CHECKER] No today 1-min candles for {option_symbol}"
                            )
                            continue

                        # Use the latest completed candle
                        # (last row — the most recently closed 1-min candle)
                        # latest_1min = today_candles.iloc[-1]
                        # latest_close = float(latest_1min["close"])
                        # latest_ts    = latest_1min["Timestamp"]

                        # logger.info(
                        #     f"[PHASE1 CHECKER] {option_symbol} | "
                        #     f"Latest 1-min close={latest_close} @ {latest_ts} | "
                        #     f"five_min_high={five_min_high} | "
                        #     f"Signal={'YES' if latest_close > five_min_high else 'NO'}"
                        # )

                        # # ---- TRIGGER CONDITION ----
                        # if latest_close > five_min_high:
                        #     logger.info(
                        #         f"[PHASE1 CHECKER] SIGNAL TRIGGERED for {option_symbol} | "
                        #         f"1-min close ({latest_close}) > option 5-min high ({five_min_high})"
                        #     )

                        #     if self.trades_today >= self.max_trades_per_day:
                        #         logger.info(
                        #             f"[PHASE1 CHECKER] Trade limit reached "
                        #             f"({self.trades_today}/{self.max_trades_per_day}), "
                        #             f"skipping order for {option_symbol}"
                        #         )
                        #         continue

                        #     # Place order via order_manager
                        #     try:
                        #         self.order_manager.place_order(
                        #             angel        = angel,
                        #             symbol       = option_symbol,
                        #             entry        = entry.to_dict(),
                        #             settings     = settings,
                        #             user_profile = user_profile,
                        #             strategy     = self,
                        #         )
                        #         logger.info(
                        #             f"[PHASE1 CHECKER] Order placed for {option_symbol}"
                        #         )
                        #     except Exception:
                        #         logger.exception(
                        #             f"[PHASE1 CHECKER] Error placing order for {option_symbol}"
                        #         )

                        #     # Mark entry INACTIVE in CSV so it is not re-triggered
                        #     try:
                        #         updated_df = pd.read_csv(self.watchlist_csv)
                        #         mask = (
                        #             (updated_df["option_symbol"] == option_symbol) &
                        #             (updated_df["status"] == "ACTIVE")
                        #         )
                        #         updated_df.loc[mask, "status"] = "INACTIVE"
                        #         updated_df.to_csv(self.watchlist_csv, index=False)
                        #         logger.info(
                        #             f"[PHASE1 CHECKER] Marked {option_symbol} INACTIVE in watchlist"
                        #         )
                        #     except Exception:
                        #         logger.exception(
                        #             f"[PHASE1 CHECKER] Error marking {option_symbol} INACTIVE"
                        #         )

                        
                        
                        # =====================================================
                        # CHECK ALL 1-MIN CANDLES FROM 09:20 ONWARDS
                        # Timestamp=09:20 => Candle 09:20-09:21
                        # =====================================================
                        # Use latest completed candle only
                        latest_1min = today_candles.iloc[-1]

                        latest_close = float(latest_1min["close"])
                        latest_ts = latest_1min["Timestamp"]

                        logger.info(
                            f"[PHASE1 CHECKER] {option_symbol} | "
                            f"Latest 1-min close={latest_close} @ {latest_ts} | "
                            f"five_min_high={five_min_high} | "
                            f"Signal={'YES' if latest_close > five_min_high else 'NO'}"
                        )

                        # ---- TRIGGER CONDITION ----
                        if latest_close > five_min_high:

                            logger.info(
                                f"[PHASE1 CHECKER] SIGNAL TRIGGERED for {option_symbol} | "
                                f"1-min close ({latest_close}) > option 5-min high ({five_min_high})"
                            )

                            if self.trades_today >= self.max_trades_per_day:
                                logger.info(
                                    f"[PHASE1 CHECKER] Trade limit reached "
                                    f"({self.trades_today}/{self.max_trades_per_day}), "
                                    f"skipping order for {option_symbol}"
                                )
                                continue

                            # Place order via order_manager
                            try:
                                self.order_manager.place_order(
                                    angel=angel,
                                    symbol=option_symbol,
                                    entry=entry.to_dict(),
                                    settings=settings,
                                    user_profile=user_profile,
                                    strategy=self,
                                )

                                logger.info(
                                    f"[PHASE1 CHECKER] Order placed for {option_symbol}"
                                )

                            except Exception:
                                logger.exception(
                                    f"[PHASE1 CHECKER] Error placing order for {option_symbol}"
                                )

                            # Mark entry INACTIVE in CSV
                            try:
                                updated_df = pd.read_csv(self.watchlist_csv)

                                mask = (
                                    (updated_df["option_symbol"] == option_symbol)
                                    &
                                    (updated_df["status"] == "ACTIVE")
                                )

                                updated_df.loc[mask, "status"] = "INACTIVE"

                                updated_df.to_csv(
                                    self.watchlist_csv,
                                    index=False
                                )

                                logger.info(
                                    f"[PHASE1 CHECKER] Marked "
                                    f"{option_symbol} INACTIVE in watchlist"
                                )

                            except Exception:
                                logger.exception(
                                    f"[PHASE1 CHECKER] Error marking "
                                    f"{option_symbol} INACTIVE"
                                )

                        else:
                            logger.info(
                                f"[PHASE1 CHECKER] No breakout found for "
                                f"{option_symbol}"
                            )
                        
                    except Exception:
                        logger.exception(
                            f"[PHASE1 CHECKER] Error processing 1-min data for {option_symbol}"
                        )
                        continue

            except Exception:
                logger.exception("[PHASE1 CHECKER] Unexpected error in signal checker loop")

            # Sleep 60s before next poll cycle
            time.sleep(60)

        logger.info("[PHASE1 CHECKER] Signal checker thread exiting")

    def process_stocks_for_monitoring(self, angel, settings, stocks_data, user_profile):
        """
        Build Phase 1 watchlist.

        Per requirement doc (Step 6):
          OHLC data is fetched on the UNDERLYING STOCK on NSE exchange,
          NOT on the option contract.
          Example: fetch data for RELIANCE, not for RELIANCE27JUN2800CE

        Data fetched from underlying stock:
          - Previous Day High (PDH) and Previous Day Date
          - Today's first 5-min candle (09:15 candle): Open, High, Low, Close, Volume
          - 20-day average volume

        Conditions checked on STOCK candle data (Step 7):
          C1: Previous Day High < Today's First Candle Open
          C2: Volume >= volume_multiplier * avg_20_volume
          C3: Green candle (close >= open)

        Only AFTER all conditions pass (Step 8):
          - Direction determined from Stock Change % (positive → CE, negative → PE)
          - Option symbol created via angel_fetch_symbol()

        CHANGED (Phase 1 watchlist entry):
          - After option symbol is created, fetch option's own 5-min candle
          - five_min_high stored = option symbol's 5-min candle HIGH
            (used by _phase1_signal_checker as the trigger threshold)
          - No WebSocket subscription in Phase 1

        FIX: Added 1s inter-stock delay to reduce burst rate-limiting.
        """
        logger.info(f"[PHASE1] Analyzing {len(stocks_data)} stocks for Phase 1 watchlist")
        logger.info("[PHASE1] OHLC data will be fetched for UNDERLYING STOCK on NSE (not option contract)")

        if self.trades_today >= self.max_trades_per_day:
            logger.info(
                f"[PHASE1] Trade limit reached ({self.trades_today}/{self.max_trades_per_day}). Skipping."
            )
            return

        instrument_list = self.order_manager.instrument_list
        symboldf        = self.order_manager.symboldf
        processed       = added = 0

        for stock_idx, (_, stock) in enumerate(stocks_data.iterrows()):
            if self._is_stop_requested():
                break

            if stock.get("status") != "ACTIVE":
                continue

            # Inter-stock delay to avoid rate-limiting (skip before first stock)
            if stock_idx > 0:
                time.sleep(1)

            symbol = stock["Symbol"]

            # Skip if already in active watchlist today
            try:
                if os.path.exists(self.watchlist_csv):
                    ex_df = pd.read_csv(self.watchlist_csv)
                    if "stock_symbol" in ex_df.columns:
                        already = ex_df[
                            (ex_df["stock_symbol"] == symbol) &
                            (ex_df["status"] == "ACTIVE")
                        ]
                        if not already.empty:
                            logger.info(f"[PHASE1] {symbol} already in active watchlist, skipping")
                            continue
            except Exception:
                logger.exception(f"[PHASE1] Error checking existing watchlist for {symbol}")

            processed += 1

            # ------------------------------------------------------------------
            # STEP 1: Fetch OHLC data for UNDERLYING STOCK on NSE
            # Requirement: "OHLC data is fetched on the Underlying Stock,
            #               not on the option contract"
            # ------------------------------------------------------------------
            logger.info(
                f"[PHASE1] Fetching OHLC data for UNDERLYING STOCK: {symbol} on NSE exchange"
            )
            stock_candle_data = self.get_todays_ohlc_data_(
                angel, symbol, interval="5",
                instrument_list=instrument_list, exchange="NSE",
            )

            if stock_candle_data is None or stock_candle_data.empty:
                logger.info(f"[PHASE1] No stock candle data for {symbol}, skipping")
                continue

            try:
                stock_candle_data["Timestamp"] = pd.to_datetime(
                    stock_candle_data["Timestamp"], utc=True
                )
                stock_candle_data["Timestamp"] = stock_candle_data["Timestamp"].dt.tz_convert(IST)
                stock_candle_data = stock_candle_data.sort_values("Timestamp").reset_index(drop=True)

                logger.info(f"[DEBUG] {symbol} Total stock candles={len(stock_candle_data)}")
                logger.info(f"[DEBUG] {symbol} Timestamp dtype={stock_candle_data['Timestamp'].dtype}")
                logger.info(f"[DEBUG] {symbol} First timestamp={stock_candle_data['Timestamp'].iloc[0]}")
                logger.info(f"[DEBUG] {symbol} Last timestamp={stock_candle_data['Timestamp'].iloc[-1]}")
                logger.info(
                    f"[DEBUG] {symbol} "
                    f"Unique dates={list(stock_candle_data['Timestamp'].dt.date.unique())[-10:]}"
                )

                today_date    = self._now_ist().date()
                logger.info(f"[DEBUG] System today={today_date}")

                today_candles = stock_candle_data[stock_candle_data["Timestamp"].dt.date == today_date]
                prev_candles  = stock_candle_data[stock_candle_data["Timestamp"].dt.date < today_date]

                logger.info(f"[DEBUG] {symbol} today_date={today_date}")
                logger.info(f"[DEBUG] {symbol} today_candles={len(today_candles)}")
                logger.info(f"[DEBUG] {symbol} prev_candles={len(prev_candles)}")

                if not today_candles.empty:
                    logger.info(
                        f"[DEBUG] {symbol} "
                        f"first_today={today_candles.iloc[0]['Timestamp']}"
                    )

                if today_candles.empty:
                    logger.info(f"[PHASE1] No today candles for stock {symbol}, skipping")
                    continue

                if prev_candles.empty:
                    logger.info(f"[PHASE1] No previous day data for stock {symbol}, skipping")
                    continue

                logger.info(
                    f"[DEBUG] {symbol} Available dates="
                    f"{sorted(list(prev_candles['Timestamp'].dt.date.unique()))}"
                )

                # ==========================================================
                # PREVIOUS TRADING DAY DATA  (from underlying stock candles)
                # Requirement: Previous Day High and Previous Day Date
                # ==========================================================

                last_day = prev_candles["Timestamp"].dt.date.max()

                last_day_df = prev_candles[
                    prev_candles["Timestamp"].dt.date == last_day
                ].copy()

                if last_day_df.empty:
                    logger.warning(
                        f"[PHASE1] {symbol} "
                        f"No stock candles found for previous trading day {last_day}"
                    )
                    continue

                prev_day_high  = float(last_day_df["high"].max())
                prev_day_low   = float(last_day_df["low"].min())
                prev_day_open  = float(last_day_df.iloc[0]["open"])
                prev_day_close = float(last_day_df.iloc[-1]["close"])

                high_candle = last_day_df.loc[last_day_df["high"].idxmax()]

                logger.info(
                    f"[PREV_DAY] {symbol} | "
                    f"Date={last_day} | "
                    f"Candles={len(last_day_df)} | "
                    f"Open={prev_day_open:.2f} | "
                    f"High={prev_day_high:.2f} | "
                    f"Low={prev_day_low:.2f} | "
                    f"Close={prev_day_close:.2f}"
                )

                logger.info(
                    f"[PREV_DAY_HIGH] {symbol} | "
                    f"High={prev_day_high:.2f} | "
                    f"Time={high_candle['Timestamp']}"
                )

                logger.info(
                    f"[PREV_DAY_FIRST] {symbol} | "
                    f"{last_day_df.iloc[0].to_dict()}"
                )

                logger.info(
                    f"[PREV_DAY_LAST] {symbol} | "
                    f"{last_day_df.iloc[-1].to_dict()}"
                )

                # ==========================================================
                # TODAY FIRST 5-MIN CANDLE (09:15 candle) from underlying stock
                # Requirement: "Today's First 5 Minute Candle (09:15 Candle)"
                # ==========================================================

                first_candle = today_candles.iloc[0]
                first_ts     = first_candle["Timestamp"]

                logger.info(
                    f"[PHASE1] {symbol} | "
                    f"Stock First Candle (09:15): "
                    f"PDH={prev_day_high:.2f} | "
                    f"Open={first_candle['open']:.2f} | High={first_candle['high']:.2f} | "
                    f"Low={first_candle['low']:.2f} | Close={first_candle['close']:.2f} | "
                    f"Vol={first_candle['volume']:.0f} | Timestamp={first_ts}"
                )

                # 20-day average volume from stock candles
                historical_days = (
                    prev_candles
                    .groupby(prev_candles["Timestamp"].dt.date)["volume"]
                    .sum()
                    .sort_index()
                )

                last_20_days = historical_days.tail(20)

                if len(last_20_days) < 20:
                    logger.info(
                        f"[PHASE1] {symbol} Less than 20 trading days data available "
                        f"({len(last_20_days)} days), skipping"
                    )
                    continue

                avg_vol = float(last_20_days.mean())

                volume_multiplier = float(
                    settings.get("volume_multiplier", 1.0)
                )

                req_vol = avg_vol * volume_multiplier

                logger.info(
                    f"[PHASE1][VOLUME] {symbol} | "
                    f"20DayAvgVol={avg_vol:.0f} | "
                    f"Multiplier={volume_multiplier} | "
                    f"RequiredVol={req_vol:.0f} | "
                    f"FirstCandleVol={first_candle['volume']:.0f}"
                )

                # ==========================================================
                # PHASE 1 CONDITIONS checked on STOCK candle data
                # ==========================================================

                # C1: Previous Day High < Today's First Candle Open
                # c1 = prev_day_high < first_candle["open"]


                # C2: Today's Volume >= Volume Multiplier × Avg20Volume
                # c2 = float(first_candle["volume"]) >= req_vol

                c1 = True
                c2 = True


                # C3: Green Candle (Close >= Open)
                c3 = first_candle["close"] >= first_candle["open"]

                logger.info(
                    f"[PHASE1][C1] PDH({prev_day_high:.2f}) < OPEN({first_candle['open']:.2f}): {c1}"
                )
                logger.info(
                    f"[PHASE1][C2] Vol({first_candle['volume']:.0f}) >= Req({req_vol:.0f}): {c2}"
                )
                logger.info(
                    f"[PHASE1][C3] Green candle "
                    f"close({first_candle['close']:.2f}) >= open({first_candle['open']:.2f}): {c3}"
                )

                if not all([c1, c2, c3]):
                    failed = []
                    if not c1: failed.append("PDH<OPEN")
                    if not c2: failed.append("VOLUME")
                    if not c3: failed.append("GREEN_CANDLE")
                    logger.info(f"[PHASE1][REJECTED] {symbol} | Failed: {', '.join(failed)}")
                    continue

                logger.info(f"[PHASE1][PASSED] {symbol} | All conditions passed on stock candle data")

                # ==========================================================
                # STEP 2: After conditions pass — create OPTION SYMBOL
                # Requirement: "After all Phase 1 conditions pass:
                #               Direction is determined.
                #               Positive Stock Movement -> CE
                #               Negative Stock Movement -> PE"
                # ==========================================================

                option_type = "CE" if float(stock["Stock Change %"]) > 0 else "PE"
                logger.info(
                    f"[PHASE1] {symbol} Stock Change%={stock['Stock Change %']:.2f} "
                    f"-> Option Type: {option_type}"
                )

                logger.info(
                    f"[PHASE1] Creating option symbol for {symbol} ({option_type}) "
                    f"after all conditions passed"
                )
                option_symbol = self.angel_fetch_symbol(
                    angel, symbol, symbol, option_type, settings, instrument_list, symboldf
                )
                if not option_symbol:
                    logger.warning(
                        f"[PHASE1] Could not create option symbol for {symbol}, skipping"
                    )
                    continue

                logger.info(
                    f"[PHASE1] Option symbol created: {option_symbol} for stock {symbol}"
                )

                # ==========================================================
                # STEP 3: Fetch option's own 5-min candle to get five_min_high
                # CHANGED: five_min_high is now from the OPTION SYMBOL's 5-min candle,
                #          not from the stock's first candle.
                # This value is later used by _phase1_signal_checker as the
                # trigger threshold: option 1-min close > five_min_high
                # ==========================================================

                logger.info(
                    f"[PHASE1] Fetching 5-min candle for OPTION SYMBOL: {option_symbol} on NFO"
                )
                time.sleep(1)  # Small delay before option candle fetch
                option_candle_data = self.get_todays_ohlc_data_(
                    angel, option_symbol, interval="5",
                    instrument_list=instrument_list, exchange="NFO",
                )

                if option_candle_data is None or option_candle_data.empty:
                    logger.warning(
                        f"[PHASE1] No 5-min candle data for option {option_symbol}, skipping"
                    )
                    continue

                option_candle_data["Timestamp"] = pd.to_datetime(
                    option_candle_data["Timestamp"], utc=True
                )
                option_candle_data["Timestamp"] = option_candle_data["Timestamp"].dt.tz_convert(IST)
                option_candle_data = option_candle_data.sort_values("Timestamp").reset_index(drop=True)

# ========================Fetch latest 5 min candle for available option symbol================
                # opt_today_candles = option_candle_data[
                #     option_candle_data["Timestamp"].dt.date == today_date
                # ]

                # if opt_today_candles.empty:
                #     logger.warning(
                #         f"[PHASE1] No today 5-min candles for option {option_symbol}, skipping"
                #     )
                #     continue

                # # Use the first today candle (09:15 candle) of the option
                # opt_first_candle  = opt_today_candles.iloc[0]
                # option_five_min_high = float(opt_first_candle["high"])
                # option_five_min_low  = float(opt_first_candle["low"])
                # option_five_min_close = float(opt_first_candle["close"])
                # option_five_min_volume = float(opt_first_candle["volume"])
                
                
                
                opt_today_candles = option_candle_data[
                    option_candle_data["Timestamp"].dt.date == today_date
                ]

                if opt_today_candles.empty:
                    logger.warning(
                        f"[PHASE1] No today 5-min candles for option {option_symbol}, skipping"
                    )
                    continue

                # =====================================================
                # STRICT REQUIREMENT:
                # ONLY USE 09:15 -> 09:20 OPTION CANDLE
                # IF NOT AVAILABLE => SKIP STOCK
                # =====================================================

                target_915_candle = opt_today_candles[
                    (opt_today_candles["Timestamp"].dt.hour == 9) &
                    (opt_today_candles["Timestamp"].dt.minute == 15)
                ]

                if target_915_candle.empty:
                    logger.warning(
                        f"[PHASE1] {option_symbol} "
                        f"09:15 option candle not found. Skipping stock."
                    )
                    continue

                opt_first_candle = target_915_candle.iloc[0]

                option_five_min_high = float(opt_first_candle["high"])
                option_five_min_low = float(opt_first_candle["low"])
                option_five_min_close = float(opt_first_candle["close"])
                option_five_min_volume = float(opt_first_candle["volume"])

                logger.info(
                    f"[PHASE1] Option {option_symbol} first 5-min candle | "
                    f"High={option_five_min_high:.2f} | "
                    f"Low={option_five_min_low:.2f} | "
                    f"Close={option_five_min_close:.2f} | "
                    f"Volume={option_five_min_volume:.0f} | "
                    f"Timestamp={opt_first_candle['Timestamp']}"
                )

                # ==========================================================
                # STEP 4: Build watchlist entry
                # five_min_high = option's 5-min candle HIGH (trigger threshold)
                # five_min_low, five_min_close, five_min_volume = option's 5-min candle values
                # stoploss = option's 5-min candle LOW
                # avg_volume_20 retained from stock (20-day stock avg volume)
                # ==========================================================

                entry = {
                    "timestamp":         self._now_ist(),
                    "option_symbol":     option_symbol,
                    "stock_symbol":      symbol,
                    "option_type":       option_type,
                    "previous_day_high": prev_day_high,
                    "previous_day_date": str(last_day),
                    "five_min_high":     option_five_min_high,    # option's 5-min candle HIGH — trigger threshold
                    "five_min_low":      option_five_min_low,     # option's 5-min candle LOW
                    "five_min_close":    option_five_min_close,   # option's 5-min candle CLOSE
                    "five_min_volume":   option_five_min_volume,  # option's 5-min candle VOLUME
                    "avg_volume_20":     avg_vol,
                    "entry_signal":      False,
                    "status":            "ACTIVE",
                    "stoploss":          option_five_min_low,     # stoploss = option's 5-min candle LOW
                }

                self.watchlist.append(entry)
                added += 1
                logger.info(
                    f"[PHASE1] Added to watchlist: "
                    f"option_symbol={option_symbol} | "
                    f"stock_symbol={symbol} | "
                    f"five_min_high={option_five_min_high:.2f} (option 5-min high — 1-min trigger threshold) | "
                    f"stoploss={option_five_min_low:.2f} (option 5-min low)"
                )

                self.save_watchlist_to_csv()

            except Exception:
                logger.exception(f"[PHASE1] Error processing stock {symbol}")
                continue

        logger.info(f"[PHASE1] Processed {processed} stocks, added {added} to watchlist")

    # ===============================
    # PHASE 2 — interval scan
    # ===============================

    def _run_phase2_scan(self, angel, settings, user_profile, now):
        logger.info(f"[PHASE2] _run_phase2_scan called at {now.strftime('%H:%M:%S')}")

        self.deactivate_watchlist2()

        if self._is_stop_requested():
            return

        scan_ok = False
        for attempt in range(3):
            if self._is_stop_requested():
                return
            self.run_scrap_sector(settings)
            try:
                df = pd.read_csv("sectorwise_stocks_filtered.csv")
                today = self._now_ist().date()
                df["scan_time"] = pd.to_datetime(df["scan_time"], errors="coerce")
                df_today = df[df["scan_time"].dt.date == today]
                if not df_today.empty:
                    scan_ok = True
                    break
            except Exception:
                logger.exception("[PHASE2] Error reading sector CSV after scan")
            logger.warning(f"[PHASE2] Empty sector data. Retry {attempt + 2}/3")
            time.sleep(3)

        if not scan_ok:
            logger.warning("[PHASE2] Sector scan yielded no data, skipping this interval")
            return

        if self._is_stop_requested():
            return

        t = threading.Thread(
            target=self._process_interval_with_timeout,
            args=(angel, settings, now, user_profile),
            daemon=True,
        )
        t.start()
        t.join(timeout=240)
        if t.is_alive():
            logger.warning("[PHASE2] Interval processing timed out (240s)")

    def _process_interval_with_timeout(self, angel, settings, current_time, user_profile):
        try:
            logger.info(f"[PHASE2] Processing interval {current_time.strftime('%H:%M')}")

            if self.trades_today >= self.max_trades_per_day:
                logger.info("[PHASE2] Trade limit reached, skipping interval")
                return

            stocks_df = pd.read_csv("sectorwise_stocks_filtered.csv")
            today     = self._now_ist().date()
            stocks_df["scan_time"] = pd.to_datetime(stocks_df["scan_time"], errors="coerce")
            active = stocks_df[
                (stocks_df["status"] == "ACTIVE") &
                (stocks_df["scan_time"].dt.date == today)
            ]

            if active.empty:
                logger.info("[PHASE2] No active stocks to process")
                return

            logger.info(f"[PHASE2] Processing {len(active)} active stocks")
            for stock_idx, (_, stock) in enumerate(active.iterrows()):
                if self._is_stop_requested():
                    return
                # Inter-stock delay
                if stock_idx > 0:
                    time.sleep(1)
                try:
                    self.process_stock_for_phase2(angel, settings, stock, current_time, user_profile)
                except Exception:
                    logger.exception(f"[PHASE2] Error processing stock {stock.get('Symbol')}")

            logger.info(f"[PHASE2] Interval processing complete for {current_time.strftime('%H:%M')}")

        except Exception:
            logger.exception("[PHASE2] Interval processing error")

    def process_stock_for_phase2(self, angel, settings, stock, current_time, user_profile):
        if self.trades_today >= self.max_trades_per_day:
            logger.info(f"[PHASE2] Trade limit reached, skipping {stock['Symbol']}")
            return

        symbol      = stock["Symbol"]
        option_type = "CE" if float(stock["Stock Change %"]) > 0 else "PE"

        instrument_list = self.order_manager.instrument_list
        symboldf        = self.order_manager.symboldf

        option_symbol = self.angel_fetch_symbol(
            angel, symbol, symbol, option_type, settings, instrument_list, symboldf
        )
        if not option_symbol:
            logger.info(f"[PHASE2] No option symbol for {symbol}")
            return

        # Skip if already in active watchlist2 today
        try:
            if os.path.exists(self.watchlist_csv2):
                w2_df = pd.read_csv(self.watchlist_csv2)
                already = w2_df[
                    (w2_df["stock_symbol"] == symbol) &
                    (w2_df["status"] == "ACTIVE") &
                    (pd.to_datetime(w2_df["timestamp"]).dt.date == current_time.date())
                ]
                if not already.empty:
                    logger.info(f"[PHASE2] {symbol} already in active watchlist2, skipping")
                    return
        except Exception:
            pass

        candle_data = self.get_todays_ohlc_data_(
            angel, option_symbol, interval="5",
            instrument_list=instrument_list, exchange="NFO",
        )
        if candle_data is None or candle_data.empty:
            logger.info(f"[PHASE2] No candle data for {option_symbol}")
            return

        try:
            candle_data["Timestamp"] = pd.to_datetime(candle_data["Timestamp"], utc=True)
            candle_data["Timestamp"] = candle_data["Timestamp"].dt.tz_convert(IST)
            candle_data = candle_data.sort_values("Timestamp").reset_index(drop=True)

            today_date    = current_time.date()
            today_candles = candle_data[candle_data["Timestamp"].dt.date == today_date]
            prev_candles  = candle_data[candle_data["Timestamp"].dt.date < today_date]

            if today_candles.empty:
                logger.info(f"[PHASE2] No today candles for {option_symbol}")
                return

            if prev_candles.empty:
                logger.info(f"[PHASE2] No previous day data for {option_symbol}")
                return

            last_day         = prev_candles["Timestamp"].dt.date.max()
            last_day_candles = prev_candles[prev_candles["Timestamp"].dt.date == last_day]
            prev_day_high    = last_day_candles["high"].max()

            target_ts = pd.Timestamp(
                current_time.replace(second=0, microsecond=0)
            ).tz_localize(IST) - pd.Timedelta(minutes=5)

            current_candle = today_candles[today_candles["Timestamp"] == target_ts]

            if current_candle.empty:
                logger.info(
                    f"[PHASE2] No candle at {target_ts.strftime('%H:%M')} for {option_symbol}, "
                    f"using latest available"
                )
                current_candle = today_candles.tail(1)

            latest            = current_candle.iloc[0]
            current_candle_ts = latest["Timestamp"]

            candles_up_to = candle_data[candle_data["Timestamp"] <= current_candle_ts]
            recent_20     = candles_up_to.tail(20) if len(candles_up_to) >= 20 else candles_up_to
            avg_volume    = round(float(recent_20["volume"].mean()))
            req_volume    = float(settings.get("volume_multiplier", 1.0)) * avg_volume

            logger.info(
                f"[PHASE2] {symbol} | Vol: {latest['volume']:.0f} | "
                f"{settings.get('volume_multiplier', 1.0)}x avg: {req_volume:.0f}"
            )

            if latest["volume"] <= req_volume:
                logger.info(f"[CONDITION] FAILED — Volume check for {symbol}")
                return

            # VWAP & WMA-9
            today_vwap_df = today_candles[
                today_candles["Timestamp"] <= current_candle_ts
            ].copy().set_index("Timestamp").sort_index()

            if today_vwap_df.empty:
                logger.info(f"[PHASE2] Insufficient data for VWAP for {symbol}")
                return

            current_vwap = None
            current_wma  = None

            try:
                vwap_result = pd_ta.vwap(
                    high   = today_vwap_df["high"],
                    low    = today_vwap_df["low"],
                    close  = today_vwap_df["close"],
                    volume = today_vwap_df["volume"],
                )
                today_vwap_df["vwap"] = vwap_result

                needed_for_wma = 9
                today_count    = len(today_vwap_df)
                extra_needed   = needed_for_wma - today_count

                if extra_needed > 0 and not last_day_candles.empty:
                    prev_sorted = (
                        last_day_candles.sort_values("Timestamp")
                        .tail(extra_needed)
                        .copy()
                        .set_index("Timestamp")
                    )
                    combined = pd.concat([prev_sorted, today_vwap_df])
                else:
                    combined = today_vwap_df

                if len(combined) >= needed_for_wma:
                    wma_series = pd_ta.wma(combined["close"], length=needed_for_wma)
                    last_wma   = wma_series.iloc[-1]
                    current_wma = round(float(last_wma), 2) if not pd.isna(last_wma) else None

                if current_candle_ts in today_vwap_df.index:
                    raw = today_vwap_df.loc[current_candle_ts, "vwap"]
                    current_vwap = round(float(raw), 2) if not pd.isna(raw) else None

            except Exception:
                logger.exception(f"[PHASE2] VWAP/WMA calculation error for {symbol}")
                return

            logger.info(
                f"[CONDITION] {symbol} OHLC={latest['open']:.2f}/"
                f"{latest['high']:.2f}/{latest['low']:.2f}/{latest['close']:.2f}"
            )
            logger.info(
                f"[CONDITION] PDH={prev_day_high:.2f} | "
                f"VWAP={current_vwap} | WMA9={current_wma}"
            )

            c1 = prev_day_high < latest["open"]
            c2 = latest["volume"] > req_volume
            c3 = latest["close"] >= latest["open"]
            c4 = current_vwap is not None and latest["close"] > current_vwap
            c5 = current_wma  is not None and latest["close"] > current_wma
            c6 = current_wma  is not None and current_vwap is not None and current_vwap < current_wma

            logger.info(
                f"[CONDITION] C1(PDH<open)={c1} C2(vol)={c2} C3(green)={c3} "
                f"C4(>VWAP)={c4} C5(>WMA9)={c5} C6(VWAP<WMA9)={c6}"
            )

            if not all([c1, c2, c3, c4, c5, c6]):
                failed = [f"C{i+1}" for i, c in enumerate([c1, c2, c3, c4, c5, c6]) if not c]
                logger.info(f"[CONDITION] FAILED {failed} for {symbol}")
                return

            logger.info(f"[CONDITION] ALL CONDITIONS MET for {symbol}")

            limit_multiplier = float(settings.get("limit_multiplier", 1.0))
            limit_price      = round(float(latest["high"]) * limit_multiplier, 2)

            watchlist_entry = {
                "timestamp":       timezone.localtime(timezone.now()),
                "option_symbol":   option_symbol,
                "stock_symbol":    symbol,
                "option_type":     option_type,
                "five_min_high":   float(latest["high"]),
                "five_min_low":    float(latest["low"]),
                "five_min_close":  float(latest["close"]),
                "five_min_volume": float(latest["volume"]),
                "avg_volume_20":   avg_volume,
                "vwap":            current_vwap,
                "wma_9":           current_wma,
                "entry_signal":    True,
                "status":          "ACTIVE",
                "limit_price":     limit_price,
                "stoploss":        float(latest["low"]),
            }

            self.watchlist2.append(watchlist_entry)
            self.save_watchlist2_to_csv()
            logger.info(
                f"[PHASE2] {option_symbol} added to watchlist2 | limit_price={limit_price}"
            )

            if self.websocket_manager:
                try:
                    self.websocket_manager.subscribe_token(
                        symbol          = option_symbol,
                        limit_price     = limit_price,
                        row_data        = watchlist_entry,
                        instrument_list = instrument_list,
                    )
                    logger.info(f"[SUBSCRIBE] {option_symbol} subscribed via WebSocket")
                except Exception:
                    logger.exception(f"[SUBSCRIBE] Error subscribing {option_symbol}")

        except Exception:
            logger.exception(f"[PHASE2] Unexpected error processing {option_symbol}")

    # ===============================
    # TRADE COUNTER
    # ===============================

    def increment_trade_count(self):
        self.trades_today += 1
        logger.info(f"[ORDER] Trade counter: {self.trades_today}/{self.max_trades_per_day}")