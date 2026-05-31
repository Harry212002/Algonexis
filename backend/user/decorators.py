from functools import wraps
from django.http import JsonResponse
from rest_framework_simplejwt.tokens import AccessToken
from .models import User


def role_required(roles=None):

    if roles and not isinstance(roles, list):
        roles = [roles]

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            auth_header = request.headers.get("Authorization")

            if not auth_header:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Authorization header missing"
                    },
                    status=401
                )

            try:
                token = auth_header.split(" ")[1]

                payload = AccessToken(token)

                user = User.objects.get(id=payload["user_id"])

                request.user = user

                if roles and user.role not in roles:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": "Access forbidden"
                        },
                        status=403
                    )

                return view_func(request, *args, **kwargs)

            except User.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "User not found"
                    },
                    status=401
                )

            except Exception:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Invalid or expired token"
                    },
                    status=401
                )

        return wrapper

    return decorator