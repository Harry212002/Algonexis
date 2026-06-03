"""
order_manager.py
----------------
Handles all order placement, symbol resolution, expiry calculation,
strike selection, target/stoploss calculation, and DB saving.

Extracted from angel_one_apis.py and strategy_files.py.
All original calculations preserved exactly.
"""

import json
import logging
import time
import traceback
import urllib
import pandas as pd
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger('strategy_log')

# -----------------------------------------------------------------------
# Rate-limit guard (same constant as original)
# -----------------------------------------------------------------------
max_requests_per_minute = 100
delay_between_requests = 80 / max_requests_per_minute


class OrderManager:
    """
    Manages all order-related operations for SectorMomentumBreakoutStrategy.

    Usage:
        om = OrderManager()
        om.place_order(...)
        om.execute_trade(...)
    """

    def __init__(self):
        instrument_url = (
            "https://margincalculator.angelbroking.com"
            "/OpenAPI_File/files/OpenAPIScripMaster.json"
        )
        response = urllib.request.urlopen(instrument_url)
        import json as _json
        self.instrument_list = _json.loads(response.read())
        self.symboldf = pd.DataFrame(self.instrument_list)
        logger.info("[ORDER MANAGER] Instrument list loaded")

    # ===============================
    # TOKEN / LOT SIZE LOOKUP
    # ===============================

    def token_lookup(self, ticker, instrument_list, exchange="NSE"):
        logger.debug(f"token_lookup ticker={ticker} exchange={exchange}")
        for instrument in instrument_list:
            if (
                instrument["name"] == ticker
                and instrument["exch_seg"] == exchange
                and instrument["symbol"].split('-')[-1] == "EQ"
            ):
                return instrument["token"]
            elif instrument["symbol"] == ticker and instrument["exch_seg"] == exchange:
                return instrument["token"]
        return None

    def lot_size_lookup(self, symbol, instrument_list, exchange="NSE"):
        logger.debug(f"lot_size_lookup symbol={symbol} exchange={exchange}")
        for instrument in instrument_list:
            if (
                instrument["symbol"] == symbol
                and instrument["exch_seg"] == exchange
                and instrument["symbol"].split('-')[-1] == "EQ"
            ):
                return instrument["lotsize"]
            elif instrument["symbol"] == symbol and instrument["exch_seg"] == exchange:
                return instrument["lotsize"]
        return None

    # ===============================
    # LTP
    # ===============================

    def get_ltp(self, obj, instrument_list, ticker, exchange="NFO"):
        params = {
            "exchange": exchange,
            "tradingsymbol": ticker,
            "symboltoken": self.token_lookup(ticker, instrument_list, exchange=exchange)
        }
        response = obj.ltpData(params["exchange"], params["tradingsymbol"], params["symboltoken"])
        return response

    def get_option_ltp(self, exchange, angel, tradingsymbol):
        token = self.token_lookup(tradingsymbol, self.instrument_list, exchange)
        if not token:
            logger.error(f"Token not found for {tradingsymbol}")
            return None
        try:
            LTP = angel.ltpData(exchange, tradingsymbol, token)
        except Exception as e:
            logger.error(f"Angel One empty response for {tradingsymbol}: {e}")
            return None
        if not LTP or not LTP.get("status"):
            logger.error(f"LTP failed for {tradingsymbol}: {LTP}")
            return None
        data = LTP.get("data")
        if not data:
            logger.error(f"LTP data empty for {tradingsymbol}")
            return None
        return data.get("ltp")

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

    def getExpiryDateFut(self, index, setting):
        symboldataframe = self.symboldf.copy()
        df = symboldataframe[self.symboldf.name == index].copy()
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

        return expiry_dates[0] if len(expiry_dates) > 0 else None

    def get_monthly_expiry_fut(self, index, setting):
        expiry_date = self.getExpiryDateFut(index, setting)
        formatted_expiry = expiry_date.strftime('%d%b%y').upper()
        return formatted_expiry

    def get_inst_fut(self, index, setting):
        expiry_code = self.get_monthly_expiry_fut(index, setting)
        formatted_expiry = expiry_code[:-2] + expiry_code[-2:]
        return formatted_expiry

    # ===============================
    # STRIKE CALCULATION
    # ===============================

    def get_correct_strike_price(self, ltp, ce_pe, strike_prices, strike_multiplier):
        """
        Exact original logic preserved.
        """
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

    def calculate_strike(self, ltp, ce_pe, index, setting):
        """
        Calculate the option symbol given LTP, option type, index, and setting.
        Exact original logic.
        """
        expiry = self.get_inst_fut(index, setting)
        expiry = expiry.upper()

        filtered_data = self.symboldf[
            (self.symboldf["name"] == index) &
            (self.symboldf["instrumenttype"] == "OPTSTK")
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
        else:
            opt_symbol = None

        return opt_symbol

    # ===============================
    # QUANTITY CALCULATION
    # ===============================

    def calculate_quantity(self, option_symbol, per_trade_allocation, ltp):
        """
        Calculate number of lots based on per-trade fund allocation and LTP.
        Exact original logic.
        """
        lot_size = int(self.lot_size_lookup(option_symbol, self.instrument_list, exchange="NFO"))
        if not lot_size or lot_size <= 0:
            logger.error(f"[QTY] Invalid lot size for {option_symbol}: {lot_size}")
            return None, None

        cost_per_lot = ltp * lot_size
        max_lots = int(per_trade_allocation // cost_per_lot)

        if max_lots <= 0:
            logger.error(f"[QTY] Cannot afford even 1 lot. Cost per lot: {cost_per_lot}, Per trade: {per_trade_allocation}")
            return None, None

        qty = int(lot_size) * max_lots
        return max_lots, qty

    # ===============================
    # TARGET / STOPLOSS CALCULATION
    # ===============================

    def calculate_target(self, limit_price, target_pct):
        """target_pct is percentage e.g. 5 means 5%"""
        return limit_price * target_pct / 100

    def calculate_stoploss(self, limit_price, stoploss_pct, candle_low):
        """
        Exact original logic:
        stoploss = min(calculated_stoploss, original_stoploss)
        """
        calculated_stoploss = limit_price * stoploss_pct / 100
        original_stoploss = abs(limit_price - candle_low)
        stoploss = min(calculated_stoploss, original_stoploss)
        if stoploss <= 0:
            stoploss = 0.1
        return stoploss

    # ===============================
    # ORDER VALIDATION
    # ===============================

    def validate_order(self, angel, order_id, symbol):
        """
        Validate order via orderbook after placement.
        Exact original logic.
        """
        try:
            orderbook = angel.orderBook()
            time.sleep(delay_between_requests)
            if not orderbook.get("status"):
                return False

            orders = orderbook.get("data", [])
            for order in orders:
                if order.get("orderid") == order_id:
                    status = order.get("orderstatus", "").lower()
                    logger.info(f"[ORDER STATUS] OrderID={order_id} symbol={symbol} Status={status}")
                    if status in ["complete", "open", "trigger pending"]:
                        return True
                    else:
                        return False
            return False
        except Exception as e:
            logger.error(f"[ORDER CHECK ERROR] {e}")
            return False

    # ===============================
    # SAVE ORDER TO DB
    # ===============================

    def save_order(self, user_profile, params, response_data, order_id, qty,
                   option_symbol, stock_symbol, stoploss, squareoff,
                   transaction_type, settings, entry_price, message=""):
        """
        Save OptionOrder to database.
        Exact original field mapping preserved.
        """
        from .models import OptionOrder  # adjust to your app path

        try:
            order_record = OptionOrder(
                user=user_profile,
                qty=qty,
                symbol=stock_symbol,
                ordertype="ROBO",
                side=1 if transaction_type == "BUY" else -1,
                productType="BO",
                stopLoss=stoploss,
                takeProfit=squareoff,
                action=transaction_type,
                type_of_stock="OPTION",
                broker="angelone",
                time_frame=int(settings.get("time_frame", 1)),
                strategy_name=settings.get("strategy_name", "Sector Momentum Breakout"),
                active=True,
                order_details=json.dumps(params),
                api_response=json.dumps(response_data),
                order_id=order_id,
                full_symbol=option_symbol,
                entry_price=entry_price,
                message=message,
                time=timezone.localtime(timezone.now())
            )
            order_record.save()
            logger.info(f"[DB SAVE] Order saved for {option_symbol}")
            return order_record
        except Exception as e:
            logger.error(f"[DB ERROR] Failed to save order for {option_symbol}: {str(e)}")
            return None

    def save_rejected_order(self, user_profile, params, response_data,
                            option_symbol, stock_symbol, stoploss, squareoff,
                            transaction_type, settings,entry_price, reject_msg=""):
        """
        Save rejected OptionOrder to DB for audit trail.
        """
        from .models import OptionOrder  # adjust to your app path

        try:
            order_record = OptionOrder(
                user=user_profile,
                qty=0,
                symbol=stock_symbol,
                ordertype="ROBO",
                side=1,
                productType="BO",
                stopLoss=0,
                takeProfit=0,
                action=transaction_type,
                type_of_stock="OPTION",
                broker="angelone",
                time_frame=int(settings.get("time_frame", 1)),
                strategy_name=settings.get("strategy_name", "Sector Momentum Breakout"),
                active=False,
                order_details=json.dumps(params),
                api_response=json.dumps(response_data),
                order_id="REJECTED",
                full_symbol=option_symbol,
                entry_price=entry_price,
                message=reject_msg,
                time=timezone.localtime(timezone.now())
            )
            order_record.save()
            logger.info(f"[DB SAVE] Rejected order saved for {option_symbol}")
        except Exception as e:
            logger.error(f"[DB ERROR] Failed to save rejected order: {e}")

    # ===============================
    # PLACE ROBO ORDER
    # ===============================

    def place_robo_order(self, angel, option_symbol, qty, limit_price,
                         squareoff, stoploss, transaction_type="BUY"):
        """
        Place a ROBO (Bracket Order) via Angel One API.
        Exact original params structure preserved.
        """
        order_params = {
            "variety": "ROBO",
            "tradingsymbol": option_symbol,
            "symboltoken": self.token_lookup(option_symbol, self.instrument_list, exchange="NFO"),
            "transactiontype": transaction_type,
            "exchange": "NFO",
            "ordertype": "LIMIT",
            "producttype": "BO",
            "duration": "DAY",
            "quantity": qty,
            "price": limit_price,
            "squareoff": round(abs(squareoff), 2),
            "stoploss": round(abs(stoploss), 2),
            "trailingStopLoss": 0
        }

        logger.info(f"[ROBO ORDER PARAMS] {order_params}")

        response = angel.placeOrderFullResponse(order_params)
        time.sleep(delay_between_requests)

        return response, order_params

    # ===============================
    # EXECUTE TRADE (main entry point)
    # ===============================

    def execute_trade(self, angel, settings, entry, user_profile):
        """
        Execute the trade when entry signal is found using ROBO (Bracket Order).
        Exact original flow preserved.

        Returns:
            (True, limit_price) on success
            False on failure
        """
        # ---- Trade limit check ----
        # Note: strategy increments trade count after this returns True
        logger.info(f"[TRADE] Executing ROBO trade for {entry['option_symbol']}")

        ltp = self.get_option_ltp("NFO", angel, entry['option_symbol'])

        try:
            try:
                fund_allocation = float(settings["fund_allocation"])
                trades_per_day = int(settings["trades_per_day"])
            except (ValueError, TypeError) as e:
                logger.error(f"[TRADE] Invalid fund_allocation or trades_per_day: {e}")
                return False

            if fund_allocation <= 0:
                logger.error(f"[TRADE] fund_allocation must be > 0 got: {fund_allocation}")
                return False

            if trades_per_day <= 0:
                logger.error(f"[TRADE] trades_per_day must be > 0 got: {trades_per_day}")
                return False

            per_trade_allocation = fund_allocation / trades_per_day
            logger.info(f"[TRADE] Fund: {fund_allocation} Trades/Day: {trades_per_day} Per Trade: {per_trade_allocation}")

            if ltp is None:
                logger.error(f"[TRADE] Could not get LTP for {entry['option_symbol']}")
                return False

            if ltp <= 0:
                logger.error(f"[TRADE] Invalid LTP for {entry['option_symbol']}: {ltp}")
                return False

            lot_size = int(self.lot_size_lookup(entry['option_symbol'], self.instrument_list, exchange="NFO"))
            if not lot_size or lot_size <= 0:
                logger.error(f"[TRADE] Invalid lot size for {entry['option_symbol']}: {lot_size}")
                return False

            cost_per_lot = ltp * lot_size
            max_lots = int(per_trade_allocation // cost_per_lot)

            if max_lots <= 0:
                logger.error(f"[TRADE] Cannot afford even 1 lot. Cost per lot: {cost_per_lot}, Per trade: {per_trade_allocation}")
                return False

            requested_qty = max_lots
            logger.info(f"Final Qty: {requested_qty} Lot Size: {lot_size}")

            qty = int(lot_size) * requested_qty

            # ---- Profit/Loss pct ----
            target_pct = float(settings.get("exit_by_profit", 0))
            stoploss_pct = float(settings.get("exit_by_loss", 0))

            # ---- Limit price ----
            limit_multiplier = float(settings.get('limit_multiplier', 1.0))

            if 'five_min_high' not in entry:
                logger.error(f"[TRADE] five_min_high not found in entry for {entry['option_symbol']}")
                return False

            five_min_high = float(entry.get('five_min_high', 0))
            if five_min_high <= 0:
                logger.error(f"[TRADE] Invalid five_min_high: {five_min_high}")
                return False

            limit_price = round(five_min_high * limit_multiplier, 2)

            if target_pct <= 0 or stoploss_pct <= 0:
                logger.error("[ROBO] Target and stoploss percentages must be > 0 for ROBO orders")
                return False

            # ---- Target and stoploss ----
            target_points = self.calculate_target(limit_price, target_pct)
            calculated_stoploss = limit_price * stoploss_pct / 100
            original_stoploss = abs(limit_price - entry['stoploss'])
            stoploss = min(calculated_stoploss, original_stoploss)
            if stoploss <= 0:
                stoploss = 0.1

            transaction_type = "BUY"
            squareoff = target_points

            logger.info(f"[ROBO CALCULATIONS] Entry: {limit_price}, Target: {squareoff}, calculated_sl: {calculated_stoploss}, candle_sl={original_stoploss}, stoploss={stoploss}")

            # ---- Place order ----
            response, order_params = self.place_robo_order(
                angel=angel,
                option_symbol=entry['option_symbol'],
                qty=qty,
                limit_price=limit_price,
                squareoff=squareoff,
                stoploss=stoploss,
                transaction_type=transaction_type
            )

            # ---- Handle response ----
            if not response:
                logger.error(f"[ROBO] Empty response for {entry['option_symbol']}")
                return False

            try:
                response_data = response if isinstance(response, dict) else json.loads(response)
            except Exception:
                logger.error(f"[ROBO] Failed to parse response: {response}")
                return False

            time.sleep(1)

            if not response_data.get("status", False):
                reject_msg = response_data.get("message", "Order Rejected")
                logger.error(f"[ROBO] Order Failed: {reject_msg}")

                self.save_rejected_order(
                    user_profile=user_profile,
                    params=order_params,
                    response_data=response_data,
                    option_symbol=entry['option_symbol'],
                    stock_symbol=entry['stock_symbol'],
                    stoploss=0,
                    squareoff=0,
                    transaction_type=transaction_type,
                    settings=settings,
                    reject_msg=reject_msg
                )
                return False

            order_id = response_data.get("data", {}).get("orderid", "")
            logger.info(f"[ROBO SUCCESS] Main order placed: {order_id}")

            # ---- Get message from orderbook ----
            message = ""
            angel_orderbook = angel.orderBook()
            for order in angel_orderbook['data']:
                if order_id == order['orderid']:
                    message = order['text']
                    break

            self.save_order(
                user_profile=user_profile,
                params=order_params,
                response_data=response_data,
                order_id=order_id,
                qty=qty,
                option_symbol=entry['option_symbol'],
                stock_symbol=entry['stock_symbol'],
                stoploss=stoploss,
                squareoff=squareoff,
                transaction_type=transaction_type,
                settings=settings,
                entry_price=limit_price,
                message=message
            )

            # ---- Mark stock inactive in sector CSV ----
            # (strategy_engine.mark_stock_inactive_in_sector_csv is called by the strategy)
            logger.info(f"[ROBO COMPLETE] Bracket order placed for {entry['option_symbol']}")

            # ---- Validate order ----
            if self.validate_order(angel, order_id, entry['option_symbol']):
                return True, limit_price
            else:
                logger.warning(f"[TRADE NOT COUNTED] Order rejected or cancelled: {order_id}")
                return True, limit_price  # order placed but validation failed

        except Exception as e:
            logger.error(f"[ROBO] Trade execution failed: {str(e)}")
            return False
