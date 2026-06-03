"""
views.py
--------
All bot start/stop control lives here.
No other file starts or stops the bot.

ACTIVE_BOTS registry:
    key   = user.id
    value = {
        "strategy":  SectorMomentumBreakoutStrategy instance,
        "stop_event": threading.Event,
        "thread":     threading.Thread,
        "ws_manager": SharedWebSocketManager instance,
        "order_mgr":  OrderManager instance,
    }
"""

import json
import logging
import threading
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from .decorators import role_required
from .models import User, AngelOneCredentials, SectorMomentumBreakoutConfig

logger = logging.getLogger("strategy_log")

# -----------------------------------------------------------------------
# Global bot registry  {user_id: {...}}
# -----------------------------------------------------------------------
ACTIVE_BOTS = {}


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------

def _build_settings_from_config(config):
    """Convert a SectorMomentumBreakoutConfig ORM object to a plain dict."""
    return {
        "broker":             config.broker,
        "expiry_date":        config.expiry_date,
        "strike_price":       config.strike_price,
        "entry_time":         config.entry_time.strftime("%H:%M"),
        "exit_time":          config.exit_time.strftime("%H:%M"),
        "trades_per_day":     config.trades_per_day,
        "fund_allocation":    config.fund_allocation,
        "exit_by_profit":     config.target_percentage,
        "exit_by_loss":       config.stoploss_percentage,
        "volume_multiplier":  config.volume_multiplier,
        "limit_multiplier":   config.limit_multiplier,
        "sectors_scan":       config.sectors_scan,
        "stocks_scan":        config.stocks_scan,
        "strategy_name":      config.strategy_name,
        # Optional phase-time overrides from DB (may be None → use class defaults)
        "phase1_start_time":  config.phase1_start_time.strftime("%H:%M") if config.phase1_start_time else None,
        "phase1_end_time":    config.phase1_end_time.strftime("%H:%M")   if config.phase1_end_time   else None,
        "phase2_start_time":  config.phase2_start_time.strftime("%H:%M") if config.phase2_start_time else None,
        "phase2_end_time":    config.phase2_end_time.strftime("%H:%M")   if config.phase2_end_time   else None,
    }


def _start_bot(user, config):
    """
    Create and start a SectorMomentumBreakoutStrategy bot for `user`.
    Returns (True, message) or (False, error_message).
    """
    from SmartApi import SmartConnect
    import pyotp

    user_id = user.id

    if user_id in ACTIVE_BOTS:
        logger.warning(f"[BOT] Bot already running for user {user_id}")
        return False, "Bot is already running"

    # ---- Load Angel One credentials ----
    try:
        credentials = AngelOneCredentials.objects.get(user=user, is_active=True)
    except AngelOneCredentials.DoesNotExist:
        logger.error(f"[BOT] No active Angel One credentials for user {user_id}")
        return False, "Angel One credentials not found or inactive"

    # ---- Authenticate ----
    try:
        totp = pyotp.TOTP(credentials.angel_totp_secret).now()
        angel = SmartConnect(api_key=credentials.angel_api_key)
        session_data = angel.generateSession(
            credentials.angel_client_code,
            credentials.angel_password,
            totp
        )
        if not session_data or not session_data.get("status"):
            raise ValueError(f"Session creation failed: {session_data}")
        logger.info(f"[BOT] Angel One session created for user {user_id}")
    except Exception as e:
        logger.exception(f"[BOT] Authentication failed for user {user_id}: {e}")
        return False, f"Angel One authentication failed: {str(e)}"

    # ---- Build settings ----
    settings_dict = _build_settings_from_config(config)

    # ---- Create support objects ----
    from .order_manager import OrderManager
    from .websocket_manager import SharedWebSocketManager
    from .strategies.sector_momentum_breakout_strategy import SectorMomentumBreakoutStrategy

    stop_event = threading.Event()
    order_mgr  = OrderManager()
    ws_manager = SharedWebSocketManager()

    # ---- Create strategy (scheduler_loop starts inside __init__) ----
    strategy = SectorMomentumBreakoutStrategy(
        angel=angel,
        settings=settings_dict,
        data={},
        user_profile=user,
        stop_event=stop_event,
        websocket_manager=ws_manager,
        order_manager=order_mgr,
    )

    # ---- Register in global registry ----
    ACTIVE_BOTS[user_id] = {
        "strategy":   strategy,
        "stop_event": stop_event,
        "ws_manager": ws_manager,
        "order_mgr":  order_mgr,
        "angel":      angel,
        "started_at": timezone.now(),
    }

    logger.info(f"[BOT] Bot started successfully for user {user_id}")
    return True, "Bot started successfully"


