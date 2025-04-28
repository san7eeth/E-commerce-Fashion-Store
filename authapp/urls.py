from django.urls import path
from authapp import views



urlpatterns = [
    # Authentication URLs
    path('login/', views.login_view, name='login'),  # Login page
    path('signin/', views.signin, name='signin'),  # Handle form submission
    path('logout/', views.logout_view, name='logout'),  # Logout
    path('resetpassword/', views.reset, name='reset'),  # Reset password page

    # Signup URLs
    path('brand_signup_page/', views.brand_signup_page, name='brand_signup_page'),  # Brand signup
    path('customersignup/', views.customer_signup, name='customer_signup'),  # Customer signup
    path('brandsignup/', views.brand_signup, name='brand_signup'),  # Brand signup

    # Home URLs
    path('brand/brandhome/', views.brandhome, name='brandhome'),  # Brand home
    path('customerhome/', views.customerhome, name='customerhome'),  # Customer home
    path('adminhome/', views.adminhome, name='adminhome'),  # Admin home
]
