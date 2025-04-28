from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required,user_passes_test
from authapp.models import Brand ,Customer,Login
from django.contrib import messages
from ecommerceapp.models import Product, Category, ProductSize,Cart, CartItem,Wishlist,Order,OrderItem,Bank,Review,ReturnRequest
from sklearn.neighbors import NearestNeighbors
from ecommerceapp.utils import extract_features
import numpy as np
import pickle
from ecommerceapp.utils import search_products_by_nlp
from django.db import transaction
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from django.views.decorators.csrf import csrf_exempt
from uuid import UUID
from django.conf import settings
import uuid
from django.utils import timezone
from datetime import timedelta
import csv
from django.http import HttpResponse
from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Avg
import logging

# Create your views here.
def index(request):
    products = Product.objects.all().order_by('-id')[:4]  # Get 4 most recent products
    return render(request, 'index.html', {"products": products})

def about(request):
    return render(request, 'aboutus.html')

def contact(request):
    return render(request, 'contactus.html')

def shop(request):
    # Only show visible products by default
    products = Product.objects.filter(is_visible=True)
    search_query = request.POST.get("search_query", "").strip()

    # TEXT SEARCH
    if search_query:
        searched_products = search_products_by_nlp(search_query).filter(is_visible=True)  # NLP-based search
        if searched_products.exists():
            products = searched_products
        else:
            products = Product.objects.none()  # No results
            messages.info(request, "No visible products found matching your search.")

    # IMAGE SEARCH
    elif request.method == "POST" and request.FILES.get("search_image"):
        search_image = request.FILES["search_image"]
        search_features = extract_features(search_image)

        if search_features is not None:
            # Only consider visible products with feature vectors
            feature_products = Product.objects.filter(is_visible=True).exclude(feature_vector__isnull=True)
            features = []
            product_ids = []
            product_categories = {}
            product_colors = {}

            # Collect product data
            for product in feature_products:
                if product.feature_vector:
                    features.append(pickle.loads(product.feature_vector))
                    product_ids.append(product.product_id)
                    product_categories[product.product_id] = product.category.id
                    product_colors[product.product_id] = product.color.lower() if product.color else ""

            if features:
                features = np.array(features)
                n_neighbors = min(20, len(features))
                neighbors = NearestNeighbors(n_neighbors=n_neighbors, metric="euclidean")
                neighbors.fit(features)

                distances, indices = neighbors.kneighbors([search_features])

                # Get only visible products from matches
                matched_products = [Product.objects.get(product_id=product_ids[idx]) 
                                  for idx in indices[0] 
                                  if Product.objects.filter(product_id=product_ids[idx], is_visible=True).exists()]
                
                top_match = matched_products[0] if matched_products else None

                if top_match:
                    top_category = top_match.category.id
                    search_color = top_match.color.lower() if top_match.color else ""

                    # Filter by category
                    same_category_products = [p for p in matched_products if p.category.id == top_category]
                    filtered_products = same_category_products if same_category_products else matched_products

                    # Filter by color
                    if search_color:
                        color_matched = [p for p in filtered_products if p.color and p.color.lower() == search_color]
                        remaining = [p for p in filtered_products if not p.color or p.color.lower() != search_color]
                        filtered_products = color_matched + remaining

                    products = filtered_products
                else:
                    products = Product.objects.none()
                    messages.info(request, "No similar visible products found based on your image.")

    return render(
        request, 
        'shop.html',
        {
            "products": products,
            "search_query": search_query,
        }
    )

def cart(request):
    return render(request, 'cart.html')

# Set up logging
logger = logging.getLogger(__name__)

@login_required
def customer_shop(request):
    """Display all visible products and allow text & image-based search."""
    try:
        customer = Customer.objects.get(login=request.user)
    except Customer.DoesNotExist:
        customer = Customer.objects.create(login=request.user)
        customer.save()
        logger.info(f"Created new customer for user: {request.user.username}")

    # Only show visible products by default
    products = Product.objects.filter(is_visible=True)
    search_query = request.POST.get("search_query", "").strip()

    # TEXT SEARCH
    if search_query:
        logger.debug(f"Performing NLP search for query: {search_query}")
        searched_products = search_products_by_nlp(search_query)  # Returns a list of visible products
        if searched_products:
            products = searched_products
            logger.info(f"Found {len(searched_products)} products for query: {search_query}")
        else:
            products = []  # Empty list for no results
            messages.info(request, "No visible products found matching your search.")
            logger.info(f"No products found for query: {search_query}")

    # IMAGE SEARCH
    elif request.method == "POST" and request.FILES.get("search_image"):
        search_image = request.FILES["search_image"]
        logger.debug("Performing image-based search")
        search_features = extract_features(search_image)

        if search_features is not None:
            # Only consider visible products with feature vectors
            feature_products = Product.objects.filter(is_visible=True).exclude(feature_vector__isnull=True)
            features = []
            product_ids = []
            product_categories = {}
            product_colors = {}

            # Collect product data
            for product in feature_products:
                if product.feature_vector:
                    features.append(pickle.loads(product.feature_vector))
                    product_ids.append(product.product_id)
                    product_categories[product.product_id] = product.category.id
                    product_colors[product.product_id] = product.color.lower() if product.color else ""

            if features:
                features = np.array(features)
                n_neighbors = min(20, len(features))
                neighbors = NearestNeighbors(n_neighbors=n_neighbors, metric="euclidean")
                neighbors.fit(features)

                distances, indices = neighbors.kneighbors([search_features])

                # Get only visible products from matches
                matched_products = []
                for idx in indices[0]:
                    try:
                        product = Product.objects.get(product_id=product_ids[idx], is_visible=True)
                        matched_products.append(product)
                    except Product.DoesNotExist:
                        continue
                
                top_match = matched_products[0] if matched_products else None

                if top_match:
                    top_category = top_match.category.id
                    search_color = top_match.color.lower() if top_match.color else ""

                    # Filter by category
                    same_category_products = [p for p in matched_products if p.category.id == top_category]
                    filtered_products = same_category_products if same_category_products else matched_products

                    # Filter by color
                    if search_color:
                        color_matched = [p for p in filtered_products if p.color and p.color.lower() == search_color]
                        remaining = [p for p in filtered_products if not p.color or p.color.lower() != search_color]
                        filtered_products = color_matched + remaining

                    products = filtered_products
                    logger.info(f"Found {len(products)} products for image search")
                else:
                    products = []
                    messages.info(request, "No similar visible products found based on your image.")
                    logger.info("No products found for image search")
            else:
                products = []
                messages.info(request, "No visible products with feature vectors available.")
                logger.warning("No products with feature vectors for image search")
        else:
            products = []
            messages.info(request, "Failed to process the uploaded image.")
            logger.error("Failed to extract features from uploaded image")

    return render(request, "customer/customershop.html", {
        "products": products,
        "search_query": search_query,
        "customer": customer
    })

