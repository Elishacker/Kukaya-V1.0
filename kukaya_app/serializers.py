from rest_framework import serializers # type: ignore
from .models import User, Apartment, ApartmentImage, Booking
from django.core.files.base import ContentFile # type: ignore
from django.utils import timezone # type: ignore
import base64


# ===========================================================
# USER SERIALIZER
# ===========================================================
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone', 'role']


# ===========================================================
# APARTMENT IMAGE SERIALIZER
# ===========================================================
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


# ===========================================================
# APARTMENT SERIALIZER
# ===========================================================
class ApartmentSerializer(serializers.ModelSerializer):
    owner_phone = serializers.CharField(source='owner.phone', read_only=True)
    images = ApartmentImageSerializer(many=True, read_only=True)

    # JSON field for offers
    offers = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )

    # Base64 image upload
    uploaded_images = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of Base64 encoded images"
    )

    class Meta:
        model = Apartment
        fields = [
            'id',
            'name',
            'details',
            'location',
            'price',
            'category',
            'owner',
            'owner_phone',
            'images',
            'uploaded_images',
            'is_active',
            'service_type',
            'num_apartments',
            'apartment_names',
            'num_rooms',
            'num_floors',
            'rooms_per_floor',
            'offers',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']

    # -----------------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------------
    def validate(self, attrs):
        service_type = attrs.get('service_type')

        if service_type == 'standalone':
            required_fields = ['num_apartments', 'apartment_names', 'num_rooms']
        elif service_type == 'ghorofa':
            required_fields = ['num_floors', 'rooms_per_floor']
        else:
            raise serializers.ValidationError({
                'service_type': 'Must be either "standalone" or "ghorofa".'
            })

        errors = {}
        for field in required_fields:
            value = attrs.get(field)
            if value in [None, '']:
                errors[field] = f"{field} is required for service_type '{service_type}'."

        if errors:
            raise serializers.ValidationError(errors)

        # Category check
        if attrs.get('category') not in ['apartment', 'hotel', 'lodge', 'office']:
            raise serializers.ValidationError({
                'category': 'Category must be one of: apartment, hotel, lodge, office.'
            })

        return attrs

    # -----------------------------------------------------------
    # CREATE METHOD
    # -----------------------------------------------------------
    def create(self, validated_data):
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        uploaded_images = validated_data.pop('uploaded_images', [])

        # Assign owner
        validated_data['owner'] = user

        # Ensure comma-separated fields are clean
        if validated_data.get('apartment_names') and isinstance(validated_data['apartment_names'], str):
            validated_data['apartment_names'] = ','.join(
                [x.strip() for x in validated_data['apartment_names'].split(',') if x.strip()]
            )

        if validated_data.get('rooms_per_floor') and isinstance(validated_data['rooms_per_floor'], str):
            validated_data['rooms_per_floor'] = ','.join(
                [x.strip() for x in validated_data['rooms_per_floor'].split(',') if x.strip()]
            )

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


# ===========================================================
# BOOKING SERIALIZER
# ===========================================================
class BookingSerializer(serializers.ModelSerializer):
    apartment_name = serializers.CharField(source='apartment.name', read_only=True)
    location = serializers.CharField(source='apartment.location', read_only=True)
    price = serializers.DecimalField(source='apartment.price', max_digits=12, decimal_places=2, read_only=True)
    owner_phone = serializers.CharField(source='apartment.owner.phone', read_only=True)
    category = serializers.CharField(source='apartment.category', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'customer',
            'apartment',
            'apartment_name',
            'location',
            'price',
            'owner_phone',
            'category',
            'status',
            'check_in',
            'check_out',
            'rooms',   # added
            'notes',   # added
            'created_at',
        ]
        read_only_fields = ['customer', 'created_at', 'status']
