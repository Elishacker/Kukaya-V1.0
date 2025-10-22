from django.urls import path # type: ignore
from . import views

app_name = "kukaya_app"  # Optional: namespacing for reverse URL lookups

urlpatterns = [
    # Customer / Owner Authentication
    path('auth/request-otp/', views.request_otp, name='request-otp'),
    path('auth/verify-otp/', views.verify_otp, name='verify-otp'),
    path('auth/profile/', views.user_profile, name='profile'),
    path('auth/profile/update/', views.update_profile, name='update-profile'),
    path('auth/logout/', views.logout, name='logout'),

    # Admin Authentication
    path('auth/admin-login/', views.admin_login, name='admin-login'),


    # Apartments Lists (Public)
    path('apartments/lists/', views.list_apartments, name='list-apartments'),

    # Apartments (Owner / Admin)
    path('apartments/owner/', views.owner_apartments, name='owner-apartments'),  # only authenticated owner
    path('apartments/add/', views.add_apartment, name='add-apartment'),
    path('apartments/edit/<int:apartment_id>/', views.edit_apartment, name='edit-apartment'),

    # Booking
    path('bookings/add/', views.book_apartment, name='book-apartment'),
    path('bookings/history/', views.booking_history, name='booking-history'),
    path('bookings/payments/', views.make_payment, name='payment'),

    # Admin Endpoints
    path('admin/users/', views.admin_list_users, name='admin-list-users'),
    path('admin/apartments/', views.admin_list_apartments, name='admin-list-apartments'),
]
