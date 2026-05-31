from django.shortcuts import render
from .models import User,AngelOneCredentials
from django.views import View
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import AccessToken
from .decorators import role_required


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