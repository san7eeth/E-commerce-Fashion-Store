from authapp.models import Brand ,Customer # Import your Brand model

def brand_context(request):
    if request.user.is_authenticated:
        brand = Brand.objects.filter(login=request.user).first()  # Use 'login' instead of 'user'
        return {'brand': brand}  # Pass brand info to templates
    return {}  # Empty if user not logged in

def customer_context(request):
    if request.user.is_authenticated:
        customer = Customer.objects.filter(login=request.user).first()  
        return {'customer': customer}  
    return {} 