def _stop_bot(user_id):
    """
    Gracefully stop a running bot for `user_id`.
    Returns (True, message) or (False, error_message).
    """
    if user_id not in ACTIVE_BOTS:
        logger.warning(f"[BOT] No active bot found for user {user_id}")
        return False, "No active bot found for this user"

    bot = ACTIVE_BOTS[user_id]

    # 1. Signal the scheduler loop to exit
    stop_event = bot.get("stop_event")
    if stop_event:
        stop_event.set()
        logger.info(f"[BOT] Stop event set for user {user_id}")

    # 2. Unsubscribe all websocket tokens
    ws_manager = bot.get("ws_manager")
    if ws_manager:
        try:
            ws_manager.unsubscribe_all()
            logger.info(f"[BOT] WebSocket tokens unsubscribed for user {user_id}")
        except Exception as e:
            logger.error(f"[BOT] Error unsubscribing WS tokens for user {user_id}: {e}")

        # 3. Close websocket connection
        try:
            ws_manager.close_connection()
            logger.info(f"[BOT] WebSocket connection closed for user {user_id}")
        except Exception as e:
            logger.error(f"[BOT] Error closing WS connection for user {user_id}: {e}")

    # 4. Remove from registry
    del ACTIVE_BOTS[user_id]
    logger.info(f"[STOP] Bot removed from ACTIVE_BOTS for user {user_id}")

    return True, "Bot stopped successfully"


# -----------------------------------------------------------------------
# AUTH VIEWS
# -----------------------------------------------------------------------

@csrf_exempt
def register(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid Request Method"}, status=405)

    try:
        data = json.loads(request.body)

        first_name       = data.get("first_name")
        last_name        = data.get("last_name")
        mobile_number    = data.get("mobile_number")
        email            = data.get("email")
        password         = data.get("password")
        confirm_password = data.get("confirm_password")

        if not all([first_name, last_name, mobile_number, email, password, confirm_password]):
            return JsonResponse({"error": "All fields are required"}, status=400)

        if password != confirm_password:
            return JsonResponse({"error": "Passwords do not match"}, status=400)

        if User.objects.filter(email=email).exists():
            return JsonResponse({"success": False, "message": "User already registered with this email"}, status=400)

        if User.objects.filter(mobile_number=mobile_number).exists():
            return JsonResponse({"success": False, "message": "Mobile number already registered"}, status=400)

        user = User.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            mobile_number=mobile_number,
            email=email,
            password=password,
            role="TRADER",
            is_active=True,
        )

        return JsonResponse({"success": True, "message": "User registered successfully", "user_id": user.id}, status=201)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@csrf_exempt
