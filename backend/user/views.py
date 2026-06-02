from django.shortcuts import render
from .models import User,AngelOneCredentials,SectorMomentumBreakoutConfig
from django.views import View
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import AccessToken
from .decorators import role_required
from datetime import datetime

@csrf_exempt
def register(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "error":"Invalid Request Method"
            },
            status=405
        )
        
    try:
        
        data=json.loads(request.body)
    
        first_name=data.get("first_name")
        last_name=data.get("last_name")
        mobile_number=data.get("mobile_number")
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
    
        if not all([first_name,last_name,mobile_number,email,password,confirm_password]):
            return JsonResponse(
                {
                    "error":"All feilds are required"
                },
                status=400
            )
    
        if password != confirm_password:
            return JsonResponse(
                {
                    "error":"Password do not match"
                 },
                status=400
            )
        
        existing_user=User.objects.filter(email=email).first()
    
        if existing_user:
            return JsonResponse(
                {
                    "success":False,
                    "message":"User already registered with this email"
                },
                status=400
            )
    
        existing_mobile = User.objects.filter(
                mobile_number=mobile_number
            ).first()

        if existing_mobile:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Mobile number already registered"
                },
                status=400
            )
            
        user=User.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            mobile_number=mobile_number,
            email=email,
            password=password,
            role="TRADER",
            is_active=True
        )
        
        return JsonResponse(
            {
                "success":True,
                "message": "User registered successfully",
                "user_id": user.id
            },
            status=201
        )
        
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid JSON data"
            },
            status=400
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=500
        )
    
@csrf_exempt    
def login(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "error":"Invalid request method"
            },
            status=405  
        )
        
    try:
        
        data=json.loads(request.body)
        email=data.get("email")
        password=data.get("password")
        
        if not email or not password:
            return JsonResponse(
                {
                    "success":False,
                    "message":"email and password are required"
                },
                status=400
            )
            
        
        user=User.objects.filter(email=email).first()
        
        if not user:
            return JsonResponse(
                {
                    "success":False,
                    "message":"Invalid Email or Password"
                },
                status=400
            )
            
        if not user.check_password(password):
            return JsonResponse(
                {
                    "success":False,
                    "message":"Invalid Password"
                },
                status=401
            )
            
        access_token=AccessToken.for_user(user)
        
        return JsonResponse(
            {
                "success":True,
                "message":"Login successfully",
                "access_token":str(access_token),
                "user":{
                    
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "role": user.role
                }
            },
            status=200
        )
        
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid JSON"
            },
            status=400
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=500
        )
        
@csrf_exempt
@role_required("TRADER")      
def save_angelone_credentials(request):
    
    if request.method not in ["POST", "PUT"]:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method"
            },
            status=405
        )
        
    try:
        
        data=json.loads(request.body)
        
        angel_api_key=data.get("angel_api_key")
        angel_client_code=data.get("angel_client_code")
        angel_password=data.get("angel_password")
        angel_totp_secret=data.get("angel_totp_secret")
        
        if not all([angel_api_key,angel_client_code,angel_password,angel_totp_secret]):
            return JsonResponse(
                {
                    "success":False,
                    "message":"All fields are required"
                },
                status=400
            )
            
        user=request.user
        
        if AngelOneCredentials.objects.filter(user=user).exists():
            return JsonResponse(
                {
                    "success":False,
                    "message":"Angel One account already exists"
                },
                status=400
            )
        
        credential, created = AngelOneCredentials.objects.update_or_create(
            user=user,
            defaults={
                "angel_api_key": angel_api_key,
                "angel_client_code": angel_client_code,
                "angel_password": angel_password,
                "angel_totp_secret": angel_totp_secret,
                "is_active": True
            }
        )

        
        
        return JsonResponse(
            {
                "success": True,
                "message": (
                    "Angel One credentials added successfully"
                    if created
                    else "Angel One credentials updated successfully"
                ),
                "data": {
                    "id": credential.id,
                    "client_code": credential.angel_client_code,
                    "is_active": credential.is_active
                }
            },
            status=201 if created else 200
        )

        
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid JSON data"
            },
            status=400
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=500
        )
        