@login_required
def customer_cart(request):
    customer=request.user.customer
    print("Entering cart_view")
    if request.user.is_authenticated:
        customer, _ = Customer.objects.get_or_create(login=request.user)
        cart, _ = Cart.objects.get_or_create(customer=customer)
        print(f"User: {request.user}, Customer: {customer}, Cart ID: {cart.id}")
    else:
        session_id = request.session.session_key or request.session.create()
        cart, _ = Cart.objects.get_or_create(session_id=session_id)
        print(f"Session ID: {session_id}, Cart ID: {cart.id}")

    cart_items = cart.items.all()
    cart_total = sum(item.total_price() for item in cart_items)
    return render(request, 'customer/customercart.html', {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'customer':customer
    })

@login_required
def customer_aboutus(request):
    customer=request.user.customer
    return render(request, 'customer/customeraboutus.html',{'customer':customer})

@login_required
def customer_contactus(request):
    customer=request.user.customer
    return render(request, 'customer/customercontactus.html',{'customer':customer})

def brand_orders(request):
    return render(request, 'brand/orders.html')


@login_required
def brand_reviews(request):
    if not hasattr(request.user, 'usertype') or request.user.usertype != "brand":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    try:
        brand = Brand.objects.get(login=request.user)
    except Brand.DoesNotExist:
        messages.error(request, "Brand profile not found. Please contact support.")
        return redirect("login")

    # Fetch reviews for the brand's products
    reviews = Review.objects.filter(product__brand=brand).select_related('customer', 'product')

    context = {
        "brand": brand,
        "reviews": reviews,
    }
    return render(request, "brand/reviews.html", context)

@login_required
def delete_review(request, review_id):
    if not hasattr(request.user, 'usertype') or request.user.usertype != "brand":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    review = get_object_or_404(Review, id=review_id, product__brand__login=request.user)
    if request.method == "POST":
        review.delete()
        messages.success(request, "Review deleted successfully.")
        return redirect("brand_reviews")
    return redirect("brand_reviews")


@login_required
def customeraccount(request):
    if request.user.usertype != "customer":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    try:
        customer = Customer.objects.get(login=request.user)
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect("customerhome")

    if request.method == "POST":
        customer.name = request.POST.get("name", customer.name)
        customer.phone = request.POST.get("phone", customer.phone)
        customer.address = request.POST.get("address", customer.address)
        customer.pincode = request.POST.get("pincode", customer.pincode)

        if "photo" in request.FILES:
            customer.photo = request.FILES["photo"]
        customer.save()

        new_email = request.POST.get("email")
        if new_email and new_email != request.user.email:
            request.user.email = new_email
            request.user.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("customeraccount")

    # Fetch wishlist and orders with related data
    wishlist = Wishlist.objects.filter(customer=customer)
    orders = Order.objects.filter(customer=customer).prefetch_related(
        'items__product__review_set'
    ).order_by('-created_at')

    # Attach reviews to order items
    for order in orders:
        for item in order.items.all():
            review = item.product.review_set.filter(
                customer=customer,
                order=order
            ).first()
            item.review = review  # Attach the review directly to the item

    return render(request, "customer/customeraccount.html", {
        "customer": customer,
        "wishlist": wishlist,
        "orders": orders,
    })

@login_required
def cancel_order(request, order_id):
    if request.user.usertype != "customer":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    order = get_object_or_404(Order, order_id=order_id, customer__login=request.user)
    if request.method == "POST":
        if order.status in ["pending", "processing", "shipped"]:
            order.status = "cancelled"
            order.save()
            messages.success(request, "Order cancelled successfully.")
        else:
            messages.error(request, "Cannot cancel this order now.")
    return redirect("customeraccount")

@login_required
def manage_review(request, order_id, order_item_id):
    # Check if user is a customer
    if request.user.usertype != "customer":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    # Get order and order item
    order = get_object_or_404(Order, order_id=order_id, customer__login=request.user)
    order_item = get_object_or_404(OrderItem, id=order_item_id, order=order)
    
    # Check if order is delivered
    if order.status != "delivered":
        messages.error(request, "Reviews can only be managed for delivered orders.")
        return redirect("customeraccount")

    # Try to get existing review (adjusted to match your Review model)
    review = Review.objects.filter(
        customer=order.customer,
        product=order_item.product,
        order=order
    ).first()

    if request.method == "POST":
        rating = request.POST.get("rating")
        comment = request.POST.get("review", "")  # Changed from "comment" to match template
        
        # Validate rating
        try:
            rating_int = int(rating)
            if not (1 <= rating_int <= 5):
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, "Invalid rating. Please provide a rating between 1 and 5.")
            return redirect("customeraccount")

        # Update or create review
        if review:  # Edit existing review
            review.rating = rating_int
            review.comment = comment
            review.save()
            messages.success(request, "Review updated successfully.")
        else:  # Add new review
            Review.objects.create(
                customer=order.customer,
                product=order_item.product,
                order=order,
                rating=rating_int,
                comment=comment
            )
            messages.success(request, "Review added successfully.")
    
    return redirect("customeraccount")


@login_required
def brand_account(request):
    brand = request.user.brand  # Assuming the logged-in user has a related brand object
    user = request.user  # Get the logged-in user
    
    if request.method == "POST":
        # Update editable fields
        brand.brand_name = request.POST.get("brand_name")
        brand.representative_name = request.POST.get("representative_name")
        brand.phone = request.POST.get("phone")
        brand.address = request.POST.get("address")
        brand.pincode = request.POST.get("pincode")
        
        # Update bank details (now editable)
        brand.bank_account_number = request.POST.get("bank_account_number")
        brand.ifsc_code = request.POST.get("ifsc_code")
        
        # Handle logo update
        if "logo" in request.FILES:
            brand.logo = request.FILES["logo"]
        
        # Handle password update
        password = request.POST.get("password")
        if password:
            user.set_password(password)

        try:
            # Save changes
            with transaction.atomic():
                brand.save()
                user.save()
            
            messages.success(request, "Account details updated successfully.")
        except Exception as e:
            messages.error(request, f"Error updating account: {str(e)}")
        
        return redirect("brand_account")

    return render(request, "brand/myaccount.html", {
        "brand": brand,
        "user": user
    })


