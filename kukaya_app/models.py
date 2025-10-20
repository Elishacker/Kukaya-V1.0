from django.db import models # type: ignore
from django.contrib.auth.models import AbstractUser, BaseUserManager # type: ignore
from django.utils import timezone # type: ignore
import random

# ====================================================
#  CUSTOM USER MANAGER
# ====================================================

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
        """Create and save a superuser with the given phone and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(phone, password, **extra_fields)


# ====================================================
#  CUSTOM USER MODEL
# ====================================================

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


# ====================================================
#  APARTMENT MODEL
# ====================================================

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
    """Represents an apartment, hotel room, or office listing."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="apartments")
    name = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    image = models.ImageField(
        upload_to="apartments/", blank=True, null=True, help_text="Main display image"
    )
    is_active = models.BooleanField(default=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="apartment")
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES, default="standalone")

    # Standalone fields
    num_apartments = models.PositiveIntegerField(null=True, blank=True)
    apartment_names = models.TextField(blank=True, null=True, help_text="Comma-separated apartment names")
    num_rooms = models.PositiveIntegerField(null=True, blank=True)

    # Ghorofa fields
    num_floors = models.PositiveIntegerField(null=True, blank=True)
    rooms_per_floor = models.TextField(blank=True, null=True, help_text="Comma-separated room counts per floor")

    # Extra offers/features (JSON)
    offers = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.category} ({self.owner.phone})"

    # ===========================================================
    #  HELPER METHODS
    # ===========================================================
    @property
    def image_url(self):
        """Return full URL for the main image."""
        try:
            return self.image.url if self.image else None
        except ValueError:
            return None

    def get_apartment_names_list(self):
        """Return apartment names as list."""
        if self.apartment_names:
            return [x.strip() for x in self.apartment_names.split(",") if x.strip()]
        return []

    def get_rooms_per_floor_list(self):
        """Return room numbers per floor as list of ints."""
        if self.rooms_per_floor:
            return [
                int(x.strip())
                for x in self.rooms_per_floor.split(",")
                if x.strip().isdigit()
            ]
        return []


# ====================================================
#  APARTMENT IMAGE MODEL
# ====================================================

class ApartmentImage(models.Model):
    apartment = models.ForeignKey(
        Apartment, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="apartments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Apartment Image"
        verbose_name_plural = "Apartment Images"

    def __str__(self):
        return f"Image for {self.apartment.name}"


# ====================================================
#  BOOKING MODEL
# ====================================================

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
    rooms = models.PositiveIntegerField(default=1)  # new
    notes = models.TextField(blank=True, null=True)  # new
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.phone} → {self.apartment.name} [{self.status}]"



# ====================================================
#  PHONE OTP MODEL
# ====================================================

class PhoneOTP(models.Model):
    phone = models.CharField(max_length=15, unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    expires_in = models.IntegerField(default=5)  # minutes

    def __str__(self):
        return f"{self.phone} -> {self.otp} ({'✔' if self.verified else '✖'})"

    # OTP Logic
    def generate_otp(self, length=4):
        """Generate a new numeric OTP."""
        length = 6 if length not in [4, 6] else length
        self.otp = "".join([str(random.randint(0, 9)) for _ in range(length)])
        self.attempts = 0
        self.verified = False
        self.created_at = timezone.now()
        self.save()
        return self.otp

    def verify_otp(self, otp_input):
        """Validate OTP input and handle attempts/expiry."""
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
        """Check if OTP is expired."""
        elapsed = (timezone.now() - self.created_at).total_seconds()
        return elapsed > self.expires_in * 60
