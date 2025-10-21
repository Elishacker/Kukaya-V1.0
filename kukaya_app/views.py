from rest_framework.decorators import api_view, permission_classes # type: ignore
from rest_framework.permissions import IsAuthenticated, AllowAny # type: ignore
from rest_framework.response import Response # type: ignore
from django.contrib.auth import authenticate, get_user_model, login # type: ignore
from django.contrib.auth import logout as django_logout # type: ignore
from django.db import transaction # type: ignore
from django.core.files.base import ContentFile # type: ignore
from django.utils import timezone # type: ignore
from .models import Apartment, Booking, PhoneOTP, ApartmentImage
from .serializers import (
    UserSerializer,
    ApartmentSerializer,
    BookingSerializer,
    ApartmentImageSerializer,
)
import random, base64, json

User = get_user_model()

#  REQUEST OTP
@api_view(["POST"])
@permission_classes([AllowAny])
def request_otp(request):
    phone = request.data.get("phone")
    if not phone:
        return Response({"ok": False, "error": "Phone number is required."}, status=400)

    otp = str(random.randint(1000, 9999))
    PhoneOTP.objects.update_or_create(phone=phone, defaults={"otp": otp, "verified": False})
    print(f"[DEV MODE] OTP for {phone}: {otp}")  # Remove in production!

    return Response({"ok": True, "message": "OTP sent successfully (dev mode)", "otp": otp})


#  VERIFY OTP & LOGIN / LOGOUT/ REGISTER
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):
    phone = request.data.get("phone")
    otp = request.data.get("otp")

    if not phone or not otp:
        return Response({"ok": False, "error": "Phone and OTP are required."}, status=400)

    try:
        otp_obj = PhoneOTP.objects.get(phone=phone)
    except PhoneOTP.DoesNotExist:
        return Response({"ok": False, "error": "OTP not found."}, status=404)

    if otp_obj.otp != otp:
        return Response({"ok": False, "error": "Invalid OTP."}, status=400)

    user, created = User.objects.get_or_create(phone=phone, defaults={"role": "customer"})
    otp_obj.verified = True
    otp_obj.save(update_fields=["verified"])

    login(request, user) 

    return Response({
        "ok": True,
        "user": UserSerializer(user).data,
        "created": created,
        "message": "Login successful."
    })

@api_view(['POST'])
def logout(request):
    django_logout(request) 
    return Response({"ok": True})


#  ADMIN LOGIN
@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    phone = request.data.get("phone")
    password = request.data.get("password")

    if not phone or not password:
        return Response({"ok": False, "error": "Phone and password are required."}, status=400)

    user = authenticate(request, phone=phone, password=password)
    if not user or user.role != "admin":
        return Response({"ok": False, "error": "Invalid admin credentials."}, status=403)

    login(request, user)

    return Response({"ok": True, "user": UserSerializer(user).data, "message": "Admin login successful."})


#  ADD APARTMENT
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def add_apartment(request):
    user = request.user
    if user.role not in ["owner", "admin"]:
        return Response({"ok": False, "error": "Permission denied."}, status=403)

    data = request.data.copy()

    # Convert price_amount to float
    try:
        data["price"] = float(data.pop("price_amount", 0))
    except (ValueError, TypeError):
        return Response({"ok": False, "error": "Invalid price format."}, status=400)

    # Parse offers and dynamic fields safely
    if isinstance(data.get("offers"), str):
        try:
            data["offers"] = json.loads(data["offers"])
        except Exception:
            data["offers"] = []

    dynamic_fields = data.pop("dynamic_fields", {})
    if isinstance(dynamic_fields, str):
        try:
            dynamic_fields = json.loads(dynamic_fields)
        except Exception:
            dynamic_fields = {}
    data.update(dynamic_fields)

    # Assign owner
    data["owner"] = user.id

    serializer = ApartmentSerializer(data=data, context={"request": request})
    if not serializer.is_valid():
        return Response({"ok": False, "errors": serializer.errors}, status=400)

    apartment = serializer.save()

    # Handle Base64 images
    images_data = data.get("images", [])
    if isinstance(images_data, str):
        try:
            images_data = json.loads(images_data)
        except Exception:
            images_data = []

    for img_str in images_data[:5]:
        if img_str and "base64," in img_str:
            img_str = img_str.split("base64,")[1]
            try:
                img_file = ContentFile(
                    base64.b64decode(img_str),
                    name=f"{apartment.name}_{timezone.now().timestamp()}.png",
                )
                ApartmentImage.objects.create(apartment=apartment, image=img_file)
            except Exception as e:
                print(f"Error decoding image: {e}")

    apartment_data = ApartmentSerializer(apartment, context={"request": request}).data
    apartment_data["images"] = ApartmentImageSerializer(
        apartment.images.all(), many=True, context={"request": request}
    ).data

    return Response({
        "ok": True,
        "apartment": apartment_data,
        "message": "Apartment added successfully."
    })


