from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .models import Customer, Brand
from ecommerceapp.models import Product, OrderItem, Order, Review
from django.views.decorators.cache import never_cache
import re

User = get_user_model()

# Login View
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        # Redirect to appropriate home based on user type
        if request.user.usertype == "brand":
            return redirect("brandhome")
        elif request.user.usertype == "customer":
            return redirect("customerhome")
        request.session['login_visited'] = True
    return render(request, 'authentication/login.html')

# Reset Password View
def reset(request):
    return render(request, 'authentication/resetpassword.html')

def brand_signup_page(request):
    return render(request, 'authentication/brand_signup.html')

# Customer Signup
def customer_signup(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        phone = request.POST.get("phone", "")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists! Please login.")
            return redirect("login")

        try:
            user = User.objects.create_user(
                username=email, 
                email=email, 
                password=password, 
                usertype="customer",
                is_approved=True  # Auto-approved for customers
            )
            Customer.objects.create(login=user, name=name, phone=phone)

            messages.success(request, "Registration successful! Please log in.")
            return redirect("login")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect("customer_signup")

    return render(request, "authentication/login.html")

# Brand Signup
def brand_signup(request):
    if request.method == "POST":
        # Extract all form data
        brand_name = request.POST.get("brandname")
        representative_name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        pincode = request.POST.get("pincode")
        pan_card = request.POST.get("pan_card")
        gstin = request.POST.get("gstin")
        bank_account_number = request.POST.get("bank_account_number")
        ifsc_code = request.POST.get("ifsc_code")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        
        # Get uploaded files
        logo = request.FILES.get("logo")
        aadhaar_photo = request.FILES.get("aadhaar_photo")

        # Validation checks
        errors = []
        
        # Check if email exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists! Please login.")
            return redirect("login")
            
        # Check if PAN card exists
        if Brand.objects.filter(pan_card=pan_card).exists():
            messages.error(request, "This PAN card number is already registered!")
            return redirect("brand_signup")
            
        # Check if GSTIN exists
        if Brand.objects.filter(gstin=gstin).exists():
            messages.error(request, "This GSTIN is already registered!")
            return redirect("brand_signup")
            
        # Password validation
        if password != confirm_password:
            messages.error(request, "Passwords do not match!")
            return redirect("brand_signup")
            
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long!")
            return redirect("brand_signup")
            
        # PAN validation
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan_card):
            messages.error(request, "Invalid PAN card format. Please use format: ABCDE1234F")
            return redirect("brand_signup")
            
        # GSTIN validation
        if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', gstin):
            messages.error(request, "Invalid GSTIN format")
            return redirect("brand_signup")
            
        # IFSC validation
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
            messages.error(request, "Invalid IFSC code format. Please use format: ABCD0123456")
            return redirect("brand_signup")
            
        # Pincode validation
        if not re.match(r'^[1-9][0-9]{5}$', pincode):
            messages.error(request, "Invalid pincode. Must be 6 digits and cannot start with 0")
            return redirect("brand_signup")
            
        # Aadhaar photo validation
        if not aadhaar_photo:
            messages.error(request, "Aadhaar photo is required")
            return redirect("brand_signup")
            
        if aadhaar_photo.size > 10 * 1024 * 1024:  # 10MB
            messages.error(request, "Aadhaar photo size should be less than 2MB")
            return redirect("brand_signup")
            
        if not aadhaar_photo.content_type in ['image/jpeg', 'image/png']:
            messages.error(request, "Aadhaar photo must be JPEG or PNG format")
            return redirect("brand_signup")

        try:
            # Create user
            user = User.objects.create_user(
                username=email, 
                email=email, 
                password=password, 
                usertype="brand",
                is_approved=False  # Requires admin approval
            )
            
            # Create brand with all fields
            brand = Brand.objects.create(
                login=user, 
                brand_name=brand_name, 
                representative_name=representative_name, 
                phone=phone, 
                address=address,
                pincode=pincode,
                pan_card=pan_card,
                gstin=gstin,
                bank_account_number=bank_account_number,
                ifsc_code=ifsc_code,
                aadhaar_photo=aadhaar_photo
            )
            
            # Add logo if provided
            if logo:
                brand.logo = logo
                brand.save()

            messages.success(request, "Brand registration successful! Please wait for admin approval.")
            return redirect("login")
            
        except Exception as e:
            # Clean up if any error occurs
            if 'user' in locals():
                user.delete()
            messages.error(request, f"An error occurred during registration: {str(e)}")
            return redirect("brand_signup")

    return render(request, "authentication/brand_signup.html")

