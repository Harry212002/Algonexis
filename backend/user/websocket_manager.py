"""
websocket_manager.py
--------------------
Shared WebSocket Manager for SmartAPI (Angel One).
Single WebSocket connection. Multiple strategies can subscribe.

Flow:
    Angel WebSocket
          ↓
    SharedWebSocketManager
          ↓
    Token Subscribers
          ↓
    Strategy Callbacks
"""

import threading
import logging
import traceback
import json
import time

logger = logging.getLogger('dev_log')


class SharedWebSocketManager:
    """
    Manages a single SmartAPI WebSocket connection.
    Strategies subscribe tokens and receive LTP callbacks.
    """

    def __init__(self):
        self.sws = None
        self._ws_closing = False
        self._connected = False

        # token -> {"symbol": str, "limit_price": float, "row_data": dict}
        self.active_trades = {}

        # Injected at start() time
        self._angel = None
        self._settings = None
        self._user_profile = None
        self._order_manager = None
        self._strategy = None

        logger.info("[WS MANAGER] SharedWebSocketManager created")

    # ===============================
    # START
    # ===============================

    def start(self, angel, settings, user_profile, order_manager, strategy):
        """
        Initialize and connect the WebSocket.
        Called once from strategy_engine.run_phase2().
        """
        self._angel = angel
        self._settings = settings
        self._user_profile = user_profile
        self._order_manager = order_manager
        self._strategy = strategy
        self._ws_closing = False

        if self.sws is not None:
            logger.warning("[WS MANAGER] WebSocket already running, skipping re-init")
            return

        logger.info("========== [WS INIT START] ==========")

        try:
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2
            from .models import AngelOneCredentials  # adjust import path to your project

            # ---- Fetch tokens ----
            jwt_token = getattr(angel, "access_token", None)
            feed_token = None

            try:
                feed_token = angel.getfeedToken()
            except Exception as e:
                logger.error(f"[WS ERROR] Failed to fetch feed_token: {e}")

            angel_details = AngelOneCredentials.objects.get(
                user=self._user_profile
            )

            client_code = angel_details.angel_client_code
            api_key = getattr(angel, "api_key", None)

            # ---- Log ----
            logger.info(f"[WS PARAM] jwt_token exists: {bool(jwt_token)}")
            logger.info(f"[WS PARAM] feed_token exists: {bool(feed_token)}")
            logger.info(f"[WS PARAM] api_key exists: {bool(api_key)}")
            logger.info(f"[WS PARAM] client_code: {client_code}")

            if jwt_token:
                logger.info(f"[WS DEBUG] jwt_token sample: {jwt_token}")
            if feed_token:
                logger.info(f"[WS DEBUG] feed_token sample: {feed_token}")
            if api_key:
                logger.info(f"[WS DEBUG] api_key: {api_key}")

            # ---- Validate ----
            if not jwt_token:
                logger.error("[WS ERROR] jwt_token missing")
                return
            if not feed_token:
                logger.error("[WS ERROR] feed_token missing")
                return
            if not api_key:
                logger.error("[WS ERROR] api_key missing")
                return
            if not client_code:
                logger.error("[WS ERROR] client_code missing")
                return

            logger.info("[WS] All parameters validated successfully")

            # ---- Create WebSocket ----
            self.sws = SmartWebSocketV2(
                auth_token=jwt_token,
                api_key=api_key,
                client_code=client_code,
                feed_token=feed_token
            )

            logger.info("[WS] SmartWebSocketV2 object created")

            # ---- Attach callbacks ----
            self.sws.on_open = self._ws_on_open
            self.sws.on_data = self._ws_on_data
            self.sws.on_error = lambda ws, err: logger.error(f"[WS ERROR CALLBACK] {err}")
            self.sws.on_close = self._ws_on_close

            logger.info("[WS] Callbacks attached")

            # ---- Start connection thread ----
            threading.Thread(
                target=self._safe_ws_connect,
                daemon=True
            ).start()

            logger.info("[WS] WebSocket thread started successfully")
            logger.info("========== [WS INIT END] ==========")

        except Exception as e:
            logger.exception(f"[WS FATAL ERROR] {e}")

    # ===============================
    # CONNECTION
    # ===============================

    def _safe_ws_connect(self):
        try:
            self.sws.connect()
        except Exception as e:
            logger.exception(f"[WS CONNECT ERROR] {e}")

    def close_connection(self):
        """Close WebSocket connection and prevent reconnection."""
        if self.sws:
            try:
                self._ws_closing = True
                self.sws.close_connection()
                logger.info("[WS] WebSocket closed.")
            except Exception as e:
                logger.error(f"[WS] Error closing WebSocket: {e}")
            finally:
                if hasattr(self.sws, 'on_open'):
                    self.sws.on_open = None
                if hasattr(self.sws, 'on_data'):
                    self.sws.on_data = None
                if hasattr(self.sws, 'on_error'):
                    self.sws.on_error = None
                if hasattr(self.sws, 'on_close'):
                    self.sws.on_close = None
                self.sws = None
        else:
            logger.debug("[WS] No active WebSocket to close.")

    # ===============================
    # CALLBACKS
    # ===============================

    def _ws_on_open(self, ws):
        """
        Called when WebSocket connects.
        Subscribes all active tokens from watchlist2.csv.
        """
        import os
        import pandas as pd

        logger.info("[WS] Connected")
        self._connected = True

        watchlist_csv2 = 'watchlist2.csv'
        if not os.path.exists(watchlist_csv2):
            return

        df = pd.read_csv(watchlist_csv2)
        active_df = df[df["status"] == "ACTIVE"]

        if active_df.empty:
            return

        tokens = []
        instrument_list = self._order_manager.instrument_list

        for _, row in active_df.iterrows():
            symbol = row["option_symbol"]
            token = self._order_manager.token_lookup(symbol, instrument_list, exchange="NFO")

            if not token:
                continue

            tokens.append(token)
            self.active_trades[token] = {
                "symbol": symbol,
                "limit_price": float(row["limit_price"]),
                "row_data": row.to_dict()
            }

        if tokens:
            self.sws.subscribe(
                correlation_id="watchlist2",
                mode=1,
                token_list=[{
                    "exchangeType": 2,
                    "tokens": tokens
                }]
            )
            logger.info(f"[WS ON_OPEN] Subscribed {len(tokens)} tokens")

    def _ws_on_data(self, ws, message):
        """
        Called on every LTP tick.
        Checks if LTP >= limit_price, then executes trade.
        """
        import os
        import pandas as pd
        from django.utils import timezone as dj_timezone

        try:
            token = message.get("token")
            ltp_raw = message.get("last_traded_price")

            if not token or ltp_raw is None:
                return

            ltp = ltp_raw / 100

            current_time = dj_timezone.localtime(dj_timezone.now())
            formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")

            if token not in self.active_trades:
                return

            trade_data = self.active_trades[token]
            symbol = trade_data["symbol"]
            limit_price = trade_data["limit_price"]

            logger.info(
                f"[WS LTP] {formatted_time} | {symbol} | "
                f"LTP: {ltp} | Limit: {limit_price}"
            )

            # ---- STRICT LIMIT CHECK ----
            if ltp >= limit_price:
                logger.info(
                    f"[WS TRIGGER] {formatted_time} | {symbol} "
                    f"LTP {ltp} crossed {limit_price}"
                )

                # STEP 1: Remove token immediately
                trade_info = self.active_trades.pop(token, None)

                # STEP 2: Immediately unsubscribe
                try:
                    self.sws.unsubscribe(
                        correlation_id="watchlist2_dynamic",
                        mode=1,
                        token_list=[{
                            "exchangeType": 2,
                            "tokens": [token]
                        }]
                    )
                    logger.info(f"[WS UNSUBSCRIBED] {symbol}")
                except Exception as e:
                    logger.error(f"[WS UNSUBSCRIBE ERROR] {e}")

                if not trade_info:
                    return

                # Check trade limit via strategy
                if self._strategy and self._strategy.trades_today >= self._strategy.max_trades_per_day:
                    logger.warning(
                        f"[WS BLOCKED] Trade limit reached "
                        f"{self._strategy.trades_today}/{self._strategy.max_trades_per_day}"
                    )
                    return

                # STEP 3: Execute trade via order_manager
                result = self._order_manager.execute_trade(
                    self._angel,
                    self._settings,
                    trade_info["row_data"],
                    self._user_profile
                )

                if isinstance(result, tuple):
                    success, exec_limit_price = result
                else:
                    success = result
                    exec_limit_price = 0

                # Update watchlist2 CSV
                watchlist_csv2 = 'watchlist2.csv'
                if os.path.exists(watchlist_csv2):
                    df = pd.read_csv(watchlist_csv2)
                    df.loc[df["option_symbol"] == symbol, "status"] = "INACTIVE"
                    df.to_csv(watchlist_csv2, index=False)

                if success:
                    logger.info(f"[WS DONE] {formatted_time} | {symbol} executed successfully")
                    if self._strategy:
                        self._strategy.increment_trade_count()

        except Exception as e:
            logger.exception(f"[WS DATA ERROR] {e}")

    def _ws_on_close(self, ws):
        logger.warning("[WS CLOSED CALLBACK]")
        self._connected = False

    # ===============================
    # SUBSCRIBE / UNSUBSCRIBE
    # ===============================

    def subscribe_token(self, symbol, limit_price, row_data, instrument_list):
        """
        Dynamically subscribe a new token after phase2 condition is met.
        Called from strategy_engine.process_stock_for_phase2().
        """
        if not self.sws:
            logger.warning("[WS] Cannot subscribe - WebSocket not initialized")
            return

        token = self._order_manager.token_lookup(symbol, instrument_list, exchange="NFO")
        if not token:
            logger.warning(f"[WS] Token not found for {symbol}")
            return

        if token in self.active_trades:
            logger.info(f"[WS] Token {token} for {symbol} already subscribed")
            return

        self.active_trades[token] = {
            "symbol": symbol,
            "limit_price": limit_price,
            "row_data": row_data
        }

        self.sws.subscribe(
            correlation_id="watchlist2_dynamic",
            mode=1,
            token_list=[{
                "exchangeType": 2,
                "tokens": [token]
            }]
        )

        logger.info(f"[WS] Dynamically subscribed {symbol} | Token: {token} | Limit: {limit_price}")

    def unsubscribe_all(self):
        """
        Unsubscribe all tokens.
        Called from strategy_engine.deactivate_watchlist2().
        """
        if not self.sws or not self.active_trades:
            return

        tokens = list(self.active_trades.keys())

        try:
            self.sws.unsubscribe(
                correlation_id="watchlist2_reset",
                mode=1,
                token_list=[{
                    "exchangeType": 2,
                    "tokens": tokens
                }]
            )
            self.active_trades.clear()
            logger.info(f"[WS] Unsubscribed {len(tokens)} tokens")
        except Exception as e:
            logger.error(f"[WS UNSUBSCRIBE ALL ERROR] {e}")

    def reset_ltp_tracking(self):
        """
        Unsubscribe all websocket tokens and clear active trades.
        Called before new sector scan starts.
        """
        try:
            if not self.sws or not self.active_trades:
                return

            tokens = list(self.active_trades.keys())
            logger.info(f"[WS RESET] Unsubscribing {len(tokens)} tokens")

            self.sws.unsubscribe(
                correlation_id="watchlist2_reset",
                mode=1,
                token_list=[{
                    "exchangeType": 2,
                    "tokens": tokens
                }]
            )

            self.active_trades.clear()
            logger.info("[WS RESET] Active trades cleared")

        except Exception as e:
            logger.error(f"[WS RESET ERROR] {e}")