@login_required
def brand_products(request):
    """Display all products of the logged-in brand and handle product addition."""
    
    if request.user.usertype != "brand":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    brand = get_object_or_404(Brand, login=request.user)
    products = Product.objects.filter(brand=brand)
    categories = Category.objects.all()

    alphabet_sizes = ["XS", "S", "M", "L", "XL", "XXL"]
    numeric_sizes = ["28", "30", "32", "34", "36"]

    if request.method == "POST":
        print("🚀 POST request received for product upload!")

        name = request.POST.get("name")
        category_id = request.POST.get("category")
        price = request.POST.get("price")
        discount_price = request.POST.get("discount_price", "")
        color = request.POST.get("color", "")
        image_file = request.FILES.get("image")
        size_type = request.POST.get("size_type")
        selected_sizes = request.POST.getlist("sizes")  # ✅ No stock field, only selected sizes
        stock_available = request.POST.get("stock_available") == "yes"
        is_visible = request.POST.get("is_visible") == "yes"
        
        product_code = request.POST.get("product_code", "").strip()
        description = request.POST.get("description", "")
        material = request.POST.get("material", "")
        package_contains = request.POST.get("package_contains", "")
        marketed_by = request.POST.get("marketed_by", "")
        imported_by = request.POST.get("imported_by", "")
        country_of_origin = request.POST.get("country_of_origin", "")
        net_quantity = request.POST.get("net_quantity", "")
        customer_care_address = request.POST.get("customer_care_address", "")
        commodity = request.POST.get("commodity", "")

        print(f"Product Name: {name}")
        print(f"Category ID: {category_id}")
        print(f"Price: {price}")
        print(f"Discount Price: {discount_price}")
        print(f"Color: {color}")
        print(f"Size Type: {size_type}")
        print(f"Selected Sizes: {selected_sizes}")
        print(f"Stock Available: {stock_available}")

        if image_file:
            print(f"✅ Image file received: {image_file.name}")
        else:
            print("❌ No image file uploaded!")

        try:
            category = get_object_or_404(Category, id=int(category_id))
            price = Decimal(price)  # ✅ Convert price safely

            with transaction.atomic():  # ✅ Prevent partial inserts
                # ✅ Auto-generate product code if empty
                if not product_code:
                    product_code = Product().generate_unique_product_code()

                # ✅ Create product
                product = Product.objects.create(
                    name=name,
                    brand=brand,
                    category=category,
                    price=price,
                    discount_price=discount_price,
                    color=color,
                    image=image_file,
                    size_type=size_type,
                    stock_available=stock_available,
                    is_visible=is_visible,
                    product_code=product_code,
                    description=description,
                    material=material,
                    package_contains=package_contains,
                    marketed_by=marketed_by,
                    imported_by=imported_by,
                    country_of_origin=country_of_origin,
                    net_quantity=net_quantity,
                    customer_care_address=customer_care_address,
                    commodity=commodity
                )
                print(f"✅ Product {product.name} created successfully with ID {product.id}")

                # ✅ Validate and assign selected sizes (No stock field)
                valid_sizes = alphabet_sizes if size_type == "alphabet" else numeric_sizes
                for size in selected_sizes:
                    if size in valid_sizes:
                        ProductSize.objects.create(product=product, size_type=size)
                    else:
                        messages.error(request, f"Invalid size {size} for selected size type.")
                        raise ValueError(f"Invalid size {size}")

            messages.success(request, "Product added successfully!")
            return redirect("brand_products")

        except Exception as e:
            print(f"❌ ERROR: {e}")
            messages.error(request, f"Error adding product: {e}")

    return render(request, "brand/products.html", {
        "products": products,
        "categories": categories,
        "alphabet_sizes": alphabet_sizes,
        "numeric_sizes": numeric_sizes
    })

