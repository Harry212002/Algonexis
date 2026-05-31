from django.db import models
from django.contrib.auth.models import AbstractUser
from .managers import UserManager
from django.conf import settings

# Create your models here.


class User(AbstractUser):
    
    username = None
    
    
    ROLE_CHOICES = (
        ("ADMIN","Admin"),
        ("TRADER","Trader"),
    )
    
    first_name=models.CharField(max_length=100)
    last_name=models.CharField(max_length=100)
    mobile_number=models.CharField(max_length=15,unique=True)
    email=models.EmailField(unique=True)
    role=models.CharField(max_length=20,choices=ROLE_CHOICES,default="TRADER")
    is_active=models.BooleanField(default=True)
    
    USERNAME_FIELD="email"
    REQUIRED_FIELDS=[]
    
    objects = UserManager()
    
    def __str__(self):
        return self.email
    
    
class AngelOneCredentials(models.Model):
    
    user=models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="angelone_account"
    )
    
    angel_api_key=models.CharField(max_length=200)
    angel_client_code=models.CharField(max_length=50,unique=True)
    angel_password=models.CharField(max_length=4)
    angel_totp_secret=models.CharField(max_length=250)
    
    is_active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.angel_client_code}"