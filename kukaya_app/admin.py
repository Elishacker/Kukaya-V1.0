from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Apartment, Booking, PhoneOTP, Payment

# ----------------------
# Custom User Admin
# ----------------------
class UserAdmin(BaseUserAdmin):
    list_display = ('phone', 'role', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('phone',)
    ordering = ('phone',)
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Permissions', {'fields': ('role', 'is_staff', 'is_superuser', 'is_active')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'role', 'password1', 'password2', 'is_staff', 'is_superuser', 'is_active'),
        }),
    )

admin.site.register(User, UserAdmin)
admin.site.register(Apartment)
admin.site.register(Booking)
admin.site.register(PhoneOTP)
admin.site.register(Payment)
