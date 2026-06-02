"""
strategy_engine.py
------------------
Contains ONLY the SectorMomentumBreakoutStrategy strategy logic.
All websocket calls are delegated to self.websocket_manager.
All order placement calls are delegated to self.order_manager.
"""

import csv
import os
import time
import threading
import traceback
import logging
import requests
import json
import pandas as pd
import pandas_ta as pd_ta
import numpy as np
import pytz
from datetime import datetime, timedelta
from urllib.parse import quote
from django.utils import timezone

logger = logging.getLogger('dev_log')

IST = pytz.timezone("Asia/Kolkata")

# ===============================
# FIXED SCHEMAS
# ===============================
SECTOR_COLS = ["scan_time", "sector", "sector_change", "url", "status"]
STOCK_COLS = [
    "scan_time",
    "Sector",
    "Sector Change %",
    "Symbol",
    "Price",
    "Stock Change %",
    "OI Change",
    "Volume",
    "status"
]


class SectorMomentumBreakoutStrategy:

    def __init__(self, angel, settings, data, user_profile, stop_event=None, **kwargs):
        logger.info("[INIT] SectorMomentumBreakoutStrategy initializing")
        self.angel = angel
        self.settings = settings
        self.user_profile = user_profile

        self.watchlist = []
        self.watchlist_csv = 'watchlist.csv'
        self.watchlist2 = []
        self.watchlist_csv2 = 'watchlist2.csv'

        # Trade counter
        self.trades_today = 0
        self.max_trades_per_day = int(settings.get("trades_per_day", 5))
        logger.info(f"[INIT] Max trades per day: {self.max_trades_per_day}")

        self._initialize_csv_headers()
        self._initialize_csv_headers_for_watchlist2()
        self.stop_event = stop_event

        # websocket_manager and order_manager are injected from outside
        # They must be set before scheduler_loop runs
        self.websocket_manager = kwargs.get("websocket_manager", None)
        self.order_manager = kwargs.get("order_manager", None)

        self._ws_closing = False

        t = threading.Thread(
            target=self.scheduler_loop,
            args=(angel, settings, user_profile),
            daemon=True
        )
        t.start()

    # ===============================
    # CSV INIT
    # ===============================

    def _initialize_csv_headers(self):
        if not os.path.exists(self.watchlist_csv):
            headers = [
                'timestamp', 'option_symbol', 'stock_symbol', 'option_type',
                'five_min_high', 'five_min_low', 'five_min_close',
                'five_min_volume', 'avg_volume_20', 'entry_signal',
                'status', 'stoploss'
            ]
            with open(self.watchlist_csv, 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
            logger.info(f"[INIT] Created new watchlist CSV: {self.watchlist_csv}")

    def _initialize_csv_headers_for_watchlist2(self):
        if not os.path.exists(self.watchlist_csv2):
            headers = [
                'timestamp', 'option_symbol', 'stock_symbol', 'option_type',
                'five_min_high', 'five_min_low', 'five_min_close',
                'five_min_volume', 'avg_volume_20', "vwap", 'wma_9', 'entry_signal',
                'status', 'limit_price', 'stoploss'
            ]
            with open(self.watchlist_csv2, 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
            logger.info(f"[INIT] Created new watchlist2 CSV: {self.watchlist_csv2}")

    # ===============================
    # CLEAN OLD CSV DATA
    # ===============================

    def clean_old_csv_data(self):
        try:
            today = datetime.now(IST).date()

            if os.path.exists("sectors_filtered.csv"):
                sectors_df = pd.read_csv("sectors_filtered.csv")
                if 'scan_time' in sectors_df.columns:
                    sectors_df['scan_time'] = pd.to_datetime(sectors_df['scan_time'], errors='coerce')
                    sectors_df = sectors_df[sectors_df['scan_time'].dt.date == today]
                sectors_df.to_csv("sectors_filtered.csv", index=False)
                logger.info(f"[CLEAN] sectors_filtered.csv cleaned. Kept {len(sectors_df)} rows from today.")

            if os.path.exists("sectorwise_stocks_filtered.csv"):
                stocks_df = pd.read_csv("sectorwise_stocks_filtered.csv")
                if 'scan_time' in stocks_df.columns:
                    stocks_df['scan_time'] = pd.to_datetime(stocks_df['scan_time'], errors='coerce')
                    stocks_df = stocks_df[stocks_df['scan_time'].dt.date == today]
                stocks_df.to_csv("sectorwise_stocks_filtered.csv", index=False)
                logger.info(f"[CLEAN] sectorwise_stocks_filtered.csv cleaned. Kept {len(stocks_df)} rows from today.")

        except Exception as e:
            logger.error(f"[CLEAN] Error cleaning old CSV data: {e}")

    # ===============================
    # EXPIRY HELPERS
    # ===============================

    def get_last_day_of_month_fut(self, date):
        next_month = date.replace(day=28) + timedelta(days=4)
        return next_month - timedelta(days=next_month.day)

    def find_last_expiry_of_month(self, expiry_dates, month_date):
        last_expiry = None
        for expiry_date in expiry_dates:
            if expiry_date.month == month_date.month and expiry_date.year == month_date.year:
                if last_expiry is None or expiry_date > last_expiry:
                    last_expiry = expiry_date
        return last_expiry

    def getExpiryDateFut(self, index, setting, exchange, symboldf):
        symboldataframe = symboldf.copy()
        df = symboldataframe[
            (symboldf.name == index) &
            (symboldf.instrumenttype == "OPTSTK") &
            (symboldf.exch_seg == exchange)
        ].copy()

        df['expiry'] = pd.to_datetime(df['expiry'], format='%d%b%Y', errors='coerce')
        today = pd.to_datetime(timezone.localtime(timezone.now()).date())
        df = df[df.expiry >= today]
        df.reset_index(drop=True, inplace=True)

        expiry_dates = df['expiry'].dropna().unique().tolist()
        expiry_dates = pd.to_datetime(pd.Series(expiry_dates).sort_values()).reset_index(drop=True)

        current_date = timezone.localtime(timezone.now()).date()
        last_day_current_month = self.get_last_day_of_month_fut(current_date)
        last_expiry_date_this_month = self.find_last_expiry_of_month(expiry_dates, last_day_current_month)

        if last_expiry_date_this_month is None:
            next_month = current_date.replace(day=28) + timedelta(days=4)
            next_month_expiry = self.find_last_expiry_of_month(expiry_dates, next_month)
            if next_month_expiry:
                return next_month_expiry

        if setting["expiry_date"] == "next_month":
            next_month = current_date.replace(day=28) + timedelta(days=4)
            next_month_expiry = self.find_last_expiry_of_month(expiry_dates, next_month)
            if next_month_expiry:
                return next_month_expiry

        if setting["expiry_date"] == "far_month":
            far_month = current_date.replace(day=28) + timedelta(days=35)
            far_month_expiry = self.find_last_expiry_of_month(expiry_dates, far_month)
            if far_month_expiry:
                return far_month_expiry

        if last_expiry_date_this_month and last_expiry_date_this_month >= today:
            return last_expiry_date_this_month

    def get_monthly_expiry_fut(self, index, setting, exchange, symboldf):
        expiry_date = self.getExpiryDateFut(index, setting, exchange, symboldf)
        formatted_expiry = expiry_date.strftime('%d%b%y').upper()
        return formatted_expiry

    def get_inst_fut(self, index, setting, exchange, symboldf):
        expiry_code = self.get_monthly_expiry_fut(index, setting, exchange, symboldf)
        formatted_expiry = expiry_code[:-2] + expiry_code[-2:]
        return formatted_expiry

    # ===============================
    # STRIKE PRICE HELPERS
    # ===============================

    def get_correct_strike_price(self, ltp, ce_pe, strike_prices, strike_multiplier):
        higher_strikes = [s for s in strike_prices if s >= ltp]
        lower_strikes = [s for s in strike_prices if s < ltp]

        if ce_pe == "CE":
            if len(higher_strikes) >= strike_multiplier:
                strike_price = higher_strikes[strike_multiplier - 1]
            else:
                strike_price = higher_strikes[-1]
        else:
            if len(lower_strikes) >= strike_multiplier:
                strike_price = lower_strikes[-strike_multiplier]
            else:
                strike_price = lower_strikes[0]

        return strike_price

    def angel_fetch_symbol(self, obj, symbol, index, ce_pe, setting, instrument_list, symboldf):
        expiry = self.get_inst_fut(index, setting, "NFO", symboldf)
        expiry = expiry.upper()

        ltp = None
        for attempt in range(3):
            try:
                ltp_resp = self.order_manager.get_ltp(obj, instrument_list, symbol, "NSE")
                if ltp_resp["status"] and "data" in ltp_resp:
                    ltp = ltp_resp["data"]["ltp"]
                    logger.info(f"LTP fetched on attempt {attempt + 1}: {ltp}")
                    break
                else:
                    logger.warning(f"LTP response invalid on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Error fetching LTP on attempt {attempt + 1}: {e}")
            time.sleep(1)

        if ltp is None:
            logger.error(f"Could not fetch LTP for {symbol} after 3 attempts")
            return None

        filtered_data = symboldf[
            (symboldf["name"] == index) &
            (symboldf["instrumenttype"] == "OPTSTK")
        ]

        strike_prices = sorted(filtered_data["strike"].unique())
        strike_prices = [
            round(float(price) / 100, 1) if float(price) % 100 != 0 else int(float(price) / 100)
            for price in strike_prices
        ]

        strike_multiplier = int(setting["strike_price"])
        correct_strike = self.get_correct_strike_price(ltp, ce_pe, strike_prices, strike_multiplier)

        if ce_pe == "CE":
            opt_symbol = f"{index}{expiry}{correct_strike}CE"
        elif ce_pe == "PE":
            opt_symbol = f"{index}{expiry}{correct_strike}PE"

        return opt_symbol

    # ===============================
    # OHLC DATA FETCH
    # ===============================

    def get_todays_ohlc_data_(self, obj, opt_symbol, interval, instrument_list, exchange="NFO", retries=3, delay=1):
        for attempt in range(retries):
            try:
                logger.info(f"[OHLC RETRY] Attempt {attempt + 1}/{retries} for {opt_symbol}")

                wait_time = delay * (attempt + 1)
                logger.info(f"[OHLC RETRY] Sleeping {wait_time} seconds before attempt")
                time.sleep(wait_time)

                if interval == "5" or interval == 5:
                    interval = "FIVE_MINUTE"

                today = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')
                start_time = timezone.localtime(timezone.now()).replace(hour=9, minute=15, second=0, microsecond=0)

                logger.info(f"today======={start_time}")
                seven_days_ago = start_time - timedelta(days=5)
                seven_days_ago = seven_days_ago.strftime('%Y-%m-%d %H:%M')
                logger.info(f"seven_days_ago======= {seven_days_ago}")

                params = {
                    "exchange": exchange,
                    "symboltoken": self.order_manager.token_lookup(opt_symbol, instrument_list, exchange="NFO"),
                    "interval": interval,
                    "fromdate": seven_days_ago,
                    "todate": today
                }

                hist_data = obj.getCandleData(params)

                if hist_data and "data" in hist_data and hist_data["data"]:
                    columns = ["Timestamp", "open", "high", "low", "close", "volume"]
                    df = pd.DataFrame(hist_data["data"], columns=columns)
                    df = df.reset_index(drop=True)

                    if not df.empty:
                        logger.info(f"[OHLC RETRY] Successfully fetched {len(df)} candles for {opt_symbol} on attempt {attempt + 1}")
                        return df
                    else:
                        logger.warning(f"[OHLC RETRY] Attempt {attempt + 1} returned empty DataFrame for {opt_symbol}")
                else:
                    logger.warning(f"[OHLC RETRY] Attempt {attempt + 1} returned no data for {opt_symbol}")

            except Exception as e:
                logger.error(f"[OHLC RETRY] Attempt {attempt + 1} failed with error: {e}")
                logger.error(traceback.format_exc())

        logger.error(f"[OHLC RETRY] All {retries} attempts failed for {opt_symbol}")
        return None

    # ===============================
    # CSV OPERATIONS
    # ===============================

    def mark_stock_inactive_in_sector_csv(self, symbol):
        try:
            csv_path = "sectorwise_stocks_filtered.csv"
            if not os.path.exists(csv_path):
                return
            df = pd.read_csv(csv_path)
            mask = (df["Symbol"] == symbol) & (df["status"] == "ACTIVE")
            if mask.any():
                df.loc[mask, "status"] = "INACTIVE"
                df.to_csv(csv_path, index=False)
                logger.info(f"[SECTOR CSV] Marked {symbol} as INACTIVE")
        except Exception as e:
            logger.error(f"[SECTOR CSV] Failed to mark inactive for {symbol}: {e}")

    def update_csv_with_status(self, csv_path, new_df, cols):
        if new_df.empty:
            logger.warning(f"[WARN] No data to write for {csv_path}")
            return
        try:
            for col in cols:
                if col not in new_df.columns:
                    new_df[col] = ""
            new_df = new_df[cols]

            if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                try:
                    old_df = pd.read_csv(csv_path)
                    if 'status' in old_df.columns:
                        old_df['status'] = 'INACTIVE'
                    final_df = pd.concat([old_df, new_df], ignore_index=True)
                    final_df = final_df.drop_duplicates(
                        subset=[col for col in cols if col != 'status'],
                        keep='last'
                    )
                    final_df.to_csv(csv_path, index=False)
                    logger.info(f"[INFO] Updated {csv_path}")
                except (pd.errors.EmptyDataError, pd.errors.ParserError):
                    new_df.to_csv(csv_path, index=False)
            else:
                new_df.to_csv(csv_path, index=False)
        except Exception as e:
            logger.error(f"[ERROR] Failed to update {csv_path}: {e}")
            traceback.print_exc()

    def save_watchlist_to_csv(self):
        if not self.watchlist:
            return

        today = datetime.now().date()

        headers = [
            'timestamp', 'option_symbol', 'stock_symbol', 'option_type',
            'five_min_high', 'five_min_low', 'five_min_close',
            'five_min_volume', 'avg_volume_20', 'entry_signal',
            'status', 'stoploss'
        ]

        todays_entries = [
            e for e in self.watchlist
            if e["timestamp"].date() == today
        ]

        if not todays_entries:
            self.watchlist.clear()
            return

        if os.path.exists(self.watchlist_csv):
            df = pd.read_csv(self.watchlist_csv)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df[df["timestamp"].dt.date == today]
        else:
            df = pd.DataFrame(columns=headers)

        new_df = pd.DataFrame(todays_entries)
        new_df["timestamp"] = new_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

        final_df = pd.concat([df, new_df], ignore_index=True)
        final_df.to_csv(self.watchlist_csv, index=False)

        logger.info(f"[SAVE] Saved {len(new_df)} entries to watchlist.csv")
        self.watchlist.clear()

    def save_watchlist2_to_csv(self):
        if not self.watchlist2:
            return

        today = datetime.now().date()

        headers = [
            'timestamp', 'option_symbol', 'stock_symbol', 'option_type',
            'five_min_high', 'five_min_low', 'five_min_close',
            'five_min_volume', 'avg_volume_20', 'vwap', 'wma_9', 'entry_signal',
            'status', 'limit_price', 'stoploss'
        ]

        todays_entries = [
            e for e in self.watchlist2
            if e["timestamp"].date() == today
        ]

        if not todays_entries:
            self.watchlist2.clear()
            return

        if os.path.exists(self.watchlist_csv2):
            df = pd.read_csv(self.watchlist_csv2)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df[df["timestamp"].dt.date == today]
        else:
            df = pd.DataFrame(columns=headers)

        new_df = pd.DataFrame(todays_entries)
        new_df["timestamp"] = new_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

        final_df = pd.concat([df, new_df], ignore_index=True)
        final_df.to_csv(self.watchlist_csv2, index=False)

        logger.info(f"[SAVE] Saved {len(new_df)} entries to watchlist2.csv")
        self.watchlist2.clear()

    def deactivate_watchlist1(self):
        logger.info("[RESET W1] Deactivating all Phase 1 watchlist entries")
        if os.path.exists(self.watchlist_csv):
            try:
                df = pd.read_csv(self.watchlist_csv)
                if not df.empty:
                    df['status'] = 'INACTIVE'
                    df.to_csv(self.watchlist_csv, index=False)
                    logger.info(f"[RESET W1] Marked {len(df)} entries in watchlist.csv as INACTIVE")
            except Exception as e:
                logger.error(f"[RESET W1] Error updating watchlist.csv: {e}")
        self.watchlist.clear()

    def deactivate_watchlist2(self):
        logger.info("[RESET W2] Deactivating all Phase 2 watchlist entries")
        if os.path.exists(self.watchlist_csv2):
            try:
                df = pd.read_csv(self.watchlist_csv2)
                if not df.empty:
                    df['status'] = 'INACTIVE'
                    df.to_csv(self.watchlist_csv2, index=False)
                    logger.info(f"[RESET W2] Marked {len(df)} entries in watchlist2.csv as INACTIVE")
            except Exception as e:
                logger.error(f"[RESET W2] Error updating watchlist2.csv: {e}")
        self.watchlist2.clear()

        # Delegate unsubscribe to websocket_manager
        if self.websocket_manager:
            self.websocket_manager.unsubscribe_all()

    # ===============================
    # SECTOR SCAN (NSE API)
    # ===============================

    def run_scrap_sector(self, settings):
        try:
            SECTOR_SCAN_LIMIT = int(settings.get('sectors_scan', 3))
            STOCK_SCAN_LIMIT = int(settings.get('stocks_scan', 3))

            logger.info(f"SECTOR_SCAN_LIMIT : {SECTOR_SCAN_LIMIT} STOCK_SCAN_LIMIT {STOCK_SCAN_LIMIT}")

            self.clean_old_csv_data()

            scan_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[SCAN START] {scan_time}")

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
                "INOXWIND", "MUTHOOTFIN", "PIIND", "ANGELONE", "BSE"
            }

            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": "https://www.nseindia.com/"
            })
            session.get("https://www.nseindia.com")

            url = "https://www.nseindia.com/api/allIndices"
            res = session.get(url).json()

            sectors = []
            for item in res["data"]:
                sector_name = item["index"]
                sector_change = float(item["percentChange"])
                if "NIFTY" not in sector_name:
                    continue
                sectors.append({
                    "scan_time": scan_time,
                    "sector": sector_name,
                    "sector_change": sector_change,
                    "status": "ACTIVE"
                })

            if not sectors:
                logger.warning("[WARNING] No sectors found")
                return

            sectors = sorted(
                sectors,
                key=lambda x: abs(x["sector_change"]),
                reverse=True
            )[:SECTOR_SCAN_LIMIT]

            logger.info(f"[SECTOR] Selected top {len(sectors)} sectors")

            all_stocks = []
            total_stock_tiles_scanned = 0
            total_stock_selected = 0
            total_stock_fno_reject = 0
            total_stock_direction_reject = 0

            for sector in sectors:
                try:
                    sector_name = sector["sector"]
                    api_sector = quote(sector_name)
                    url = f"https://www.nseindia.com/api/equity-stockIndices?index={api_sector}"
                    res = session.get(url).json()
                    stocks = res["data"]

                    for stock in stocks:
                        if stock["symbol"] == sector_name:
                            continue

                        total_stock_tiles_scanned += 1
                        symbol = stock["symbol"].upper()

                        if symbol not in fno_symbols:
                            total_stock_fno_reject += 1
                            continue

                        price = float(stock["lastPrice"])
                        stock_change = float(stock["pChange"])

                        if sector["sector_change"] > 0 and stock_change < 1:
                            total_stock_direction_reject += 1
                            continue

                        if sector["sector_change"] < 0 and stock_change > -1:
                            total_stock_direction_reject += 1
                            continue

                        all_stocks.append({
                            "scan_time": scan_time,
                            "Sector": sector_name,
                            "Sector Change %": sector["sector_change"],
                            "Symbol": symbol,
                            "Price": price,
                            "Stock Change %": stock_change,
                            "status": "ACTIVE"
                        })
                        total_stock_selected += 1

                except Exception as e:
                    logger.error(f"[ERROR] Failed sector {sector['sector']} : {e}")

            if not all_stocks:
                logger.warning("[WARNING] No stocks matched criteria")
                return

            stocks_df = pd.DataFrame(all_stocks)
            filtered_rows = []

            for sector_name, group in stocks_df.groupby("Sector"):
                sector_change = group["Sector Change %"].iloc[0]
                if sector_change > 0:
                    topN = group.sort_values(by="Stock Change %", ascending=False).head(STOCK_SCAN_LIMIT)
                else:
                    topN = group.sort_values(by="Stock Change %", ascending=True).head(STOCK_SCAN_LIMIT)
                filtered_rows.append(topN)

            stocks_df = pd.concat(filtered_rows, ignore_index=True)
            stocks_df["abs_sector"] = stocks_df["Sector Change %"].abs()
            stocks_df["abs_stock"] = stocks_df["Stock Change %"].abs()
            stocks_df = stocks_df.sort_values(
                by=["abs_sector", "abs_stock"],
                ascending=[False, False]
            ).drop(columns=["abs_sector", "abs_stock"])
            stocks_df = stocks_df.drop_duplicates(subset=["Symbol"], keep="first")

            self.update_csv_with_status(
                "sectors_filtered.csv",
                pd.DataFrame(sectors),
                ["scan_time", "sector", "sector_change", "status"]
            )
            self.update_csv_with_status(
                "sectorwise_stocks_filtered.csv",
                stocks_df,
                ["scan_time", "Sector", "Sector Change %", "Symbol", "Price", "Stock Change %", "status"]
            )

            logger.info(f"[STOCK] Total scanned: {total_stock_tiles_scanned}")
            logger.info(f"[STOCK] FNO rejected: {total_stock_fno_reject}")
            logger.info(f"[STOCK] Direction rejected: {total_stock_direction_reject}")
            logger.info(f"[STOCK] Final selected: {total_stock_selected}")
            logger.info(f"[SCAN COMPLETE] {scan_time}")

        except Exception as e:
            logger.error(f"[FATAL ERROR] {str(e)}")
            traceback.print_exc()

    # ===============================
    # SCHEDULER LOOP
    # ===============================

    def scheduler_loop(self, angel, settings, user_profile):
        # Wait until 09:20
        while not self.stop_event.is_set():
            now = datetime.now(IST)
            if now.hour >= 9 and (now.hour > 9 or now.minute >= 20):
                break
            time.sleep(5)

        if self.stop_event.is_set():
            logger.info("[SCHEDULER] Received stop signal, exiting scheduler loop")
            return

        monitoring_start = datetime.now(IST)
        monitoring_end = monitoring_start.replace(hour=9, minute=30, second=0, microsecond=0)
        now = datetime.now(IST)

        if now.hour == 9 and (20 <= now.minute < 30):
            logger.info("[SCHEDULER] Running initial 09:20 scan")
            self.run_phase1(angel, settings)
        else:
            logger.info("[SCHEDULER] Skipping Phase-1 (outside 09:20–09:30), started phase 2 scanning")
            self.run_phase2(angel, settings, user_profile)

        while datetime.now(IST) < monitoring_end and not self.stop_event.is_set():
            now = datetime.now(IST)
            if now.second == 0:
                logger.info(f"[MONITOR] Processing {now.strftime('%H:%M')}")
                self.check_entry_signals(angel, settings, now, user_profile)

                next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
                sleep_seconds = (next_minute - datetime.now(IST)).total_seconds()

                for _ in range(int(sleep_seconds * 2)):
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.5)
            else:
                time.sleep(0.5)
                if self.stop_event.is_set():
                    break

        if not self.stop_event.is_set():
            logger.info("[SCHEDULER] PHASE 1 Complete. Starting 15-minute interval scans")
            self.run_phase2(angel, settings, user_profile)
        else:
            logger.info("[SCHEDULER] Stop signal received, exiting scheduler")

    # ===============================
    # PHASE 1
    # ===============================

    def run_phase1(self, angel, settings):
        try:
            logger.info("[PHASE-1] Started")

            while True:
                scan_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"[PHASE-1] Running sector scan at {scan_time}")

                self.run_scrap_sector(settings)
                self.deactivate_watchlist1()

                try:
                    all_stocks = pd.read_csv("sectorwise_stocks_filtered.csv")
                except Exception:
                    all_stocks = pd.DataFrame()

                if not all_stocks.empty:
                    logger.info(f"[PHASE-1] Stocks found: {len(all_stocks)}")
                    break

                logger.warning("[PHASE-1] No stocks found. Retrying sector scan...")
                time.sleep(3)

            self.process_stocks_for_monitoring(angel, settings, all_stocks)
            logger.info(f"[PHASE-1 DONE] Rows processed: {len(all_stocks)}")
            logger.info(f"[PHASE-1] Watchlist size: {len(self.watchlist)}")

        except Exception as e:
            logger.error(f"[ERROR] Phase-1 failed: {e}")

    def process_stocks_for_monitoring(self, angel, settings, stocks_data):
        logger.info(f"[PROCESSING] Analyzing {len(stocks_data)} stocks for monitoring")

        if self.trades_today >= self.max_trades_per_day:
            logger.info(f"[PROCESSING] Skipping Phase 1 - Already executed {self.trades_today}/{self.max_trades_per_day} trades today")
            return

        instrument_list = self.order_manager.instrument_list
        symboldf = self.order_manager.symboldf

        for _, stock in stocks_data.iterrows():
            if stock["status"] != "ACTIVE":
                continue

            symbol = stock["Symbol"]
            option_type = "CE" if float(stock["Stock Change %"]) > 0 else "PE"

            option_symbol = self.angel_fetch_symbol(angel, symbol, symbol, option_type, settings, instrument_list, symboldf)
            if not option_symbol:
                continue

            logger.info(f"[DATA] Fetching 09:20 candle for {option_symbol}")
            candle_data = self.get_todays_ohlc_data_(angel, option_symbol, interval="5", instrument_list=instrument_list, exchange="NFO", retries=3, delay=1)

            if candle_data is None or candle_data.empty:
                logger.info(f"[SKIP] No candle data for {option_symbol}")
                continue

            candle_data['Timestamp'] = pd.to_datetime(candle_data['Timestamp'])
            today_date = candle_data['Timestamp'].dt.date.max()
            today_candles = candle_data[candle_data['Timestamp'].dt.date == today_date]
            candle_data = candle_data.sort_values('Timestamp')

            previous_trading_candles = candle_data[candle_data['Timestamp'].dt.date < today_date]
            if previous_trading_candles.empty:
                logger.info(f"[SKIP] No previous trading day data for {option_symbol}")
                continue

            last_trade_day = previous_trading_candles['Timestamp'].dt.date.max()
            last_day_candles = previous_trading_candles[
                previous_trading_candles['Timestamp'].dt.date == last_trade_day
            ]
            if last_day_candles.empty:
                logger.info(f"[SKIP] No last day candles found for {symbol}")
                continue

            prev_day_high = last_day_candles['high'].max()

            candle_0920 = today_candles[
                today_candles['Timestamp'].dt.time == pd.to_datetime("09:20").time()
            ]
            if candle_0920.empty:
                logger.info(f"[SKIP] 09:20 candle not found for {option_symbol}")
                continue

            pre_0920_candles = today_candles[
                today_candles['Timestamp'].dt.time < pd.to_datetime("09:20").time()
            ]
            logger.info(f"pre_0920_candles {pre_0920_candles}")

            if pre_0920_candles.empty:
                logger.info(f"[SKIP] No previous 5-min candle before 09:20 for {option_symbol}")
                continue

            latest_5min_candle = pre_0920_candles.iloc[-1]
            latest_5min_close = latest_5min_candle['close']
            latest_5min_open = latest_5min_candle['open']
            logger.info(f"open {latest_5min_open} close {latest_5min_close}")

            if prev_day_high >= latest_5min_open:
                logger.info(f"[SKIP] {symbol}: Prev Day High {prev_day_high} >= Latest 5-min open {latest_5min_open}")
                continue

            if len(candle_data) >= 20:
                avg_volume = np.mean(candle_data[-20:]['volume'])
            else:
                avg_volume = np.mean(candle_data['volume'])

            final_volume = float(settings['volume_multiplier']) * avg_volume

            if latest_5min_candle['volume'] < final_volume:
                logger.info(f"[SKIP] {symbol}: Volume {latest_5min_candle['volume']} < {settings['volume_multiplier']}x avg volume {final_volume}")
                continue

            if latest_5min_open > latest_5min_close:
                logger.info(f"[SKIP] {symbol}: open {latest_5min_open} > close {latest_5min_close}")
                continue

            watchlist_entry = {
                'timestamp': datetime.now(IST),
                'option_symbol': option_symbol,
                'stock_symbol': symbol,
                'option_type': option_type,
                'five_min_high': latest_5min_candle['high'],
                'five_min_low': latest_5min_candle['low'],
                'five_min_close': latest_5min_candle['close'],
                'five_min_volume': latest_5min_candle['volume'],
                'avg_volume_20': avg_volume,
                'entry_signal': False,
                'status': 'ACTIVE',
                'stoploss': latest_5min_candle['low']
            }

            self.watchlist.append(watchlist_entry)
            logger.info(f"Volume {latest_5min_candle['volume']} {settings['volume_multiplier']}X Avg Volume {final_volume}")
            logger.info(f"prev_day_high {prev_day_high} latest_5min_open {latest_5min_open}")
            logger.info(f"latest_5min_open {latest_5min_open} latest_5min_close {latest_5min_close}")
            logger.info(f"[WATCHLIST] Added {option_symbol} to monitoring watchlist")
            logger.info(f"[WATCHLIST] Total stocks in watchlist: {len(self.watchlist)}")
            self.save_watchlist_to_csv()

    # ===============================
    # PHASE 1 - ENTRY SIGNAL CHECK
    # ===============================

    def check_entry_signals(self, angel, settings, current_time, user_profile):
        if self.trades_today >= self.max_trades_per_day:
            logger.info(f"[SIGNAL CHECK] Skipping - Already executed {self.trades_today}/{self.max_trades_per_day} trades today")
            return

        logger.info(f"[SIGNAL CHECK] Checking entry signals at {current_time.strftime('%H:%M:%S')}")

        watchlist_df = pd.read_csv("watchlist.csv")
        updated_entries = []

        instrument_list = self.order_manager.instrument_list

        for index, entry in watchlist_df.iterrows():
            if entry['status'] != 'ACTIVE' or entry['entry_signal']:
                continue

            option_symbol = entry['option_symbol']
            logger.info(f"[CHECK] Analyzing {option_symbol} for entry signal")

            one_min_data = self.get_todays_ohlc_data_(angel, option_symbol, interval="ONE_MINUTE", instrument_list=instrument_list, exchange="NFO")

            if one_min_data is None or len(one_min_data) == 0:
                continue

            latest_1min = one_min_data.iloc[-1] if isinstance(one_min_data, pd.DataFrame) else one_min_data[-1]
            logger.info(f"Latest 1-min candle: {latest_1min}")
            entry_signal_triggered = False

            latest_candle_time = latest_1min.get('Timestamp', 'NA')

            if latest_1min['close'] > entry['five_min_high']:
                logger.info(
                    f"[SIGNAL] ENTRY SIGNAL for {option_symbol} | "
                    f"Candle Time: {latest_candle_time} | "
                    f"Check Time: {current_time.strftime('%H:%M:%S')}"
                )
                logger.info(
                    f"[SIGNAL] 1-min close: {latest_1min['close']} > "
                    f"5-min high: {entry['five_min_high']} | "
                    f"Candle Time: {latest_candle_time}"
                )
                entry_signal_triggered = True

            if entry_signal_triggered:
                result = self.order_manager.execute_trade(angel, settings, entry, user_profile)

                if isinstance(result, tuple):
                    trade_success, limit_price = result
                else:
                    trade_success = result
                    limit_price = 0

                watchlist_df.at[index, 'entry_signal'] = True
                watchlist_df.at[index, 'status'] = 'INACTIVE'
                watchlist_df.at[index, 'entry_time'] = current_time.strftime('%Y-%m-%d %H:%M:%S')
                watchlist_df.at[index, 'entry_price'] = latest_1min['close']

                updated_entries.append(watchlist_df.iloc[index])
            else:
                logger.info(f"[SKIP] latest_1min['close'] {latest_1min['close']} < five_min_high {entry['five_min_high']}")

        if updated_entries:
            watchlist_df.to_csv("watchlist.csv", index=False)
            logger.info(f"[UPDATE] Updated {len(updated_entries)} entries in watchlist CSV")

    # ===============================
    # PHASE 2
    # ===============================

    def run_phase2(self, angel, settings, user_profile):
        logger.info("[PHASE2] Starting Phase 2 main loop")

        # Start WebSocket once via websocket_manager
        if not hasattr(self, "ws_started"):
            if self.websocket_manager:
                self.websocket_manager.start(
                    angel=angel,
                    settings=settings,
                    user_profile=user_profile,
                    order_manager=self.order_manager,
                    strategy=self
                )
            self.ws_started = True

        market_close = datetime.now(IST).replace(hour=15, minute=30, second=0, microsecond=0)
        self.processing_active = False
        self.current_process_thread = None
        self.stop_processing = False

        while datetime.now(IST) < market_close and not (self.stop_event and self.stop_event.is_set()):
            now = datetime.now(IST)

            if self.stop_event and self.stop_event.is_set():
                logger.info("[PHASE2] Stop signal received, exiting main loop")
                break

            # 15-MIN SECTOR SCAN
            if now.minute in [0, 10, 15, 20, 30, 45] and now.second == 0:
                logger.info("[PHASE2] New sector cycle resetting websocket tracking")

                if self.websocket_manager:
                    self.websocket_manager.reset_ltp_tracking()

                if self.stop_event and self.stop_event.is_set():
                    break

                logger.info(f"[PHASE2] {now.strftime('%H:%M')} - Running sector scan")

                retry_count = 0
                while retry_count < 3 and not (self.stop_event and self.stop_event.is_set()):
                    self.run_scrap_sector(settings)
                    self.deactivate_watchlist2()

                    try:
                        df = pd.read_csv("sectorwise_stocks_filtered.csv")
                        if not df.empty:
                            break
                        else:
                            logger.warning("[PHASE2] Empty sector data frame")
                    except Exception as e:
                        logger.error(f"[PHASE2] Error reading sector data: {e}")

                    logger.warning(f"[PHASE2] Empty sector data. Retrying... ({retry_count + 1}/3)")
                    retry_count += 1

                    for _ in range(6):
                        if self.stop_event and self.stop_event.is_set():
                            break
                        time.sleep(0.5)

            # 5-MIN PROCESSING
            if now.minute % 5 == 0 and now.second == 0:
                if self.stop_event and self.stop_event.is_set():
                    break

                if self.processing_active and self.current_process_thread:
                    self.stop_processing = True
                    timeout = 5
                    start_time = time.time()
                    while self.current_process_thread.is_alive() and (time.time() - start_time) < timeout:
                        if self.stop_event and self.stop_event.is_set():
                            break
                        time.sleep(0.1)

                    if self.current_process_thread.is_alive():
                        logger.warning("[PHASE2] Previous processing thread still alive, continuing...")

                logger.info(f"[PHASE2] Processing interval {now.strftime('%H:%M')}")

                self.processing_active = True
                self.stop_processing = False

                self.current_process_thread = threading.Thread(
                    target=self.process_interval_with_timeout,
                    args=(angel, settings, now, user_profile),
                    daemon=True
                )
                self.current_process_thread.start()

                timeout_seconds = 240
                check_interval = 1

                for _ in range(timeout_seconds):
                    if not self.current_process_thread.is_alive():
                        break
                    if self.stop_event and self.stop_event.is_set():
                        logger.info("[PHASE2] Stop signal received while waiting for processing")
                        self.stop_processing = True
                        break
                    time.sleep(check_interval)

                if self.current_process_thread.is_alive():
                    logger.warning("[PHASE2] Interval processing timeout")
                    self.stop_processing = True
                    time.sleep(2)

                self.processing_active = False
                self.current_process_thread = None

                for _ in range(2):
                    if self.stop_event and self.stop_event.is_set():
                        break
                    time.sleep(1)

            else:
                for _ in range(2):
                    if self.stop_event and self.stop_event.is_set():
                        break
                    time.sleep(0.5)

        if self.processing_active and self.current_process_thread and self.current_process_thread.is_alive():
            logger.info("[PHASE2] Stopping processing thread on exit")
            self.stop_processing = True
            time.sleep(2)

        logger.info("[PHASE2] Market closed or stopped.")

    def process_interval_with_timeout(self, angel, settings, current_time, user_profile):
        try:
            logger.info(f"[INTERVAL] Starting interval processing for {current_time.strftime('%H:%M')}")

            if self.trades_today >= self.max_trades_per_day:
                logger.info(f"[INTERVAL] Skipping - Already executed {self.trades_today}/{self.max_trades_per_day} trades today")
                return

            stocks_df = pd.read_csv("sectorwise_stocks_filtered.csv")
            active_stocks = stocks_df[stocks_df["status"] == "ACTIVE"]

            if active_stocks.empty:
                logger.info("[INTERVAL] No active stocks to process")
                return

            logger.info(f"[INTERVAL] Processing {len(active_stocks)} active stocks")

            for idx, stock in active_stocks.iterrows():
                if getattr(self, 'stop_processing', False):
                    logger.info(f"[INTERVAL] Processing stopped by flag")
                    return
                self.process_stock_for_phase2(angel, settings, stock, current_time, user_profile)

            logger.info(f"[INTERVAL] Completed processing for {current_time.strftime('%H:%M')}")

        except Exception as e:
            logger.error(f"[INTERVAL] Error processing interval: {e}")

    def process_stock_for_phase2(self, angel, settings, stock, current_time, user_profile):
        if self.trades_today >= self.max_trades_per_day:
            logger.info(f"[PHASE 2] Skipping {stock['Symbol']} - trade limit reached")
            return

        symbol = stock["Symbol"]
        option_type = "CE" if float(stock["Stock Change %"]) > 0 else "PE"

        instrument_list = self.order_manager.instrument_list
        symboldf = self.order_manager.symboldf

        option_symbol = self.angel_fetch_symbol(angel, symbol, symbol, option_type, settings, instrument_list, symboldf)
        if not option_symbol:
            logger.info(f"[PHASE 2] No option symbol for {symbol}")
            return

        if os.path.exists(self.watchlist_csv2):
            watchlist2_df = pd.read_csv(self.watchlist_csv2)
            existing_entry = watchlist2_df[
                (watchlist2_df["stock_symbol"] == symbol) &
                (watchlist2_df["status"] == "ACTIVE") &
                (pd.to_datetime(watchlist2_df["timestamp"]).dt.date == current_time.date())
            ]
            if not existing_entry.empty:
                logger.info(f"[PHASE 2] {symbol} already in active watchlist2")
                return

        candle_data = self.get_todays_ohlc_data_(angel, option_symbol, interval="5", instrument_list=instrument_list, exchange="NFO", retries=3, delay=1)
        if candle_data is None or candle_data.empty:
            logger.info(f"[PHASE 2] No candle data for {option_symbol}")
            return

        candle_data['Timestamp'] = pd.to_datetime(candle_data['Timestamp'])
        candle_data = candle_data.sort_values('Timestamp')

        today_date = current_time.date()
        today_candles = candle_data[candle_data['Timestamp'].dt.date == today_date]

        if today_candles.empty:
            logger.info(f"[PHASE 2] No candles for today {today_date}")
            return

        previous_trading_candles = candle_data[candle_data['Timestamp'].dt.date < today_date]
        if previous_trading_candles.empty:
            logger.info(f"[SKIP] No previous trading day data for {option_symbol}")
            return

        last_trade_day = previous_trading_candles['Timestamp'].dt.date.max()
        last_day_candles = previous_trading_candles[
            previous_trading_candles['Timestamp'].dt.date == last_trade_day
        ]
        if last_day_candles.empty:
            logger.info(f"[SKIP] No last day candles found for {symbol}")
            return

        prev_day_high = last_day_candles['high'].max()

        target_time = current_time.replace(second=0, microsecond=0) - timedelta(minutes=5)
        logger.info(f"Looking for candle at: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")

        current_candle = today_candles[today_candles['Timestamp'] == target_time]
        if current_candle.empty:
            logger.info(f"[PHASE 2] No 5-min candle found for {target_time.strftime('%H:%M')}")
            return

        logger.info(f"current_candle {option_symbol}: {current_candle}")
        latest_candle = current_candle.iloc[0]
        current_candle_timestamp = latest_candle['Timestamp']

        # ---- Volume calculation ----
        all_candle_data = candle_data.sort_values('Timestamp')
        candles_up_to_current = all_candle_data[all_candle_data['Timestamp'] <= current_candle_timestamp]

        if len(candles_up_to_current) >= 20:
            recent_20_candles = candles_up_to_current.tail(20)
        else:
            recent_20_candles = candles_up_to_current

        avg_volume = round(recent_20_candles['volume'].mean())
        final_volume = float(settings['volume_multiplier']) * avg_volume

        logger.info(f"volume_multiplier {settings['volume_multiplier']} : Avg Volume (20 candles): {avg_volume} : Final Volume {final_volume}")

        if latest_candle['volume'] <= final_volume:
            logger.info(f"[PHASE 2] Condition 2 FAILED early: {symbol} Volume {latest_candle['volume']} <= {settings['volume_multiplier']} x Avg Volume: {final_volume}")
            return

        # ---- VWAP & WMA calculation ----
        today_candles_vwap = today_candles[today_candles['Timestamp'] <= current_candle_timestamp].copy()

        if len(today_candles_vwap) < 1:
            logger.info(f"[PHASE 2] Insufficient data for VWAP calculation for {symbol}")
            return

        today_candles_vwap = today_candles_vwap.set_index('Timestamp')
        today_candles_vwap = today_candles_vwap.sort_index()

        try:
            vwap_result = pd_ta.vwap(
                high=today_candles_vwap['high'],
                low=today_candles_vwap['low'],
                close=today_candles_vwap['close'],
                volume=today_candles_vwap['volume']
            )
            today_candles_vwap['vwap'] = vwap_result

            needed_for_wma = 9
            today_count = len(today_candles_vwap)
            extra_needed = needed_for_wma - today_count

            if extra_needed > 0:
                if not last_day_candles.empty:
                    last_day_candles_sorted = last_day_candles.sort_values('Timestamp')
                    available_prev = len(last_day_candles_sorted)
                    take_from_prev = min(extra_needed, available_prev)

                    if take_from_prev > 0:
                        prev_candles = last_day_candles_sorted.tail(take_from_prev).copy()
                        prev_candles.set_index('Timestamp', inplace=True)
                        combined_candles = pd.concat([prev_candles, today_candles_vwap])
                        used_prev = take_from_prev
                    else:
                        combined_candles = today_candles_vwap
                        used_prev = 0
                else:
                    combined_candles = today_candles_vwap
                    used_prev = 0
            else:
                combined_candles = today_candles_vwap
                used_prev = 0

            if len(combined_candles) >= needed_for_wma:
                wma_series = pd_ta.wma(combined_candles['close'], length=needed_for_wma)
                current_wma = round(wma_series.iloc[-1], 2) if not pd.isna(wma_series.iloc[-1]) else None
                logger.info(f"WMA(9) used {used_prev} candles from previous day, {today_count} from today")
            else:
                current_wma = None
                logger.info(f"Insufficient total candles for WMA(9): only {len(combined_candles)} available (needed 9)")

            if current_candle_timestamp in today_candles_vwap.index:
                current_vwap = round(today_candles_vwap.loc[current_candle_timestamp, 'vwap'], 2) if not pd.isna(today_candles_vwap.loc[current_candle_timestamp, 'vwap']) else None
            else:
                current_vwap = None

        except Exception as e:
            logger.error(f"Error calculating VWAP/WMA: {e}")
            return

        # ---- Log all condition values ----
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Option Symbol: {option_symbol}")
        logger.info(f"Total candles today: {len(today_candles)}")
        logger.info(f"Candle time: {current_candle_timestamp}")
        logger.info(f"OHLC: {latest_candle['open']}/{latest_candle['high']}/{latest_candle['low']}/{latest_candle['close']}")
        logger.info(f"Volume: {latest_candle['volume']}")
        logger.info(f"Prev Day High: {prev_day_high}")
        logger.info(f"Calculated VWAP: {current_vwap}")
        logger.info(f"Calculated WMA(9): {current_wma}")

        # ---- Conditions ----
        logger.info(f"Condition 1: Previous day high < 5-min open: {prev_day_high} < {latest_candle['open']}")
        logger.info(f"Condition 2: Volume > {settings['volume_multiplier']}x avg volume: {latest_candle['volume']} > {final_volume}")
        logger.info(f"Condition 3: open <= close: {latest_candle['open']} <= {latest_candle['close']}")
        logger.info(f"Condition 4: Close > VWAP: {latest_candle['close']} > {current_vwap}")
        logger.info(f"Condition 5: Close > WMA(9): {latest_candle['close']} > {current_wma}")
        logger.info(f"Condition 6: VWAP < WMA(9): {current_vwap} < {current_wma}")

        condition1 = prev_day_high < latest_candle['open']
        condition2 = latest_candle['volume'] > final_volume
        condition3 = latest_candle['open'] <= latest_candle['close']
        condition4 = current_vwap is not None and latest_candle['close'] > current_vwap
        condition5 = current_wma is not None and latest_candle['close'] > current_wma
        condition6 = current_wma is not None and current_vwap < current_wma

        if not condition1:
            logger.info(f"[PHASE 2] Condition 1 FAILED: {symbol} PDH {prev_day_high} >= Open {latest_candle['open']}")
            return
        if not condition2:
            logger.info(f"[PHASE 2] Condition 2 FAILED: Volume check failed")
            return
        if not condition3:
            logger.info(f"[PHASE 2] Condition 3 Green Candle FAILED")
            return
        if not condition4:
            logger.info(f"[PHASE 2] Condition 4 FAILED: Close {latest_candle['close']} <= VWAP {current_vwap}")
            return
        if not condition5:
            logger.info(f"[PHASE 2] Condition 5 FAILED: Close {latest_candle['close']} <= WMA(9) {current_wma}")
            return
        if not condition6:
            logger.info(f"[PHASE 2] Condition 6 FAILED: VWAP {current_vwap} >= WMA(9) {current_wma}")
            return

        logger.info(f"[PHASE 2] ALL CONDITIONS MET for {symbol} at {current_time.strftime('%H:%M')}")

        limit_multiplier = float(settings.get('limit_multiplier', 1.0))
        five_min_high = float(latest_candle['high'])
        limit_price = round(five_min_high * limit_multiplier, 2)
        logger.info(f"limit_multiplier : {limit_multiplier} | five_min_high : {five_min_high} | limit_price : {limit_price}")

        today_dt = timezone.localtime(timezone.now())
        watchlist_entry = {
            'timestamp': today_dt,
            'option_symbol': option_symbol,
            'stock_symbol': symbol,
            'option_type': option_type,
            'five_min_high': latest_candle['high'],
            'five_min_low': latest_candle['low'],
            'five_min_open': latest_candle['open'],
            'five_min_close': latest_candle['close'],
            'five_min_volume': latest_candle['volume'],
            'avg_volume_20': avg_volume,
            'vwap': current_vwap,
            'wma_9': current_wma,
            'prev_day_high': prev_day_high,
            'entry_signal': True,
            'status': 'ACTIVE',
            'limit_price': limit_price,
            'stoploss': latest_candle['low']
        }

        self.watchlist2.append(watchlist_entry)
        logger.info(f"Added to watchlist2: {watchlist_entry}")
        logger.info(f"[WATCHLIST2] Added {option_symbol} for LTP monitoring at {limit_price}")
        self.save_watchlist2_to_csv()

        # Delegate websocket subscription
        if self.websocket_manager:
            self.websocket_manager.subscribe_token(
                symbol=option_symbol,
                limit_price=limit_price,
                row_data=watchlist_entry,
                instrument_list=instrument_list
            )

    # ===============================
    # TRADE COUNTER UPDATE (called by order_manager callback)
    # ===============================

    def increment_trade_count(self):
        self.trades_today += 1
        logger.info(f"[TRADE COUNT UPDATED] {self.trades_today}/{self.max_trades_per_day}")
