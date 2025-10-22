from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
import random

# ---------------------------
# CUSTOM USER MANAGER
# ---------------------------
class CustomUserManager(BaseUserManager):
    """Manager for custom user model using phone as username."""

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone number must be provided")
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "admin")

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(phone, password, **extra_fields)


# ---------------------------
# CUSTOM USER MODEL
# ---------------------------
class User(AbstractUser):
    ROLE_CHOICES = (
        ("customer", "Customer"),
        ("owner", "Owner"),
        ("admin", "Admin"),
    )

    username = None  # Disable default username
    phone = models.CharField(max_length=15, unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="customer")

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.phone} ({self.role})"


# ---------------------------
# APARTMENT MODEL
# ---------------------------
CATEGORY_CHOICES = [
    ("apartment", "Apartment"),
    ("hotel", "Hotel"),
    ("lodge", "Lodge"),
    ("office", "Office"),
]

SERVICE_CHOICES = [
    ("standalone", "Stand-alone"),
    ("ghorofa", "Ghorofa"),
]

class Apartment(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="apartments")
    name = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="apartment")
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES, default="standalone")

    # Standalone fields
    num_apartments = models.PositiveIntegerField(null=True, blank=True, help_text="Required if standalone")
    num_rooms = models.PositiveIntegerField(null=True, blank=True, help_text="Rooms per standalone unit")
    apartment_names = models.TextField(blank=True, null=True, help_text="Comma-separated apartment names")

    # Ghorofa fields
    num_floors = models.PositiveIntegerField(null=True, blank=True)
    rooms_per_floor = models.TextField(blank=True, null=True, help_text="Comma-separated room counts per floor")

    # Other dynamic fields
    nearby_locations = models.JSONField(default=list, blank=True, help_text="List of nearby landmarks")
    offers = models.JSONField(default=list, blank=True, help_text="List of offers/features")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.category} ({self.owner.phone})"

    # Helper methods
    def get_rooms_per_floor_list(self):
        if not self.rooms_per_floor:
            return []
        return [int(x.strip()) for x in self.rooms_per_floor.split(",") if x.strip().isdigit()]

    def get_apartment_names_list(self):
        if not self.apartment_names:
            return []
        return [x.strip() for x in self.apartment_names.split(",") if x.strip()]


# ---------------------------
# APARTMENT IMAGE MODEL
# ---------------------------
class ApartmentImage(models.Model):
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="apartments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Apartment Image"
        verbose_name_plural = "Apartment Images"

    def __str__(self):
        return f"Image for {self.apartment.name}"


# ---------------------------
# BOOKING MODEL
# ---------------------------
class Booking(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
    )

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE)
    check_in = models.DateField(null=True, blank=True)
    check_out = models.DateField(null=True, blank=True)
    rooms = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.phone} → {self.apartment.name} [{self.status}]"


# ---------------------------
# PHONE OTP MODEL
# ---------------------------
class PhoneOTP(models.Model):
    phone = models.CharField(max_length=15, unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    expires_in = models.IntegerField(default=5)  # minutes

    def __str__(self):
        return f"{self.phone} -> {self.otp} ({'✔' if self.verified else '✖'})"

    def generate_otp(self, length=4):
        length = 6 if length not in [4, 6] else length
        self.otp = "".join([str(random.randint(0, 9)) for _ in range(length)])
        self.attempts = 0
        self.verified = False
        self.created_at = timezone.now()
        self.save()
        return self.otp

    def verify_otp(self, otp_input):
        if self.is_expired():
            return False, "OTP expired"
        if self.attempts >= 5:
            return False, "Maximum attempts reached"
        self.attempts += 1
        if self.otp == otp_input:
            self.verified = True
            self.save()
            return True, "OTP verified successfully"
        self.save()
        return False, "Invalid OTP"

    def is_expired(self):
        elapsed = (timezone.now() - self.created_at).total_seconds()
        return elapsed > self.expires_in * 60


# ---------------------------
# PAYMENT MODEL
# ---------------------------
class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ("mobile", "Mobile Payment"),
        ("bank", "Bank Transfer"),
    )

    phone = models.CharField(max_length=15)  # Payer's phone number
    apartment_name = models.CharField(max_length=255)
    rooms = models.PositiveIntegerField(default=1)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    days_booked = models.PositiveIntegerField(default=1)

    # Optional link to Booking
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment by {self.phone} for {self.apartment_name} ({self.total_amount} Tzs)"
