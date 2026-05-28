from django.shortcuts import render
from .models import User
from django.views import View
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt


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
        
