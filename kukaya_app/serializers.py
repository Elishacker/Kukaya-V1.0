from rest_framework import serializers # type: ignore
from django.core.files.base import ContentFile # type: ignore
from django.utils import timezone # type: ignore
from django.db import transaction # type: ignore
from django.db.models import Q # type: ignore
import base64, json

from .models import User, Apartment, ApartmentImage, Booking, Payment

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB per image
MAX_UPLOAD_IMAGES = 5


# --------------------------
# USER SERIALIZER
# --------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone', 'role']


# --------------------------
# APARTMENT IMAGE SERIALIZER
# --------------------------
class ApartmentImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ApartmentImage
        fields = ['id', 'image', 'image_url', 'uploaded_at']
        read_only_fields = ['id', 'image_url', 'uploaded_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


# --------------------------
# APARTMENT SERIALIZER
# --------------------------
class ApartmentSerializer(serializers.ModelSerializer):
    owner_phone = serializers.CharField(source='owner.phone', read_only=True)
    images = ApartmentImageSerializer(many=True, read_only=True)

    # Accept base64 strings for uploaded images (write-only)
    uploaded_images = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True
    )

    # Allow flexible input (string or list) for offers and rooms_per_floor
    offers = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )

    rooms_per_floor = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = Apartment
        fields = [
            'id', 'name', 'details', 'location', 'price', 'category',
            'owner', 'owner_phone', 'images', 'uploaded_images',
            'is_active', 'service_type', 'num_apartments', 'num_rooms',
            'num_floors', 'rooms_per_floor', 'offers', 'nearby_locations',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at', 'owner_phone']

    def validate_price(self, value):
        # Extra safety: ensure non-negative and reasonable max
        if value is None:
            raise serializers.ValidationError("Price is required.")
        if value < 0:
            raise serializers.ValidationError("Price must be a non-negative value.")
        return value

    def validate(self, attrs):
        # Normalize absent service_type to instance value on update
        service_type = attrs.get('service_type', getattr(self.instance, 'service_type', None))
        errors = {}

        if service_type == 'standalone':
            if not attrs.get('num_apartments') and not attrs.get('num_rooms') and not getattr(self.instance, 'num_apartments', None):
                errors['num_apartments'] = "num_apartments or num_rooms is required for standalone."
        elif service_type == 'highrise':
            if not attrs.get('num_floors') and not getattr(self.instance, 'num_floors', None):
                errors['num_floors'] = "num_floors is required for highrise."
            if not attrs.get('rooms_per_floor') and not getattr(self.instance, 'rooms_per_floor', None):
                errors['rooms_per_floor'] = "rooms_per_floor is required for highrise."
        else:
            errors['service_type'] = 'service_type must be either "standalone" or "highrise".'

        category = attrs.get('category', getattr(self.instance, 'category', None))
        if category and category not in ['apartment', 'hotel', 'lodge', 'office']:
            errors['category'] = 'category must be one of: apartment, hotel, lodge, office.'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def _decode_base64_image(self, b64_string):
        """
        Decode a base64 image string. Accepts strings that may include a data:<mime>;base64, prefix.
        Returns ContentFile or raises serializers.ValidationError.
        """
        if not isinstance(b64_string, str) or not b64_string.strip():
            raise serializers.ValidationError("Invalid image data provided.")

        # strip data:...;base64, prefix if present
        if 'base64,' in b64_string:
            b64_string = b64_string.split('base64,', 1)[1]

        try:
            decoded = base64.b64decode(b64_string)
        except Exception:
            raise serializers.ValidationError("Could not decode base64 image.")

        if len(decoded) > MAX_IMAGE_BYTES:
            raise serializers.ValidationError(f"Image too large. Max {MAX_IMAGE_BYTES} bytes allowed.")

        # Derive a filename (png fallback)
        name = f"img_{timezone.now().timestamp()}.png"
        return ContentFile(decoded, name=name)

    def to_internal_value(self, data):
        # Support stringified JSON fields for dynamic inputs
        data = data.copy()

        dynamic = data.pop('dynamic_fields', {})
        if isinstance(dynamic, str):
            try:
                dynamic = json.loads(dynamic)
            except Exception:
                dynamic = {}
        if isinstance(dynamic, dict):
            data.update(dynamic)

        # rooms_per_floor: accept CSV string or list (string -> list of ints)
        if "rooms_per_floor" in data:
            rpf = data.get("rooms_per_floor")
            if isinstance(rpf, str):
                data["rooms_per_floor"] = [int(x.strip()) for x in rpf.split(",") if x.strip().isdigit()]
            elif isinstance(rpf, list):
                # ensure ints
                data["rooms_per_floor"] = [int(x) for x in rpf]
            else:
                data["rooms_per_floor"] = []

        # nearby_locations: accept CSV string
        if "nearby_locations" in data and isinstance(data["nearby_locations"], str):
            data["nearby_locations"] = [x.strip() for x in data["nearby_locations"].split(",") if x.strip()]

        # offers: accept JSON string
        if "offers" in data and isinstance(data["offers"], str):
            try:
                data["offers"] = json.loads(data["offers"])
            except Exception:
                data["offers"] = []

        return super().to_internal_value(data)

    @transaction.atomic
    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])[:MAX_UPLOAD_IMAGES]
        # convert rooms_per_floor list to string for model storage
        if 'rooms_per_floor' in validated_data and isinstance(validated_data['rooms_per_floor'], list):
            validated_data['rooms_per_floor'] = ','.join(map(str, validated_data['rooms_per_floor']))

        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user:
            validated_data['owner'] = user

        apartment = Apartment.objects.create(**validated_data)

        # Save images
        for b64 in uploaded_images:
            if b64:
                content = self._decode_base64_image(b64)
                ApartmentImage.objects.create(apartment=apartment, image=content)

        return apartment

    @transaction.atomic
    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        if 'rooms_per_floor' in validated_data and isinstance(validated_data['rooms_per_floor'], list):
            validated_data['rooms_per_floor'] = ','.join(map(str, validated_data['rooms_per_floor']))

        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        # Optionally append new images (respecting MAX_UPLOAD_IMAGES)
        existing_count = instance.images.count()
        space_left = max(0, MAX_UPLOAD_IMAGES - existing_count)
        for b64 in (uploaded_images[:space_left] if uploaded_images else []):
            if b64:
                content = self._decode_base64_image(b64)
                ApartmentImage.objects.create(apartment=instance, image=content)
        return instance

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # convert stored CSV rooms_per_floor back to list
        value = getattr(instance, 'rooms_per_floor', '')
        ret['rooms_per_floor'] = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()] if value else []
        return ret