def login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data     = json.loads(request.body)
        email    = data.get("email")
        password = data.get("password")

        if not email or not password:
            return JsonResponse({"success": False, "message": "email and password are required"}, status=400)

        user = User.objects.filter(email=email).first()
        if not user:
            return JsonResponse({"success": False, "message": "Invalid Email or Password"}, status=400)

        if not user.check_password(password):
            return JsonResponse({"success": False, "message": "Invalid Password"}, status=401)

        access_token = AccessToken.for_user(user)

        return JsonResponse({
            "success": True,
            "message": "Login successfully",
            "access_token": str(access_token),
            "user": {
                "id":         user.id,
                "first_name": user.first_name,
                "last_name":  user.last_name,
                "email":      user.email,
                "role":       user.role,
            },
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


# -----------------------------------------------------------------------
# ANGEL ONE CREDENTIAL VIEWS
# -----------------------------------------------------------------------

@csrf_exempt
@role_required("TRADER")
def save_angelone_credentials(request):
    if request.method not in ["POST", "PUT"]:
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)

        angel_api_key      = data.get("angel_api_key")
        angel_client_code  = data.get("angel_client_code")
        angel_password     = data.get("angel_password")
        angel_totp_secret  = data.get("angel_totp_secret")

        if not all([angel_api_key, angel_client_code, angel_password, angel_totp_secret]):
            return JsonResponse({"success": False, "message": "All fields are required"}, status=400)

        user = request.user

        credential, created = AngelOneCredentials.objects.update_or_create(
            user=user,
            defaults={
                "angel_api_key":     angel_api_key,
                "angel_client_code": angel_client_code,
                "angel_password":    angel_password,
                "angel_totp_secret": angel_totp_secret,
                "is_active":         True,
            },
        )

        return JsonResponse({
            "success": True,
            "message": "Angel One credentials added successfully" if created else "Angel One credentials updated successfully",
            "data": {
                "id":          credential.id,
                "client_code": credential.angel_client_code,
                "is_active":   credential.is_active,
            },
        }, status=201 if created else 200)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@csrf_exempt
@role_required("TRADER")
def get_angelone_credentials(request):
    if request.method != "GET":
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=405)

    try:
        credential = AngelOneCredentials.objects.filter(user=request.user).first()
        if not credential:
            return JsonResponse({"success": False, "message": "No Angel One credentials found"}, status=404)

        return JsonResponse({
            "success": True,
            "data": {
                "id":                credential.id,
                "angel_api_key":     credential.angel_api_key,
                "angel_client_code": credential.angel_client_code,
                "angel_password":    credential.angel_password,
                "angel_totp_secret": credential.angel_totp_secret,
                "is_active":         credential.is_active,
            },
        }, status=200)

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


# -----------------------------------------------------------------------
# SECTOR MOMENTUM CONFIG VIEWS
# -----------------------------------------------------------------------

@csrf_exempt
@role_required("TRADER")
def save_sector_momentum_config(request):
    if request.method not in ["POST", "PUT"]:
        return JsonResponse({"success": False, "message": "Invalid Request Method"}, status=405)

    try:
        data = json.loads(request.body)

        # Parse optional phase-time overrides
        def _parse_time(val):
            if not val:
                return None
            try:
                return datetime.strptime(val, "%H:%M").time()
            except Exception:
                return None

        config, created = SectorMomentumBreakoutConfig.objects.update_or_create(
            user=request.user,
            strategy_name="Sector Momentum Breakout",
            defaults={
                "broker":           data.get("broker"),
                "expiry_date":      data.get("expiry_date"),
                "strike_price":     int(data.get("strike_price", 1)),
                "entry_time":       datetime.strptime(data.get("entry_time"), "%H:%M").time(),
                "exit_time":        datetime.strptime(data.get("exit_time"),  "%H:%M").time(),
                "trades_per_day":   int(data.get("trades_per_day", 5)),
                "fund_allocation":  float(data.get("fund_allocation", 100000)),
                "target_percentage":   float(data.get("target_percentage", 5)),
                "stoploss_percentage": float(data.get("stoploss_percentage", 2)),
                "volume_multiplier":   float(data.get("volume_multiplier", 3)),
                "limit_multiplier":    float(data.get("limit_multiplier", 1)),
                "sectors_scan":        int(data.get("sectors_scan", 3)),
                "stocks_scan":         int(data.get("stocks_scan", 3)),
                # Phase time overrides (optional)
                "phase1_start_time": _parse_time(data.get("phase1_start_time")),
                "phase1_end_time":   _parse_time(data.get("phase1_end_time")),
                "phase2_start_time": _parse_time(data.get("phase2_start_time")),
                "phase2_end_time":   _parse_time(data.get("phase2_end_time")),
            },
        )

        return JsonResponse({"success": True, "message": "Configuration Saved", "config_id": config.id})

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@csrf_exempt
@role_required("TRADER")
def get_sector_momentum_config(request):
    try:
        config = SectorMomentumBreakoutConfig.objects.get(
            user=request.user,
            strategy_name="Sector Momentum Breakout",
        )

        return JsonResponse({
            "success": True,
            "data": {
                "broker":              config.broker,
                "expiry_date":         config.expiry_date,
                "strike_price":        config.strike_price,
                "entry_time":          config.entry_time.strftime("%H:%M"),
                "exit_time":           config.exit_time.strftime("%H:%M"),
                "trades_per_day":      config.trades_per_day,
                "fund_allocation":     config.fund_allocation,
                "target_percentage":   config.target_percentage,
                "stoploss_percentage": config.stoploss_percentage,
                "volume_multiplier":   config.volume_multiplier,
                "limit_multiplier":    config.limit_multiplier,
                "sectors_scan":        config.sectors_scan,
                "stocks_scan":         config.stocks_scan,
                "is_bot_running":      config.is_bot_running,
                "phase1_start_time":   config.phase1_start_time.strftime("%H:%M") if config.phase1_start_time else None,
                "phase1_end_time":     config.phase1_end_time.strftime("%H:%M")   if config.phase1_end_time   else None,
                "phase2_start_time":   config.phase2_start_time.strftime("%H:%M") if config.phase2_start_time else None,
                "phase2_end_time":     config.phase2_end_time.strftime("%H:%M")   if config.phase2_end_time   else None,
            },
        })

    except SectorMomentumBreakoutConfig.DoesNotExist:
        return JsonResponse({"success": False, "message": "Config not found"}, status=404)