#  EDIT APARTMENT
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def edit_apartment(request, apartment_id):
    user = request.user
    try:
        apartment = Apartment.objects.get(id=apartment_id)
    except Apartment.DoesNotExist:
        return Response({"ok": False, "error": "Apartment not found."}, status=404)

    if user.role == "owner" and apartment.owner != user:
        return Response({"ok": False, "error": "Permission denied."}, status=403)

    data = request.data.copy()
    price_amount = data.pop("price_amount", None)
    if price_amount is not None:
        try:
            data["price"] = float(price_amount)
        except (ValueError, TypeError):
            return Response({"ok": False, "error": "Invalid price format."}, status=400)

    dynamic_fields = data.pop("dynamic_fields", {})
    if isinstance(dynamic_fields, str):
        try:
            dynamic_fields = json.loads(dynamic_fields)
        except Exception:
            dynamic_fields = {}
    data.update(dynamic_fields)

    serializer = ApartmentSerializer(apartment, data=data, partial=True, context={"request": request})
    if serializer.is_valid():
        updated = serializer.save()
        return Response({"ok": True, "apartment": ApartmentSerializer(updated, context={"request": request}).data})
    return Response({"ok": False, "errors": serializer.errors}, status=400)


#  OWNER APARTMENTS
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def owner_apartments(request):
    user = request.user
    if user.role not in ["owner", "admin"]:
        return Response({"ok": False, "error": "Permission denied."}, status=403)

    apartments = Apartment.objects.filter(owner=user).prefetch_related("images").order_by("-created_at")
    serializer = ApartmentSerializer(apartments, many=True, context={"request": request})
    return Response({"ok": True, "apartments": serializer.data})


#  LIST APARTMENTS
@api_view(["GET"])
@permission_classes([AllowAny])
def list_apartments(request):
    category = request.GET.get("category", "All").lower()
    apartments = Apartment.objects.filter(is_active=True)

    filters = {
        "apartments": "apartment",
        "hotels": "hotel",
        "lodge": "lodge",
        "offices": "office",
    }
    if category in filters:
        apartments = apartments.filter(category=filters[category])

    apartments = apartments.prefetch_related("images").select_related("owner").order_by("-created_at")
    serializer = ApartmentSerializer(apartments, many=True, context={"request": request})
    return Response({"ok": True, "apartments": serializer.data})


#  BOOK APARTMENT
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def book_apartment(request):
    user = request.user
    apartment_id = request.data.get("apartment")

    if not apartment_id:
        return Response({"ok": False, "error": "Apartment ID is required."}, status=400)

    try:
        apartment = Apartment.objects.get(id=apartment_id)
    except Apartment.DoesNotExist:
        return Response({"ok": False, "error": "Apartment not found."}, status=404)

    booking = Booking.objects.create(customer=user, apartment=apartment)
    return Response({"ok": True, "booking": BookingSerializer(booking).data})


#  BOOKING HISTORY
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_history(request):
    bookings = Booking.objects.filter(customer=request.user).select_related("apartment").order_by("-created_at")
    serializer = BookingSerializer(bookings, many=True, context={"request": request})
    return Response({"ok": True, "bookings": serializer.data})


# ADMIN: LIST USERS
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_list_users(request):
    if request.user.role != "admin":
        return Response({"ok": False, "error": "Admin access required."}, status=403)
    users = User.objects.all().order_by("-id")
    serializer = UserSerializer(users, many=True)
    return Response({"ok": True, "users": serializer.data})


#  ADMIN: LIST ALL APARTMENTS
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_list_apartments(request):
    if request.user.role != "admin":
        return Response({"ok": False, "error": "Admin access required."}, status=403)
    apartments = Apartment.objects.all().prefetch_related("images").select_related("owner").order_by("-created_at")
    serializer = ApartmentSerializer(apartments, many=True, context={"request": request})
    return Response({"ok": True, "apartments": serializer.data})


#  USER PROFILE
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_profile(request):
    user = request.user
    serializer = UserSerializer(user)
    return Response({"ok": True, "user": serializer.data})


#  UPDATE PROFILE
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    serializer = UserSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({"ok": True, "user": serializer.data, "message": "Profile updated successfully."})
    return Response({"ok": False, "errors": serializer.errors}, status=400)