# --------------------------
# BOOKING SERIALIZER
# --------------------------
class BookingSerializer(serializers.ModelSerializer):
    apartment_name = serializers.CharField(source='apartment.name', read_only=True)
    location = serializers.CharField(source='apartment.location', read_only=True)
    price = serializers.DecimalField(source='apartment.price', max_digits=12, decimal_places=2, read_only=True)
    owner_phone = serializers.CharField(source='apartment.owner.phone', read_only=True)
    category = serializers.CharField(source='apartment.category', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'customer', 'apartment', 'apartment_name', 'location',
            'price', 'owner_phone', 'category', 'status', 'check_in',
            'check_out', 'rooms', 'notes', 'created_at',
        ]
        read_only_fields = ['customer', 'created_at', 'status']

    def validate(self, attrs):
        # Extract check_in/check_out from incoming attrs or instance for updates
        check_in = attrs.get('check_in', getattr(self.instance, 'check_in', None))
        check_out = attrs.get('check_out', getattr(self.instance, 'check_out', None))
        apartment = attrs.get('apartment', getattr(self.instance, 'apartment', None))

        if check_in and check_out:
            if check_out <= check_in:
                raise serializers.ValidationError({"check_out": "check_out must be after check_in."})

        # If apartment and dates provided, check for overlap with existing confirmed/pending bookings
        if apartment and check_in and check_out:
            overlapping = Booking.objects.filter(
                apartment=apartment,
                status__in=['pending', 'confirmed'],
                check_in__lt=check_out,
                check_out__gt=check_in
            )
            # exclude self for updates
            if self.instance:
                overlapping = overlapping.exclude(id=self.instance.id)
            if overlapping.exists():
                raise serializers.ValidationError("Apartment already booked for the selected dates.")

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user:
            validated_data['customer'] = user
        return super().create(validated_data)


# --------------------------
# PAYMENT SERIALIZER
# --------------------------
class PaymentSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(source='booking.id', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'phone', 'apartment_name', 'rooms', 'payment_method',
            'total_amount', 'days_booked', 'booking', 'booking_id', 'created_at'
        ]
        read_only_fields = ['created_at', 'booking_id']

    def validate_payment_method(self, value):
        if value not in ["mobile", "bank"]:
            raise serializers.ValidationError("Payment method must be either 'mobile' or 'bank'.")
        return value

    def validate_total_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("total_amount must be positive.")
        return value

    def validate(self, attrs):
        # Ensure booking exists if provided and that amounts are consistent (optional)
        booking = attrs.get('booking')
        if booking and not Booking.objects.filter(pk=booking.id).exists():
            raise serializers.ValidationError({"booking": "Provided booking does not exist."})
        return attrs
