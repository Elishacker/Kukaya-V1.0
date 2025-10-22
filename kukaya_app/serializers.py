from rest_framework import serializers
from .models import User, Apartment, ApartmentImage, Booking, Payment
from django.core.files.base import ContentFile
from django.utils import timezone
import base64, json

# -----------------------------
# USER SERIALIZER
# -----------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone', 'role']


# -----------------------------
# APARTMENT IMAGE SERIALIZER
# -----------------------------
class ApartmentImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ApartmentImage
        fields = ['id', 'image', 'image_url', 'uploaded_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


# -----------------------------
# APARTMENT SERIALIZER
# -----------------------------
class ApartmentSerializer(serializers.ModelSerializer):
    owner_phone = serializers.CharField(source='owner.phone', read_only=True)
    images = ApartmentImageSerializer(many=True, read_only=True)

    uploaded_images = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )

    offers = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )

    rooms_per_floor = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
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
        read_only_fields = ['owner', 'created_at', 'updated_at']

    def validate(self, attrs):
        service_type = attrs.get('service_type')
        errors = {}

        if service_type == 'standalone':
            if not attrs.get('num_apartments') and not attrs.get('num_rooms'):
                errors['num_apartments'] = "num_apartments or num_rooms is required for standalone."
        elif service_type == 'ghorofa':
            if not attrs.get('num_floors'):
                errors['num_floors'] = "num_floors is required for ghorofa."
            if not attrs.get('rooms_per_floor'):
                errors['rooms_per_floor'] = "rooms_per_floor is required for ghorofa."
        else:
            errors['service_type'] = 'service_type must be either "standalone" or "ghorofa".'

        if attrs.get('category') not in ['apartment', 'hotel', 'lodge', 'office']:
            errors['category'] = 'category must be one of: apartment, hotel, lodge, office.'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def to_internal_value(self, data):
        dynamic = data.pop('dynamic_fields', {})
        if isinstance(dynamic, str):
            try:
                dynamic = json.loads(dynamic)
            except Exception:
                dynamic = {}
        data.update(dynamic)

        # Convert rooms_per_floor string to list
        if "rooms_per_floor" in data:
            if isinstance(data["rooms_per_floor"], str):
                data["rooms_per_floor"] = [
                    int(x.strip()) for x in data["rooms_per_floor"].split(",") if x.strip().isdigit()
                ]
            elif not isinstance(data["rooms_per_floor"], list):
                data["rooms_per_floor"] = []

        # Parse nearby_locations
        if "nearby_locations" in data and isinstance(data["nearby_locations"], str):
            data["nearby_locations"] = [x.strip() for x in data["nearby_locations"].split(",") if x.strip()]

        # Parse offers if string
        if "offers" in data and isinstance(data["offers"], str):
            try:
                data["offers"] = json.loads(data["offers"])
            except Exception:
                data["offers"] = []

        return super().to_internal_value(data)

    def create(self, validated_data):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        uploaded_images = validated_data.pop('uploaded_images', [])
        validated_data['owner'] = user

        if 'rooms_per_floor' in validated_data and isinstance(validated_data['rooms_per_floor'], list):
            validated_data['rooms_per_floor'] = ','.join(map(str, validated_data['rooms_per_floor']))

        apartment = Apartment.objects.create(**validated_data)

        # Save Base64 images
        for img_str in uploaded_images[:5]:
            if img_str:
                if "base64," in img_str:
                    img_str = img_str.split("base64,")[1]
                try:
                    img_file = ContentFile(
                        base64.b64decode(img_str),
                        name=f"{apartment.name}_{timezone.now().timestamp()}.png"
                    )
                    ApartmentImage.objects.create(apartment=apartment, image=img_file)
                except Exception as e:
                    print(f"Error decoding image: {e}")

        return apartment

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        value = getattr(instance, 'rooms_per_floor', '')
        ret['rooms_per_floor'] = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()] if value else []
        return ret


# -----------------------------
# BOOKING SERIALIZER
# -----------------------------
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


# -----------------------------
# PAYMENT SERIALIZER
# -----------------------------
class PaymentSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(source='booking.id', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'phone', 'apartment_name', 'rooms', 'payment_method',
            'total_amount', 'days_booked', 'booking', 'booking_id', 'created_at'
        ]
        read_only_fields = ['created_at']

    def validate_payment_method(self, value):
        if value not in ["mobile", "bank"]:
            raise serializers.ValidationError("Payment method must be either 'mobile' or 'bank'.")
        return value