@csrf_exempt
@role_required("TRADER")
def get_angelone_credentials(request):

    if request.method != "GET":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method"
            },
            status=405
        )

    try:
        user = request.user

        credential = AngelOneCredentials.objects.filter(
            user=user
        ).first()

        if not credential:
            return JsonResponse(
                {
                    "success": False,
                    "message": "No Angel One credentials found"
                },
                status=404
            )

        return JsonResponse(
            {
                "success": True,
                "data": {
                    "id": credential.id,
                    "angel_api_key": credential.angel_api_key,
                    "angel_client_code": credential.angel_client_code,
                    "angel_password": credential.angel_password,
                    "angel_totp_secret": credential.angel_totp_secret,
                    "is_active": credential.is_active
                }
            },
            status=200
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=500
        )
        
    
@csrf_exempt
@role_required("TRADER")
def save_sector_momentum_config(request):
    
    if request.method not in ["POST","PUT"]:
        return JsonResponse(
            {
                "success":False,
                "message":"Invalida Request Mehtod"
            },
            status=405
        )
        
    try:
        
        data=json.loads(request.body)
        
        config,created=SectorMomentumBreakoutConfig.objects.update_or_create(
            user=request.user,
            strategy_name="Sector Momentum Breakout",
            defaults={

                "broker": data.get("broker"),

                "expiry_date": data.get("expiry_date"),

                "strike_price": int(data.get("strike_price", 1)),

                "entry_time": datetime.strptime(
                    data.get("entry_time"),
                    "%H:%M"
                ).time(),

                "exit_time": datetime.strptime(
                    data.get("exit_time"),
                    "%H:%M"
                ).time(),

                "trades_per_day": int(data.get("trades_per_day", 5)),

                "fund_allocation": float(
                    data.get("fund_allocation", 100000)
                ),

                "target_percentage": float(
                    data.get("target_percentage", 5)
                ),

                "stoploss_percentage": float(
                    data.get("stoploss_percentage", 2)
                ),

                "volume_multiplier": float(
                    data.get("volume_multiplier", 3)
                ),

                "limit_multiplier": float(
                    data.get("limit_multiplier", 1)
                ),

                "sectors_scan": int(
                    data.get("sectors_scan", 3)
                ),

                "stocks_scan": int(
                    data.get("stocks_scan", 3)
                ),
            }
        )
        
        
        return JsonResponse(
            {
                "success":True,
                "message":"Configuration Saved",
                "config_id": config.id
            }
        )
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)
        
        
@csrf_exempt
@role_required("TRADER")
def get_sector_momentum_config(request):
    
    try:
        
        config=SectorMomentumBreakoutConfig.objects.get(
            user=request.user,
            strategy_name="Sector Momentum Breakout"
        )
        
        return JsonResponse({
            "success": True,
            "data": {
                "broker": config.broker,
                "expiry_date": config.expiry_date,
                "strike_price": config.strike_price,
                "entry_time": config.entry_time.strftime("%H:%M"),
                "exit_time": config.exit_time.strftime("%H:%M"),
                "trades_per_day": config.trades_per_day,
                "fund_allocation": config.fund_allocation,
                "target_percentage": config.target_percentage,
                "stoploss_percentage": config.stoploss_percentage,
                "volume_multiplier": config.volume_multiplier,
                "limit_multiplier": config.limit_multiplier,
                "sectors_scan": config.sectors_scan,
                "is_bot_running": config.is_bot_running,
                "stocks_scan": config.stocks_scan
            }
        })
        
    except SectorMomentumBreakoutConfig.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Config not found"
        }, status=404)
        
        
@csrf_exempt
@role_required("TRADER")
def toggle_sector_momentum_bot(request):

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method"
            },
            status=405
        )
        
    try:
        
        data=json.loads(request.body)
        
        is_bot_running=data.get("is_bot_running")
        
        config=SectorMomentumBreakoutConfig.objects.get(
            user=request.user,
            strategy_name="Sector Momentum Breakout"          
        )
        
        config.is_bot_running = bool(is_bot_running)
        config.save(update_fields=["is_bot_running"])

        return JsonResponse(
            {
                "success": True,
                "message": (
                    "Bot started successfully"
                    if config.is_bot_running
                    else "Bot stopped successfully"
                ),
                "data": {
                    "is_bot_running": config.is_bot_running
                }
            }
        )

    except SectorMomentumBreakoutConfig.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "message": "Configuration not found. Please save configuration first."
            },
            status=404
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=500
        )