# -----------------------------------------------------------------------
# BOT TOGGLE  ← single entry-point for start / stop
# -----------------------------------------------------------------------

@csrf_exempt
@role_required("TRADER")
def toggle_sector_momentum_bot(request):
    """
    POST body: {"is_bot_running": true | false}

    true  → authenticate Angel One, create strategy instance, start scheduler
    false → set stop_event, unsubscribe all, close WS, remove from ACTIVE_BOTS
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=405)

    try:
        data           = json.loads(request.body)
        is_bot_running = bool(data.get("is_bot_running"))
        user           = request.user

        config = SectorMomentumBreakoutConfig.objects.get(
            user=user,
            strategy_name="Sector Momentum Breakout",
        )

        # ----------------------------------------------------------------
        # START BOT
        # ----------------------------------------------------------------
        if is_bot_running:
            logger.info(f"[BOT] Start request received for user {user.id}")

            if user.id in ACTIVE_BOTS:
                return JsonResponse({
                    "success": False,
                    "message": "Bot is already running",
                    "data": {"is_bot_running": True},
                }, status=400)

            success, message = _start_bot(user, config)

            if not success:
                return JsonResponse({"success": False, "message": message}, status=500)

            # Persist running state
            config.is_bot_running = True
            config.save(update_fields=["is_bot_running"])

            return JsonResponse({
                "success": True,
                "message": message,
                "data": {"is_bot_running": True},
            })

        # ----------------------------------------------------------------
        # STOP BOT
        # ----------------------------------------------------------------
        else:
            logger.info(f"[BOT] Stop request received for user {user.id}")

            success, message = _stop_bot(user.id)

            # Always persist stopped state regardless of whether a bot was found
            config.is_bot_running = False
            config.save(update_fields=["is_bot_running"])

            return JsonResponse({
                "success": True,
                "message": message,
                "data": {"is_bot_running": False},
            })

    except SectorMomentumBreakoutConfig.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Configuration not found. Please save configuration first.",
        }, status=404)

    except Exception as e:
        logger.exception(f"[BOT] toggle_sector_momentum_bot error: {e}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)


# -----------------------------------------------------------------------
# BOT STATUS  (bonus read-only endpoint)
# -----------------------------------------------------------------------

@csrf_exempt
@role_required("TRADER")
def get_bot_status(request):
    """GET → returns live status of the bot for the authenticated user."""
    if request.method != "GET":
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=405)

    user_id  = request.user.id
    is_alive = user_id in ACTIVE_BOTS

    info = {}
    if is_alive:
        bot = ACTIVE_BOTS[user_id]
        strategy = bot.get("strategy")
        info = {
            "started_at":  bot["started_at"].isoformat(),
            "trades_today": strategy.trades_today if strategy else 0,
            "max_trades":   strategy.max_trades_per_day if strategy else 0,
            "ws_connected": bot["ws_manager"]._connected if bot.get("ws_manager") else False,
        }

    return JsonResponse({
        "success":        True,
        "is_bot_running": is_alive,
        "details":        info,
    })