# Signin (Handles Login)
@never_cache
def signin(request):
    if request.user.is_authenticated:
        # Redirect if already logged in
        if request.user.usertype == "brand":
            return redirect("brandhome")
        elif request.user.usertype == "customer":
            return redirect("customerhome")
        elif request.user.usertype == "admin":
            return redirect("adminhome")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if not user.is_approved:
                messages.error(request, "Your account is not approved yet. Please wait for admin approval.")
                return redirect("login")

            auth_login(request, user)
            
            # Set session variable to prevent back button access
            request.session['is_logged_in'] = True
            
            user_redirects = {
                "brand": "brandhome",
                "customer": "customerhome",
            }
            if 'login_visited' in request.session:
                del request.session['login_visited']
            return redirect(reverse(user_redirects.get(user.usertype, "login")))
        else:
            messages.error(request, "Invalid Email or Password")

    return render(request, "authentication/login.html")


@never_cache
def logout_view(request):
    auth_logout(request)
    request.session.flush()  # Clear all session data
    request.session.create()  # Create a new session to prevent session fixation attacks
    messages.success(request, "You have been logged out successfully.")
    return redirect("login")


@login_required
def brandhome(request):
    if request.user.usertype != "brand":
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    try:
        brand = Brand.objects.get(login=request.user)  # Ensure the correct ForeignKey
        email = brand.login.email
    except Brand.DoesNotExist:
        messages.error(request, "Brand profile not found.")
        return redirect('some_other_page')
    # Fetch brand-specific data with optimized queries
    total_products = Product.objects.filter(brand=brand).count()
    
    # Get all order items for this brand's products
    order_items = OrderItem.objects.filter(product__brand=brand)
    
    # Get distinct orders from these order items
    order_ids = order_items.values_list('order_id', flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids)
    
    total_orders = orders.count()
    total_reviews = Review.objects.filter(product__brand=brand).count()
    
    # Recent orders (last 5)
    recent_orders = orders.select_related('customer').order_by('-created_at')[:5]

    context = {
        "brand": brand,
        "total_orders": total_orders,
        "total_products": total_products,
        "total_reviews": total_reviews,
        "recent_orders": recent_orders,
        "brand": brand ,
        "email": email,
    }
    return render(request, "brand/brandhome.html", context)

@login_required
def customerhome(request):
    if request.user.usertype != "customer":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    try:
        customer = Customer.objects.get(login=request.user)
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect("some_error_page")  
    
    products = Product.objects.all().order_by('-id')[:4]  # Adjust ordering as needed
    
    context = {
        "products": products,
        "customer": customer
    }

    return render(request, "customer/customerhome.html", context)

@login_required
def adminhome(request):
    """
    Admin dashboard view displaying site-wide statistics and recent orders.
    """
    # Fetch statistics
    total_orders = Order.objects.count()
    total_products = Product.objects.count()
    total_Users = Customer.objects.count()
    total_brands = Brand.objects.count()

    # Fetch recent orders (last 5, ordered by creation date)
    recent_orders = Order.objects.all().select_related('customer').prefetch_related('items__product__brand').order_by('-created_at')[:5]

    # Context for template
    context = {
        'total_orders': total_orders,
        'total_products': total_products,
        'total_Users': total_Users,
        'total_brands': total_brands,
        'recent_orders': recent_orders,
    }

    return render(request, 'admin/adminhome.html', context)