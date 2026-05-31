from django.urls import path
from .views import *

urlpatterns=[
    
    path("register/",register,name="register"),
    path("login/",login,name="login"),
    path("angelone/credentials/",save_angelone_credentials,name="save_angelone_credentials"),
    path("angelone/credentials/get/",get_angelone_credentials,name="get_angelone_credentials"),
    
]
