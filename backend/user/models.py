from django.db import models
from django.contrib.auth.models import AbstractUser
from .managers import UserManager
from django.conf import settings


class User(AbstractUser):

    username = None

    ROLE_CHOICES = (
        ("ADMIN", "Admin"),
        ("TRADER", "Trader"),
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    mobile_number = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="TRADER")
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class AngelOneCredentials(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="angelone_account"
    )

    angel_api_key = models.CharField(max_length=200)
    angel_client_code = models.CharField(max_length=50, unique=True)
    angel_password = models.CharField(max_length=4)
    angel_totp_secret = models.CharField(max_length=250)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.angel_client_code}"


class OptionOrder(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("OPEN", "Open"),
        ("CLOSED", "Closed"),
        ("TARGET_HIT", "Target Hit"),
        ("STOPLOSS_HIT", "Stoploss Hit"),
        ("REJECTED", "Rejected"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="option_orders"
    )
    strategy_name = models.CharField(max_length=200, db_index=True)
    order_id = models.CharField(max_length=100, blank=True, null=True)
    symbol = models.CharField(max_length=100)
    full_symbol = models.CharField(max_length=200)
    qty = models.IntegerField(default=0)
    action = models.CharField(max_length=20)
    side = models.IntegerField(default=1)
    ordertype = models.CharField(max_length=50, default="ROBO")
    productType = models.CharField(max_length=50, default="BO")
    broker = models.CharField(max_length=50, default="angelone")
    type_of_stock = models.CharField(max_length=50, default="OPTION")
    entry_price = models.FloatField(default=0)
    exit_price = models.FloatField(null=True, blank=True)
    stopLoss = models.FloatField(default=0)
    takeProfit = models.FloatField(default=0)
    pnl = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    time_frame = models.IntegerField(default=1)
    active = models.BooleanField(default=True)
    order_details = models.JSONField(null=True, blank=True)
    api_response = models.JSONField(null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_symbol} - {self.order_id}"


class SectorMomentumBreakoutConfig(models.Model):

    EXPIRY_CHOICES = (
        ("current_month", "Current Month"),
        ("next_month", "Next Month"),
        ("far_month", "Far Month"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sector_momentum_configs"
    )

    strategy_name = models.CharField(
        max_length=200,
        default="Sector Momentum Breakout"
    )

    broker = models.CharField(max_length=50, default="angelone")

    expiry_date = models.CharField(
        max_length=50,
        choices=EXPIRY_CHOICES,
        default="current_month"
    )

    strike_price = models.IntegerField(default=1)
    entry_time = models.TimeField()
    exit_time = models.TimeField()

    trades_per_day = models.IntegerField(default=5)
    fund_allocation = models.FloatField(default=100000)
    target_percentage = models.FloatField(default=5)
    stoploss_percentage = models.FloatField(default=2)
    volume_multiplier = models.FloatField(default=3)
    limit_multiplier = models.FloatField(default=1)
    sectors_scan = models.IntegerField(default=3)
    stocks_scan = models.IntegerField(default=3)
    is_active = models.BooleanField(default=True)
    is_bot_running = models.BooleanField(default=False)

    # --- Phase time overrides (optional per-config) ---
    # If null, strategy engine uses its class-level defaults
    phase1_start_time = models.TimeField(null=True, blank=True)
    phase1_end_time = models.TimeField(null=True, blank=True)
    phase2_start_time = models.TimeField(null=True, blank=True)
    phase2_end_time = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "strategy_name")

    def __str__(self):
        return f"{self.user.email} - {self.strategy_name}"