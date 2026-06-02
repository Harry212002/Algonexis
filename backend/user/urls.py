from django.urls import path
from .views import *

urlpatterns=[
    
    path("register/",register,name="register"),
    path("login/",login,name="login"),
    path("angelone/credentials/",save_angelone_credentials,name="save_angelone_credentials"),
    path("angelone/credentials/get/",get_angelone_credentials,name="get_angelone_credentials"),
    
    
    
    path("sector-momentum/config/save/",save_sector_momentum_config,name="save_sector_momentum_config"),
    path("sector-momentum/config/",get_sector_momentum_config,name="get_sector_momentum_config"),
    path("sector-momentum/toggle/",toggle_sector_momentum_bot,name="toggle_sector_momentum_bot"),
]