@login_required
def brand_orders(request):
    if request.user.usertype != "brand":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    try:
        brand = Brand.objects.get(login=request.user)
    except Brand.DoesNotExist:
        messages.error(request, "Brand profile not found.")
        return redirect("brand_dashboard")

    # Get query parameters
    product_id = request.GET.get('product_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Fetch all products for dropdown
    products = Product.objects.filter(brand=brand).order_by('name')
    if not products.exists():
        messages.info(request, "No products found for your brand.")

    # Initialize selected product and dates
    selected_product = None
    start_date_obj = None
    end_date_obj = None

    # Base queryset
    queryset = Order.objects.filter(items__product__in=products).select_related('customer__login').prefetch_related('items__return_request', 'items__product').distinct().order_by('-created_at')

    # Apply filters
    if product_id:
        try:
            product_uuid = uuid.UUID(product_id)
            selected_product = Product.objects.filter(product_id=product_uuid, brand=brand).first()
            if not selected_product:
                messages.error(request, "Selected product not found.")
                return redirect('brand_orders')
            queryset = queryset.filter(items__product__product_id=product_uuid)
        except ValueError:
            messages.error(request, "Invalid product selected.")
            return redirect('brand_orders')

    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            queryset = queryset.filter(created_at__gte=start_date_obj)
        except ValueError:
            messages.error(request, "Invalid start date format.")
            return redirect('brand_orders')

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            end_date_obj = end_date_obj.replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(created_at__lte=end_date_obj)
        except ValueError:
            messages.error(request, "Invalid end date format.")
            return redirect('brand_orders')

    # Check for valid date range
    if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
        messages.error(request, "Start date cannot be after end date.")
        return redirect('brand_orders')

    # Messages for no orders
    if not queryset.exists():
        if products.exists():
            message = "No orders found"
            if selected_product or start_date or end_date:
                message += " for the selected criteria"
            message += "."
            messages.info(request, message)

    context = {
        "orders": queryset,
        "brand": brand,
        "products": products,
        "selected_product": selected_product,
        "start_date": start_date,
        "end_date": end_date,
    }
    return render(request, "brand/orders.html", context)

@login_required
def update_order_status(request, order_id):
    if request.user.usertype != "brand":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    try:
        brand = Brand.objects.get(login=request.user)
    except Brand.DoesNotExist:
        messages.error(request, "Brand profile not found.")
        return redirect("brand_dashboard")

    order = get_object_or_404(Order, order_id=order_id)
    if not order.items.filter(product__brand=brand).exists():
        messages.error(request, "You do not have permission to update this order.")
        return redirect("brand_orders")

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            if new_status == "delivered" and not order.delivered_at:  # Set delivery date
                order.delivered_at = timezone.now()
            order.save()
            messages.success(request, "Order status updated successfully.")
        else:
            messages.error(request, "Invalid status.")
    
    return redirect("brand_orders")

@login_required
def download_invoice(request, order_id):
    if request.user.usertype != "customer":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    order = get_object_or_404(Order, order_id=order_id, customer__login=request.user)
    if order.status != "delivered":
        messages.error(request, "Invoice can only be downloaded for delivered orders.")
        return redirect("customeraccount")

    order_items = order.items.all()
    context = {
        "order": order,
        "order_items": order_items,
        "customer": order.customer,
    }
    return render(request, "customer/invoice.html", context)

@login_required
def product_page(request, product_id):
    if request.user.usertype != "customer":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    try:
        customer = request.user.customer  # Assuming OneToOneField to Customer
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect("customerhome")

    print(f"Querying product_id: {product_id}")  # Debug
    product = get_object_or_404(Product, product_id=product_id, is_visible=True)
    available_sizes = [size.size_type for size in product.sizes.all()]
    reviews = Review.objects.filter(product=product).select_related('customer')
    context = {
        'product': product,
        'similar_products': Product.objects.filter(category=product.category, is_visible=True).exclude(product_id=product.product_id)[:4],
        'available_sizes': available_sizes,
        'customer': customer,
        "reviews": reviews,
    }
    print(f"Product ID in context: {product.product_id}")  # Debug
    return render(request, 'customer/product_page.html', context)

@require_POST
def add_to_cart(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        size_value = data.get('size')
        quantity = int(data.get('quantity', 1))

        product = Product.objects.get(product_id=product_id)
        size = ProductSize.objects.get(product=product, size_type=size_value)

        if request.user.is_authenticated:
            # request.user is a Login instance; get or create the Customer
            customer, _ = Customer.objects.get_or_create(login=request.user)
            cart, _ = Cart.objects.get_or_create(customer=customer)
        else:
            session_id = request.session.session_key or request.session.create()
            cart, _ = Cart.objects.get_or_create(session_id=session_id)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            size=size,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        return JsonResponse({'message': f"{product.name} (Size: {size.size_type}) added to cart!"})
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found.'}, status=404)
    except ProductSize.DoesNotExist:
        return JsonResponse({'error': f"Size '{size_value}' is not available."}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


    

@require_POST
def update_cart(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        change = int(data.get('change'))

        cart_item = CartItem.objects.get(id=item_id)
        new_quantity = cart_item.quantity + change
        if new_quantity < 1:
            cart_item.delete()
        else:
            cart_item.quantity = new_quantity
            cart_item.save()

        return JsonResponse({'success': True})
    except CartItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_POST
def remove_from_cart(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')

        cart_item = CartItem.objects.get(id=item_id)
        cart_item.delete()

        return JsonResponse({'success': True})
    except CartItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

@require_POST
def update_cart_size(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        new_size = data.get('new_size')

        cart_item = CartItem.objects.get(id=item_id)
        # Find the new size for the product
        new_size_obj = ProductSize.objects.get(product=cart_item.product, size_type=new_size)
        cart_item.size = new_size_obj
        cart_item.save()

        return JsonResponse({'success': True})
    except CartItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found.'}, status=404)
    except ProductSize.DoesNotExist:
        return JsonResponse({'error': f"Size '{new_size}' is not available for this product."}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    
    

@login_required
def edit_product(request, product_id):
    if request.user.usertype != "brand":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    brand = get_object_or_404(Brand, login=request.user)
    product = get_object_or_404(Product, product_id=product_id, brand=brand)

    alphabet_sizes = ["XS", "S", "M", "L", "XL", "XXL"]
    numeric_sizes = ["28", "30", "32", "34", "36"]
    categories = Category.objects.all()

    if request.method == "POST":
        name = request.POST.get("name")
        category_id = request.POST.get("category")
        price = request.POST.get("price")
        discount_price = request.POST.get("discount_price", "")
        color = request.POST.get("color", "")
        image_file = request.FILES.get("image")
        size_type = request.POST.get("size_type")
        selected_sizes = request.POST.getlist("sizes")
        stock_available = request.POST.get("stock_available") == "yes"
        is_visible = request.POST.get("is_visible") == "yes"  # Already present
        description = request.POST.get("description", "")

        try:
            category = get_object_or_404(Category, id=int(category_id))
            price = Decimal(price)

            with transaction.atomic():
                product.name = name
                product.category = category
                product.price = price
                product.discount_price = discount_price if discount_price else None
                product.color = color
                if image_file:
                    product.image = image_file
                product.size_type = size_type
                product.stock_available = stock_available
                product.is_visible = is_visible  # Already handled
                product.description = description
                product.save()

                ProductSize.objects.filter(product=product).delete()
                valid_sizes = alphabet_sizes if size_type == "alphabet" else numeric_sizes
                for size in selected_sizes:
                    if size in valid_sizes:
                        ProductSize.objects.create(product=product, size_type=size)
                    else:
                        messages.error(request, f"Invalid size {size} for selected size type.")
                        raise ValueError(f"Invalid size {size}")

            messages.success(request, "Product updated successfully!")
            return redirect("brand_products")

        except Exception as e:
            messages.error(request, f"Error updating product: {e}")

    current_sizes = ProductSize.objects.filter(product=product).values_list("size_type", flat=True)
    return render(request, "brand/edit_product.html", {
        "product": product,
        "categories": categories,
        "alphabet_sizes": alphabet_sizes,
        "numeric_sizes": numeric_sizes,
        "current_sizes": list(current_sizes),
    })


@login_required
@csrf_exempt
def add_to_wishlist(request):
    if request.user.usertype != "customer":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == "POST":
        product_id = request.POST.get("product_id")
        size = request.POST.get("size", "")
        
        if not product_id:
            return JsonResponse({"error": "Product ID is missing."}, status=400)
            
        try:
            # Convert to UUID if using UUIDField
            product_id = UUID(product_id)
            customer = Customer.objects.get(login=request.user)
            product = Product.objects.get(product_id=product_id, is_visible=True)
            
            # For size handling
            size_value = size if size and size != "No sizes available" else ""
            
            wishlist_item, created = Wishlist.objects.get_or_create(
                customer=customer,
                product=product,
                defaults={'size': size_value}
            )
            
            if created:
                return JsonResponse({
                    "success": True,
                    "message": f"{product.name} added to wishlist!",
                    "product_id": str(product.product_id)  # Return UUID as string
                })
            else:
                return JsonResponse({
                    "success": False,
                    "message": f"{product.name} already in wishlist."
                })
                
        except ValueError as e:
            return JsonResponse({"error": "Invalid product ID format."}, status=400)
        except Product.DoesNotExist:
            return JsonResponse({"error": "Product not found or not available."}, status=404)
        except Customer.DoesNotExist:
            return JsonResponse({"error": "Customer profile not found."}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
@csrf_exempt
def remove_from_wishlist(request):
    if request.user.usertype != "customer":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == "POST":
        wishlist_id = request.POST.get("wishlist_id")
        try:
            customer = Customer.objects.get(login=request.user)
            wishlist_item = Wishlist.objects.get(id=wishlist_id, customer=customer)
            wishlist_item.delete()
            return JsonResponse({
                "success": True,
                "message": "Item removed from wishlist successfully."
            })
        except Wishlist.DoesNotExist:
            return JsonResponse({"error": "Item not found."}, status=404)
        except Customer.DoesNotExist:
            return JsonResponse({"error": "Customer profile not found."}, status=404)
    
    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
@csrf_exempt
def delete_product(request, product_id):
    if request.user.usertype != "brand":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == "POST":
        try:
            brand = Brand.objects.get(login=request.user)
            product = get_object_or_404(Product, product_id=product_id, brand=brand)
            product.delete()
            return JsonResponse({"message": "Product deleted successfully."})
        except Brand.DoesNotExist:
            return JsonResponse({"error": "Brand profile not found."}, status=404)
        except Product.DoesNotExist:
            return JsonResponse({"error": "Product not found or you don't have permission to delete it."}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=400)

@login_required
def checkout(request):
    if request.user.usertype != "customer":
        return redirect("login")

    try:
        customer = request.user.customer
        cart = Cart.objects.get(customer=customer)
        if not cart.items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect("cart")
        return redirect("order_confirmation")
    except (Customer.DoesNotExist, Cart.DoesNotExist):
        return redirect("login")
    

@login_required
def order_confirmation(request):
    if not hasattr(request.user, 'usertype') or request.user.usertype != "customer":
        return redirect("login")

    try:
        customer = request.user.customer  # Assumes a OneToOneField or similar
        cart = Cart.objects.get(customer=customer)
        if not cart.items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect("cart")

        cart_items = cart.items.all()
        cart_total = sum(item.get_total_price() for item in cart_items)
        banks = Bank.objects.all()

        if request.method == "POST":
            delivery_address = request.POST.get("delivery_address", customer.address)
            payment_method = request.POST.get("payment_method")

            if not delivery_address:
                messages.error(request, "Delivery address cannot be empty.")
                return redirect("order_confirmation")

            payment_method_map = {
                "card": "Credit/Debit Card",
                "netbanking": "Net Banking",
                "cod": "Cash on Delivery",
            }
            payment_method_display = payment_method_map.get(payment_method, "Cash on Delivery")

            # Create the order
            order = Order.objects.create(
                order_id=uuid.uuid4(),
                customer=customer,
                delivery_address=delivery_address,
                payment_method=payment_method_display,
                total_amount=cart_total,
                status="pending",
            )

            # Create order items
            order_items = []
            for item in cart_items:
                order_item = OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    size=item.size.size_type if item.size else "",
                    price=item.get_total_price() / item.quantity,
                )
                order_items.append(order_item)

            # Clear cart regardless of payment method
            cart.items.all().delete()

            # Process payment validation and redirect to success page
            if payment_method == "card":
                card_number = request.POST.get("cardNumber")
                card_name = request.POST.get("cardName")
                card_expiry = request.POST.get("cardExpiry")
                card_cvc = request.POST.get("cardCVC")

                if not (card_number and card_name and card_expiry and card_cvc):
                    messages.error(request, "Please provide all card details.")
                    order.delete()
                    return redirect("order_confirmation")

            elif payment_method == "netbanking":
                bank_id = request.POST.get("bank")
                if not bank_id:
                    messages.error(request, "Please select a bank.")
                    order.delete()
                    return redirect("order_confirmation")

            # Redirect to success page with order details
            messages.success(request, f"Order placed successfully! Your Order ID is {order.order_id}.")
            return redirect("order_success", order_id=str(order.order_id))

        return render(request, "customer/order_confirmation.html", {
            "cart_items": cart_items,
            "cart_total": cart_total,
            "customer": customer,
            "banks": banks,
        })

    except (Customer.DoesNotExist, Cart.DoesNotExist):
        return redirect("login")

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, customer__login=request.user)
    return render(request, "customer/order_success.html", {
        "order": order,
    })
    
@login_required
def request_return(request, order_id, item_id):
    order = get_object_or_404(Order, order_id=order_id, customer=request.user.customer)
    item = get_object_or_404(OrderItem, id=item_id, order=order)

    if order.status != 'delivered' or not order.delivered_at:
        messages.error(request, "This item is not eligible for return.")
        return redirect('customeraccount')

    # Check if within 10 days
    if order.delivered_at + timedelta(days=10) < timezone.now():
        messages.error(request, "The return period for this item has expired.")
        return redirect('customeraccount')

    # Check if return request already exists
    if hasattr(item, 'return_request'):
        messages.error(request, "A return request for this item already exists.")
        return redirect('customeraccount')

    if request.method == 'POST':
        reason = request.POST.get('reason')
        ReturnRequest.objects.create(
            order_item=item,
            customer=request.user.customer,
            reason=reason,
            status='requested'
        )
        messages.success(request, "Your return request has been submitted successfully.")
        return redirect('customeraccount')

    return redirect('customeraccount')

@login_required
def update_return_status(request, return_id):
    return_request = get_object_or_404(ReturnRequest, id=return_id)
    
    # Optional: Add permission check to ensure only the brand can update
    # e.g., check if request.user is associated with the brand of the order_item.product

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['approved', 'rejected']:
            return_request.status = new_status
            return_request.save()
            messages.success(request, f"Return request status updated to {return_request.get_status_display()}.")
        else:
            messages.error(request, "Invalid status selected.")
    
    return redirect('brand_orders')  

@login_required
def download_orders_report(request):
    if request.user.usertype != "brand":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("login")

    try:
        brand = Brand.objects.get(login=request.user)
    except Brand.DoesNotExist:
        messages.error(request, "Brand profile not found.")
        return redirect("brand_dashboard")

    # Get query parameters
    product_id = request.GET.get('product_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Base queryset
    products = Product.objects.filter(brand=brand)
    queryset = Order.objects.filter(items__product__in=products).select_related('customer__login').prefetch_related('items__return_request', 'items__product').distinct()

    # Apply filters
    selected_product = None
    if product_id:
        try:
            product_uuid = uuid.UUID(product_id.strip())
            selected_product = Product.objects.filter(product_id=product_uuid, brand=brand).first()
            if not selected_product:
                messages.error(request, "Selected product not found.")
                return redirect('brand_orders')
            queryset = queryset.filter(items__product__product_id=product_uuid)
        except (ValueError, AttributeError):
            messages.error(request, "Invalid product selected.")
            return redirect('brand_orders')

    start_date_obj = None
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date.strip(), '%Y-%m-%d')
            queryset = queryset.filter(created_at__gte=start_date_obj)
        except (ValueError, AttributeError):
            messages.error(request, "Invalid start date format.")
            return redirect('brand_orders')

    end_date_obj = None
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date.strip(), '%Y-%m-%d')
            end_date_obj = end_date_obj.replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(created_at__lte=end_date_obj)
        except (ValueError, AttributeError):
            messages.error(request, "Invalid end date format.")
            return redirect('brand_orders')

    # Check for valid date range
    if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
        messages.error(request, "Start date cannot be after end date.")
        return redirect('brand_orders')

    # Check if any orders match
    if not queryset.exists():
        messages.error(request, "No orders match the selected criteria.")
        return redirect('brand_orders')

    # Create the HTTP response with CSV content type
    response = HttpResponse(content_type='text/csv')
    filename = "orders_report"
    if selected_product:
        filename += f"_{selected_product.name.replace(' ', '_')}"
    if start_date or end_date:
        filename += f"_{start_date or 'start'}_to_{end_date or 'now'}"
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Order ID', 'Customer Name', 'Customer Email', 'Order Date', 'Order Status', 'Total Amount',
        'Item Product', 'Item Quantity', 'Item Size', 'Item Price',
        'Return Status', 'Return Reason', 'Return Request Date'
    ])

    # Write data
    for order in queryset:
        for item in order.items.all():
            if product_id and str(item.product.product_id) != product_id.strip():
                continue
            return_request = item.return_request if hasattr(item, 'return_request') else None
            writer.writerow([
                order.order_id,
                order.customer.name,
                order.customer.login.email if order.customer.login else '',
                order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                order.get_status_display(),
                f'₹{order.total_amount:.2f}',
                item.product.name,
                item.quantity,
                item.size if item.size else 'N/A',
                f'₹{item.price:.2f}',
                return_request.get_status_display() if return_request else 'None',
                return_request.reason if return_request and return_request.reason else '',
                return_request.request_date.strftime('%Y-%m-%d %H:%M:%S') if return_request else ''
            ])

    return response

#admin


# def admin_users(request):
#     return render(request, 'admin/users.html')  # Create this template

@login_required(login_url='login')
def admin_orders(request):
    """
    Admin view to display all orders with filtering, pagination, export capabilities, and bank management via AJAX.
    """
    # Check authorization
    if not request.user.is_authenticated:
        messages.error(request, "User is not authenticated.")
        return redirect('login')

    usertype = getattr(request.user, 'usertype', None)
    if not (request.user.is_superuser or usertype == "admin"):
        messages.error(request, "You are not authorized to access this page.")
        return redirect('home')

    # Force session save
    request.session.modified = True

    # Handle AJAX requests for bank management
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            action = data.get('action')

            if action == 'add_bank':
                name = data.get('name')
                if not name:
                    return JsonResponse({'error': 'Bank name is required.'}, status=400)
                if Bank.objects.filter(name=name).exists():
                    return JsonResponse({'error': 'A bank with this name already exists.'}, status=400)
                Bank.objects.create(name=name)
                return JsonResponse({'message': f"Bank '{name}' added successfully."})

            elif action == 'edit_bank':
                bank_id = data.get('bank_id')
                name = data.get('name')
                if not name:
                    return JsonResponse({'error': 'Bank name is required.'}, status=400)
                bank = Bank.objects.filter(id=bank_id).first()
                if not bank:
                    return JsonResponse({'error': 'Bank not found.'}, status=404)
                if Bank.objects.exclude(id=bank_id).filter(name=name).exists():
                    return JsonResponse({'error': 'A bank with this name already exists.'}, status=400)
                bank.name = name
                bank.save()
                return JsonResponse({'message': f"Bank '{name}' updated successfully."})

            elif action == 'delete_bank':
                bank_id = data.get('bank_id')
                bank = Bank.objects.filter(id=bank_id).first()
                if not bank:
                    return JsonResponse({'error': 'Bank not found.'}, status=404)
                bank_name = bank.name
                bank.delete()
                return JsonResponse({'message': f"Bank '{bank_name}' deleted successfully."})

            return JsonResponse({'error': 'Invalid action.'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data.'}, status=400)

    # Fetch all products for filter dropdown
    products = Product.objects.all()

    # Fetch all banks for manage banks modal
    banks = Bank.objects.all()

    # Initialize query for all orders
    orders = Order.objects.all().select_related('customer').prefetch_related('items__product')

    # Handle filters
    product_id = request.GET.get('product_id')
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    selected_product = None

    # Apply product filter
    if product_id:
        selected_product = Product.objects.filter(product_id=product_id).first()
        if selected_product:
            orders = orders.filter(items__product=selected_product).distinct()
        else:
            messages.warning(request, "Selected product does not exist.")

    # Apply status filter
    if status in ['pending', 'processing', 'shipped', 'out_for_delivery', 'delivered']:
        orders = orders.filter(status=status)
    elif status:
        messages.warning(request, "Invalid status selected.")

    # Apply date range filter
    if start_date or end_date:
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                orders = orders.filter(created_at__date__gte=start_date_obj)
            except ValueError:
                messages.error(request, "Invalid start date format. Please use YYYY-MM-DD.")
                start_date = None

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                orders = orders.filter(created_at__date__lte=end_date_obj)
            except ValueError:
                messages.error(request, "Invalid end date format. Please use YYYY-MM-DD.")
                end_date = None

        # Validate start_date <= end_date
        if start_date and end_date and start_date_obj and end_date_obj:
            if start_date_obj > end_date_obj:
                messages.error(request, "Start date cannot be after end date.")
                orders = Order.objects.all().select_related('customer').prefetch_related('items__product')

    # Calculate stats for cards
    total_orders = orders.count()
    delivered_count = orders.filter(status='delivered').count()
    pending_count = orders.filter(status='pending').count()
    shipping_count = orders.filter(Q(status='shipped') | Q(status='out_for_delivery')).count()

    # Handle export request
    if 'export' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="orders_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Order ID', 'Customer', 'Date', 'Status', 'Total Amount',
            'Product Name', 'Quantity', 'Size', 'Price'
        ])

        for order in orders:
            for item in order.items.all():
                if selected_product and item.product != selected_product:
                    continue
                writer.writerow([
                    order.order_id,
                    order.customer.name,
                    order.created_at.strftime('%Y-%m-%d'),
                    order.get_status_display(),
                    f'₹{order.total_amount:.2f}',
                    item.product.name,
                    item.quantity,
                    item.size if item.size else 'N/A',
                    f'₹{item.price:.2f}'
                ])

        return response

    # Pagination
    paginator = Paginator(orders, 10)  # Show 10 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Context for template
    context = {
        'products': products,
        'banks': banks,  # Added for manage banks modal
        'orders': page_obj,
        'selected_product': selected_product,
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
        'paginator': paginator,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'delivered_count': delivered_count,
        'pending_count': pending_count,
        'shipping_count': shipping_count,
    }

    return render(request, 'admin/orders.html', context)

@login_required(login_url='login')
def admin_products(request):
    """
    Admin view to manage all products and categories (view, delete, hide/unhide products; add/remove categories).
    """
    # Debug: Log user details
    print(f"Request: {request.path}, Method: {request.method}, User: {request.user}, "
          f"Authenticated: {request.user.is_authenticated}, Superuser: {request.user.is_superuser}, "
          f"Usertype: {getattr(request.user, 'usertype', None)}")

    # Check authorization
    if not request.user.is_authenticated:
        messages.error(request, "User is not authenticated.")
        return redirect('login')

    try:
        usertype = getattr(request.user, 'usertype', None)
    except AttributeError:
        usertype = None

    if not (request.user.is_superuser or usertype == "admin"):
        messages.error(request, "You are not authorized to access this page.")
        return redirect('home')

    # Force session save
    request.session.modified = True

    # Handle POST requests
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')

            if action == 'delete_product':
                product_id = data.get('product_id')
                product = Product.objects.get(product_id=product_id)
                product_name = product.name
                product.delete()
                messages.success(request, f"Product '{product_name}' deleted successfully.")
                return JsonResponse({'message': f"Product '{product_name}' deleted successfully."})

            elif action == 'toggle_visibility':
                product_id = data.get('product_id')
                product = Product.objects.get(product_id=product_id)
                product.is_visible = not product.is_visible
                product.save()
                status = "visible" if product.is_visible else "hidden"
                messages.success(request, f"Product '{product.name}' is now {status}.")
                return JsonResponse({'message': f"Product '{product.name}' is now {status}.", 'is_visible': product.is_visible})

            elif action == 'add_category':
                category_name = data.get('name')
                if not category_name:
                    return JsonResponse({'error': "Category name is required."}, status=400)
                if Category.objects.filter(name=category_name).exists():
                    return JsonResponse({'error': f"Category '{category_name}' already exists."}, status=400)
                category = Category.objects.create(name=category_name)
                messages.success(request, f"Category '{category_name}' created successfully.")
                return JsonResponse({'message': f"Category '{category_name}' created successfully."})

            elif action == 'delete_category':
                category_id = data.get('category_id')
                category = Category.objects.get(id=category_id)
                if Product.objects.filter(category=category).exists():
                    return JsonResponse({'error': f"Cannot delete '{category.name}' because it is assigned to products."}, status=400)
                category_name = category.name
                category.delete()
                messages.success(request, f"Category '{category_name}' deleted successfully.")
                return JsonResponse({'message': f"Category '{category_name}' deleted successfully."})

        except Product.DoesNotExist:
            messages.error(request, "Product not found.")
            return JsonResponse({'error': "Product not found."}, status=404)
        except Category.DoesNotExist:
            messages.error(request, "Category not found.")
            return JsonResponse({'error': "Category not found."}, status=404)
        except Exception as e:
            messages.error(request, "An error occurred.")
            return JsonResponse({'error': str(e)}, status=500)

    # Fetch all products and categories
    products = Product.objects.all().select_related('category')
    categories = Category.objects.all()

    context = {
        'products': products,
        'categories': categories,
    }
    return render(request, 'admin/products.html', context)

@login_required(login_url='login')
def brand_verification(request):
    """
    Admin view to verify/unverify brands by toggling login.is_approved.
    """
    # Debug: Log user details
    print(f"Request: {request.path}, Method: {request.method}, User: {request.user}, "
          f"Authenticated: {request.user.is_authenticated}, Superuser: {request.user.is_superuser}, "
          f"Usertype: {getattr(request.user, 'usertype', None)}")

    # Check authorization
    if not request.user.is_authenticated:
        messages.error(request, "User is not authenticated.")
        return redirect('login')

    try:
        usertype = getattr(request.user, 'usertype', None)
    except AttributeError:
        usertype = None

    if not (request.user.is_superuser or usertype == "admin"):
        messages.error(request, "You are not authorized to access this page.")
        return redirect('home')

    # Force session save
    request.session.modified = True

    # Handle POST requests for verification toggle
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            login_id = data.get('login_id')  # Use login_id for Login model

            if action == 'toggle_verification':
                login = Login.objects.get(id=login_id, usertype='brand')
                login.is_approved = not login.is_approved
                login.save()
                brand = Brand.objects.get(login=login)
                status = "approved" if login.is_approved else "unapproved"
                messages.success(request, f"Brand '{brand.brand_name}' is now {status}.")
                return JsonResponse({
                    'message': f"Brand '{brand.brand_name}' is now {status}.",
                    'is_approved': login.is_approved
                })

        except Login.DoesNotExist:
            messages.error(request, "Brand not found.")
            return JsonResponse({'error': "Brand not found."}, status=404)
        except Brand.DoesNotExist:
            messages.error(request, "Brand details not found.")
            return JsonResponse({'error': "Brand details not found."}, status=404)
        except Exception as e:
            messages.error(request, "An error occurred.")
            return JsonResponse({'error': str(e)}, status=500)

    # Fetch all brands
    brands = Brand.objects.filter(login__usertype='brand').select_related('login')

    context = {
        'brands': brands,
    }
    return render(request, 'admin/verification.html', context)

@login_required(login_url='login')
def admin_reviews(request):
    """
    Admin view to display all reviews with filtering, pagination, and export capabilities.
    """
    # Check authorization
    if not request.user.is_authenticated:
        messages.error(request, "User is not authenticated.")
        return redirect('login')

    usertype = getattr(request.user, 'usertype', None)
    if not (request.user.is_superuser or usertype == "admin"):
        messages.error(request, "You are not authorized to access this page.")
        return redirect('home')

    # Force session save
    request.session.modified = True

    # Fetch all products for filter dropdown
    products = Product.objects.all()

    # Initialize query for all reviews
    reviews = Review.objects.all().select_related('customer', 'product')

    # Handle filters
    product_id = request.GET.get('product_id')
    rating = request.GET.get('rating')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    selected_product = None

    # Apply product filter
    if product_id:
        selected_product = Product.objects.filter(product_id=product_id).first()
        if selected_product:
            reviews = reviews.filter(product=selected_product)
        else:
            messages.warning(request, "Selected product does not exist.")

    # Apply rating filter
    if rating in ['1', '2', '3', '4', '5']:
        reviews = reviews.filter(rating=int(rating))
    elif rating:
        messages.warning(request, "Invalid rating selected.")

    # Apply date range filter
    if start_date or end_date:
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                reviews = reviews.filter(created_at__date__gte=start_date_obj)
            except ValueError:
                messages.error(request, "Invalid start date format. Please use YYYY-MM-DD.")
                start_date = None

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                reviews = reviews.filter(created_at__date__lte=end_date_obj)
            except ValueError:
                messages.error(request, "Invalid end date format. Please use YYYY-MM-DD.")
                end_date = None

        # Validate start_date <= end_date
        if start_date and end_date and start_date_obj and end_date_obj:
            if start_date_obj > end_date_obj:
                messages.error(request, "Start date cannot be after end date.")
                reviews = Review.objects.all().select_related('customer', 'product')

    # Calculate stats for cards
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
    five_star_count = reviews.filter(rating=5).count()
    four_star_count = reviews.filter(rating=4).count()

    # Handle export request
    if 'export' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="reviews_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Review ID', 'Customer', 'Product', 'Rating', 'Comment', 'Date'
        ])

        for review in reviews:
            writer.writerow([
                review.id,
                review.customer.name,
                review.product.name,
                review.rating,
                review.comment or 'No comment',
                review.created_at.strftime('%Y-%m-%d')
            ])

        return response

    # Pagination
    paginator = Paginator(reviews, 10)  # Show 10 reviews per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Context for template
    context = {
        'products': products,
        'reviews': page_obj,
        'selected_product': selected_product,
        'rating': rating,
        'start_date': start_date,
        'end_date': end_date,
        'paginator': paginator,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'average_rating': average_rating,
        'five_star_count': five_star_count,
        'four_star_count': four_star_count,
    }

    return render(request, 'admin/reviews.html', context)

@login_required(login_url='login')
def admin_users(request):
    """
    Admin view to display all users with filtering, pagination, and export capabilities.
    """
    # Check authorization
    if not request.user.is_authenticated:
        messages.error(request, "User is not authenticated.")
        return redirect('login')

    if not (request.user.is_superuser or getattr(request.user, 'usertype', None) == "admin"):
        messages.error(request, "You are not authorized to access this page.")
        return redirect('home')

    # Force session save
    request.session.modified = True

    # Initialize query for all users
    users = Login.objects.all()

    # Handle filters
    usertype_filter = request.GET.get('usertype')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Apply usertype filter
    if usertype_filter == 'customer':
        users = users.filter(customer__isnull=False)
    elif usertype_filter == 'brand':
        users = users.filter(brand__isnull=False)
    elif usertype_filter:
        messages.warning(request, "Invalid user type selected.")

    # Apply date range filter
    if start_date or end_date:
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                users = users.filter(date_joined__date__gte=start_date_obj)
            except ValueError:
                messages.error(request, "Invalid start date format. Please use YYYY-MM-DD.")
                start_date = None

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                users = users.filter(date_joined__date__lte=end_date_obj)
            except ValueError:
                messages.error(request, "Invalid end date format. Please use YYYY-MM-DD.")
                end_date = None

        # Validate start_date <= end_date
        if start_date and end_date and start_date_obj and end_date_obj:
            if start_date_obj > end_date_obj:
                messages.error(request, "Start date cannot be after end date.")
                users = Login.objects.all()

    # Calculate stats for cards
    total_users = users.count()
    customer_count = users.filter(customer__isnull=False).count()
    brand_count = users.filter(brand__isnull=False).count()
    active_users = users.filter(is_active=True).count()

    # Handle export request
    if 'export' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="users_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'User ID', 'Name', 'Email', 'Type', 'Join Date', 'Active'
        ])

        for user in users:
            user_type = 'customer' if hasattr(user, 'customer') else 'brand' if hasattr(user, 'brand') else 'unknown'
            name = user.customer.name if hasattr(user, 'customer') else user.brand.brand_name if hasattr(user, 'brand') else user.username
            writer.writerow([
                user.id,
                name,
                user.email,
                user_type.capitalize(),
                user.date_joined.strftime('%Y-%m-%d'),
                'Yes' if user.is_active else 'No'
            ])

        return response

    # Pagination
    paginator = Paginator(users, 10)  # Show 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Context for template
    context = {
        'users': page_obj,
        'usertype': usertype_filter,
        'start_date': start_date,
        'end_date': end_date,
        'paginator': paginator,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'total_users': total_users,
        'customer_count': customer_count,
        'brand_count': brand_count,
        'active_users': active_users,
    }

    return render(request, 'admin/users.html', context)

@login_required(login_url='login')
def toggle_user_status(request, user_id):
    """
    Toggle the active status of a user.
    """
    if not (request.user.is_superuser or getattr(request.user, 'usertype', None) == "admin"):
        messages.error(request, "You are not authorized to perform this action.")
        return redirect('admin_users')
    
    if request.method == 'POST':
        try:
            user = Login.objects.get(id=user_id)
            if user == request.user:
                messages.error(request, "You cannot change your own status.")
            elif user.is_superuser or getattr(user, 'usertype', None) == "admin":
                messages.error(request, "Cannot change status of admin users.")
            else:
                user.is_active = not user.is_active
                user.save()
                # Determine user name for message
                name = user.customer.name if hasattr(user, 'customer') else user.brand.brand_name if hasattr(user, 'brand') else user.username
                status = "activated" if user.is_active else "deactivated"
                messages.success(request, f"User {name} {status} successfully.")
        except Login.DoesNotExist:
            messages.error(request, "User not found.")
    
    return redirect('admin_users')