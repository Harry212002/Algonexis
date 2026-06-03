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

Fixes applied:
  1. Credentials are passed directly via start() instead of reading from
     django.conf.settings at connect-time (fixes jwt_token missing error).
  2. on_error callback signature fixed to accept (ws, err) properly.
  3. close_connection() nulls sws before clearing callbacks to avoid
     AttributeError on already-closed socket.
  4. subscribe_token() guards against sws being None more robustly.
  5. _ws_on_close reconnect path re-uses stored credentials correctly.
"""

import threading
import logging
import time
import os
import pandas as pd
from datetime import datetime

logger = logging.getLogger('strategy_log')


class SharedWebSocketManager:
    """
    Manages a single SmartAPI WebSocket connection.
    Strategies subscribe tokens and receive LTP callbacks.

    Usage:
        manager.start(angel, settings, user_profile, order_manager, strategy,
                      jwt_token, feed_token, client_code, api_key)
        manager.subscribe_token(symbol, limit_price, row_data, instrument_list)
        manager.unsubscribe_all()
        manager.close_connection()
    """

    def __init__(self):
        self.sws             = None
        self._ws_closing     = False
        self._connected      = False
        self._connect_lock   = threading.Lock()

        # token -> {"symbol": str, "limit_price": float, "row_data": dict}
        self.active_trades   = {}
        self._trades_lock    = threading.Lock()

        # Injected at start() time
        self._angel          = None
        self._settings       = None
        self._user_profile   = None
        self._order_manager  = None
        self._strategy       = None

        # Credentials stored at start() time so reconnect can reuse them
        self._jwt_token      = None
        self._feed_token     = None
        self._client_code    = None
        self._api_key        = None

        logger.info("[WS MANAGER] SharedWebSocketManager created")

    # ===============================
    # START
    # ===============================

    def start(self, angel, settings, user_profile, order_manager, strategy,
              jwt_token=None, feed_token=None, client_code=None, api_key=None):
        """
        Initialize and connect the WebSocket.
        Safe to call multiple times — will skip if already running.

        Credentials can be passed directly (preferred) or will be read
        from django.conf.settings as fallback.
        """
        with self._connect_lock:
            if self._connected and self.sws is not None:
                logger.info("[WS MANAGER] WebSocket already connected, skipping re-init")
                return

            self._angel         = angel
            self._settings      = settings
            self._user_profile  = user_profile
            self._order_manager = order_manager
            self._strategy      = strategy
            self._ws_closing    = False

            logger.info("========== [WS INIT START] ==========")

            try:
                # ---- Resolve credentials ----
                # Priority: passed-in args > django settings > env
                resolved_jwt    = jwt_token
                resolved_feed   = feed_token
                resolved_code   = client_code
                resolved_api    = api_key

                if not resolved_jwt or not resolved_feed or not resolved_api or not resolved_code:
                    try:
                        from django.conf import settings as django_settings
                        resolved_jwt  = resolved_jwt  or getattr(django_settings, 'ANGEL_JWT_TOKEN',  None)
                        resolved_feed = resolved_feed or getattr(django_settings, 'ANGEL_FEED_TOKEN', None)
                        resolved_code = resolved_code or getattr(django_settings, 'ANGEL_CLIENT_CODE', None)
                        resolved_api  = resolved_api  or getattr(django_settings, 'ANGEL_API_KEY',    None)
                        logger.info("[WS CONFIG] Credentials resolved from django settings")
                    except Exception:
                        logger.exception("[WS CONFIG] Could not read from django settings")

                logger.info(f"[WS PARAM] jwt_token   exists: {bool(resolved_jwt)}")
                logger.info(f"[WS PARAM] feed_token  exists: {bool(resolved_feed)}")
                logger.info(f"[WS PARAM] api_key     exists: {bool(resolved_api)}")
                logger.info(f"[WS PARAM] client_code : {resolved_code}")

                if not resolved_jwt:
                    logger.error("[WS ERROR] jwt_token missing — aborting WS start")
                    return
                if not resolved_feed:
                    logger.error("[WS ERROR] feed_token missing — aborting WS start")
                    return
                if not resolved_api:
                    logger.error("[WS ERROR] api_key missing — aborting WS start")
                    return
                if not resolved_code:
                    logger.error("[WS ERROR] client_code missing — aborting WS start")
                    return

                # Store for reconnect
                self._jwt_token   = resolved_jwt
                self._feed_token  = resolved_feed
                self._client_code = resolved_code
                self._api_key     = resolved_api

                logger.info("[WS] All parameters validated successfully")

                from SmartApi.smartWebSocketV2 import SmartWebSocketV2

                self.sws = SmartWebSocketV2(
                    auth_token  = resolved_jwt,
                    api_key     = resolved_api,
                    client_code = resolved_code,
                    feed_token  = resolved_feed,
                )

                logger.info("[WS] SmartWebSocketV2 object created")

                self.sws.on_open  = self._ws_on_open
                self.sws.on_data  = self._ws_on_data
                self.sws.on_error = self._ws_on_error
                self.sws.on_close = self._ws_on_close

                logger.info("[WS] Callbacks attached")

                t = threading.Thread(target=self._safe_ws_connect, daemon=True)
                t.start()

                logger.info("[WS] WebSocket connection thread started")
                logger.info("========== [WS INIT END] ==========")

            except Exception:
                logger.exception("[WS FATAL ERROR] Failed to start WebSocket")

    # ===============================
    # CONNECTION
    # ===============================

    def _safe_ws_connect(self):
        start_time = datetime.now()

        logger.info(
            f"[WS CONNECT START] "
            f"time={start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        try:
            if self.sws is None:
                logger.error(
                    "[WS CONNECT ERROR] sws is None before connect()"
                )
                return

            logger.info(
                f"[WS CONNECT] Calling SmartWebSocketV2.connect()"
            )

            self.sws.connect()

            logger.info(
                "[WS CONNECT] connect() call returned"
            )

        except Exception as e:
            self._connected = False

            logger.exception(
                f"[WS CONNECT ERROR] "
                f"type={type(e).__name__} "
                f"message={str(e)}"
            )

    def close_connection(self):
        """Close WebSocket connection gracefully."""
        with self._connect_lock:
            if self.sws is None:
                logger.debug("[WS] No active WebSocket to close.")
                return
            sws_ref = self.sws
            self.sws       = None
            self._connected = False
            try:
                self._ws_closing = True
                sws_ref.close_connection()
                logger.info("[WS] WebSocket closed.")
            except Exception:
                logger.exception("[WS] Error closing WebSocket")
            finally:
                # Null out callbacks on the old reference to prevent stale calls
                try:
                    sws_ref.on_open  = None
                    sws_ref.on_data  = None
                    sws_ref.on_error = None
                    sws_ref.on_close = None
                except Exception:
                    pass

    # ===============================
    # CALLBACKS
    # ===============================

    def _ws_on_open(self, ws):
        """
        Called when WebSocket connects.
        Re-subscribes any tokens already in active_trades (e.g., after reconnect).
        """
        logger.info(
            f"[WS CONNECTED] "
            f"time={datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
            f"client_code={self._client_code}"
        )

        logger.info(
            f"[WS CONNECTED] "
            f"active_tokens_before_resubscribe="
            f"{len(self.active_trades)}"
        )
        self._connected = True

        with self._trades_lock:
            tokens = list(self.active_trades.keys())

        if tokens:
            try:
                self.sws.subscribe(
                    correlation_id="reconnect_resub",
                    mode=1,
                    token_list=[{"exchangeType": 2, "tokens": tokens}],
                )
                logger.info(f"[WS ON_OPEN] Re-subscribed {len(tokens)} tokens on connect/reconnect")
            except Exception:
                logger.exception("[WS ON_OPEN] Re-subscribe failed")
        else:
            logger.info("[WS ON_OPEN] No tokens to subscribe on connect")

    def _ws_on_error(self, ws, err):
        """Unified error callback with proper (ws, err) signature."""
        logger.error(
            f"[WS ERROR CALLBACK] "
            f"type={type(err).__name__} "
            f"error={err}"
        )

        logger.error(
            f"[WS ERROR CALLBACK] "
            f"connected={self._connected} "
            f"sws_exists={self.sws is not None}"
        )

    def _ws_on_data(self, ws, message):
        """
        Called on every LTP tick.
        Checks if LTP >= limit_price, then executes trade.
        """
        from django.utils import timezone as dj_timezone

        try:
            token   = message.get("token")
            ltp_raw = message.get("last_traded_price")

            if not token or ltp_raw is None:
                return

            ltp = ltp_raw / 100

            with self._trades_lock:
                if token not in self.active_trades:
                    return
                trade_data  = self.active_trades[token]

            symbol      = trade_data["symbol"]
            limit_price = trade_data["limit_price"]

            current_time   = dj_timezone.localtime(dj_timezone.now())
            formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")

            logger.info(
                f"[WS LTP] {formatted_time} | {symbol} | "
                f"LTP: {ltp:.2f} | Limit: {limit_price:.2f}"
            )

            if ltp < limit_price:
                return

            # ---- Trigger ----
            logger.info(
                f"[WS TRIGGER] {formatted_time} | {symbol} "
                f"LTP {ltp:.2f} >= limit {limit_price:.2f}"
            )

            # Remove token immediately to prevent duplicate triggers
            with self._trades_lock:
                trade_info = self.active_trades.pop(token, None)

            if trade_info is None:
                logger.warning(f"[WS] Trade info already removed for {symbol}, skipping")
                return

            # Unsubscribe this token
            try:
                if self.sws:
                    self.sws.unsubscribe(
                        correlation_id="trigger_unsub",
                        mode=1,
                        token_list=[{"exchangeType": 2, "tokens": [token]}],
                    )
                    logger.info(f"[WS UNSUBSCRIBED] {symbol} (token={token})")
            except Exception:
                logger.exception(f"[WS UNSUBSCRIBE ERROR] {symbol}")

            # Check trade limit
            if self._strategy and self._strategy.trades_today >= self._strategy.max_trades_per_day:
                logger.warning(
                    f"[WS BLOCKED] Trade limit reached "
                    f"({self._strategy.trades_today}/{self._strategy.max_trades_per_day}) — skipping {symbol}"
                )
                return

            # Execute trade
            try:
                result = self._order_manager.execute_trade(
                    self._angel,
                    self._settings,
                    trade_info["row_data"],
                    self._user_profile,
                )
                success = result[0] if isinstance(result, tuple) else result
            except Exception:
                logger.exception(f"[WS EXECUTE TRADE ERROR] {symbol}")
                success = False

            # Update watchlist2 CSV
            try:
                watchlist_csv2 = 'watchlist2.csv'
                if os.path.exists(watchlist_csv2):
                    df = pd.read_csv(watchlist_csv2)
                    df.loc[df["option_symbol"] == symbol, "status"] = "INACTIVE"
                    df.to_csv(watchlist_csv2, index=False)
            except Exception:
                logger.exception(f"[WS CSV UPDATE ERROR] {symbol}")

            if success:
                logger.info(f"[WS DONE] {formatted_time} | {symbol} executed successfully")
                if self._strategy:
                    self._strategy.increment_trade_count()
            else:
                logger.error(f"[WS DONE] {formatted_time} | {symbol} execution FAILED")

        except Exception:
            logger.exception("[WS DATA ERROR]")

    def _ws_on_close(self, ws):
        logger.warning("[WS CLOSED CALLBACK] WebSocket connection closed")
        self._connected = False

        # Auto-reconnect if not intentionally closed and credentials available
        if not self._ws_closing and self._angel is not None and self._jwt_token:
            logger.info("[WS] Attempting reconnect in 5s...")
            time.sleep(5)

            # Rebuild sws object with stored credentials before reconnecting
            try:
                from SmartApi.smartWebSocketV2 import SmartWebSocketV2
                with self._connect_lock:
                    if self._ws_closing:   # may have been set during sleep
                        return
                    self.sws = SmartWebSocketV2(
                        auth_token  = self._jwt_token,
                        api_key     = self._api_key,
                        client_code = self._client_code,
                        feed_token  = self._feed_token,
                    )
                    self.sws.on_open  = self._ws_on_open
                    self.sws.on_data  = self._ws_on_data
                    self.sws.on_error = self._ws_on_error
                    self.sws.on_close = self._ws_on_close
                    logger.info("[WS] Rebuilt SmartWebSocketV2 for reconnect")

                t = threading.Thread(target=self._safe_ws_connect, daemon=True)
                t.start()
            except Exception:
                logger.exception("[WS] Reconnect rebuild failed")

    # ===============================
    # SUBSCRIBE / UNSUBSCRIBE
    # ===============================

    def subscribe_token(self, symbol, limit_price, row_data, instrument_list):
        """
        Dynamically subscribe a new token.
        Called from strategy when a Phase 2 condition is met.
        """
        if self.sws is None:
            logger.warning(f"[WS] Cannot subscribe {symbol} — WebSocket not initialized")
            return

        if not self._connected:
            logger.warning(f"[WS] Cannot subscribe {symbol} — WebSocket not yet connected")
            return

        if self._order_manager is None:
            logger.warning(f"[WS] Cannot subscribe {symbol} — order_manager not set")
            return

        token = self._order_manager.token_lookup(symbol, instrument_list, exchange="NFO")
        if not token:
            logger.warning(f"[WS] Token not found for {symbol}")
            return

        with self._trades_lock:
            if token in self.active_trades:
                logger.info(f"[WS] {symbol} (token={token}) already subscribed, skipping")
                return

            self.active_trades[token] = {
                "symbol":      symbol,
                "limit_price": limit_price,
                "row_data":    row_data,
            }

        try:
            self.sws.subscribe(
                correlation_id="dynamic_sub",
                mode=1,
                token_list=[{"exchangeType": 2, "tokens": [token]}],
            )
            logger.info(
                f"[WS SUBSCRIBED] {symbol} | token={token} | limit={limit_price:.2f}"
            )
        except Exception:
            logger.exception(f"[WS SUBSCRIBE ERROR] {symbol}")
            with self._trades_lock:
                self.active_trades.pop(token, None)

    def unsubscribe_all(self):
        """
        Unsubscribe all active tokens and clear the trade map.
        Called before a new scan cycle or on Phase 2 end.
        """
        if self.sws is None:
            logger.debug("[WS] unsubscribe_all — no sws instance")
            return

        with self._trades_lock:
            tokens = list(self.active_trades.keys())
            if not tokens:
                logger.info("[WS] unsubscribe_all — nothing to unsubscribe")
                return
            self.active_trades.clear()

        try:
            self.sws.unsubscribe(
                correlation_id="batch_unsub",
                mode=1,
                token_list=[{"exchangeType": 2, "tokens": tokens}],
            )
            logger.info(f"[WS] Unsubscribed {len(tokens)} tokens")
        except Exception:
            logger.exception("[WS UNSUBSCRIBE ALL ERROR]")

    def is_connected(self):
        return self._connected and self.sws is not None