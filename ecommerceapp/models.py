import uuid
import pickle
import numpy as np
import tensorflow as tf
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from django.db import models
from tensorflow.keras.preprocessing import image
from tensorflow.keras.layers import GlobalMaxPooling2D
from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input
from numpy.linalg import norm
from authapp.models import Brand,Login,Customer
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

# Load AI Model (ResNet50)
model = ResNet50(weights="imagenet", include_top=False, input_shape=(224, 224, 3))
model = tf.keras.Sequential([model, GlobalMaxPooling2D()])
model.trainable = False  # Ensure it doesn't update weights

def extract_features(img_file):
    """Extract AI features from an image file."""
    try:
        img = Image.open(img_file)  # Open image using PIL
        img = img.convert("RGB")  # Ensure it's in RGB mode
        img = img.resize((224, 224))  # Resize image
        img_array = np.array(img)  # Convert to NumPy array
        expanded_img_array = np.expand_dims(img_array, axis=0)
        preprocessed_img = preprocess_input(expanded_img_array)
        result = model.predict(preprocessed_img).flatten()
        normalized_result = result / norm(result)
        return normalized_result
    except Exception as e:
        print(f"Feature extraction error: {e}")
        return None

# ✅ Category Model
class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name




class Product(models.Model):
    SIZE_TYPE_CHOICES = [
        ("alphabet", "Alphabetic Sizes"),
        ("numeric", "Numeric Sizes")
    ]

    product_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)  
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    image = models.ImageField(upload_to="products/")
    feature_vector = models.BinaryField(blank=True, null=True)
    size_type = models.CharField(max_length=10, choices=SIZE_TYPE_CHOICES, default="alphabet")
    stock_available = models.BooleanField(default=True)

    # ✅ Product Details Fields
    description = models.TextField(blank=True, null=True)  
    material = models.TextField(blank=True, null=True)  
    product_code = models.CharField(max_length=100, unique=True, blank=True)  # Allow blank, but ensure unique values
    package_contains = models.CharField(max_length=255, blank=True, null=True)  
    marketed_by = models.TextField(blank=True, null=True)  
    imported_by = models.TextField(blank=True, null=True)  
    country_of_origin = models.CharField(max_length=100, blank=True, null=True)  
    net_quantity = models.CharField(max_length=50, blank=True, null=True)  
    customer_care_address = models.TextField(blank=True, null=True)  
    commodity = models.CharField(max_length=255, blank=True, null=True)  

    is_visible = models.BooleanField(default=True, help_text="Uncheck to hide the product from customers.")
    
    def generate_unique_product_code(self):
        """Generate a unique product code and check for conflicts."""
        while True:
            new_code = f"PROD-{uuid.uuid4().hex[:8]}"
            if not Product.objects.filter(product_code=new_code).exists():
                return new_code

    def save(self, *args, **kwargs):
        """Ensure product_code is always unique and handle AI feature extraction."""

        # ✅ Auto-generate a unique product code if not provided
        if not self.product_code:
            self.product_code = self.generate_unique_product_code()

        # ✅ Extract AI features only if the image is changed or new
        if self.image and (not self.feature_vector or self._state.adding):
            try:
                img_file = self.image.open()
                features = extract_features(img_file)
                if features is not None:
                    self.feature_vector = pickle.dumps(features)  # Store as binary
            except Exception as e:
                print(f"⚠️ Error extracting features: {e}")

        try:
            super().save(*args, **kwargs)  # ✅ Call the parent class save()
        except Exception as e:
            raise ValidationError(f"⚠️ Error saving product: {e}")

    def get_feature_vector(self):
        """Retrieve feature vector as NumPy array."""
        return pickle.loads(self.feature_vector) if self.feature_vector else None

    def __str__(self):
        return f"{self.name} - {self.brand.brand_name} ({self.category.name})"
    
    @property
    def discount_percentage(self):
        if self.price and self.discount_price and self.price > 0:
            return round((self.price - self.discount_price) / self.price * 100)
        return 0


# ✅ Product Size Model (Manages Available Sizes )
class ProductSize(models.Model):
    ALPHABET_SIZES = [("XS", "XS"), ("S", "S"), ("M", "M"), ("L", "L"), ("XL", "XL"), ("XXL", "XXL")]
    NUMERIC_SIZES = [(str(size), str(size)) for size in [28, 30, 32, 34, 36]]

    SIZE_CHOICES = ALPHABET_SIZES + NUMERIC_SIZES

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sizes")
    size_type = models.CharField(max_length=10, choices=SIZE_CHOICES)

    def clean(self):
        """Ensure size matches product's size type."""
        if self.product.size_type == "alphabet" and self.size_type not in dict(self.ALPHABET_SIZES):
            raise ValidationError(f"Invalid size: {self.size_type} for alphabetic sizes.")
        if self.product.size_type == "numeric" and self.size_type not in dict(self.NUMERIC_SIZES):
            raise ValidationError(f"Invalid size: {self.size_type} for numeric sizes.")

    def __str__(self):
        return f"{self.product.name} - {self.size_type}"

class Cart(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart for {self.customer.login.username if self.customer else self.session_id or 'Anonymous'}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(customer__isnull=False) | models.Q(session_id__isnull=False),
                name="cart_must_have_customer_or_session"
            )
        ]
# ecommerceapp/models.py
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.ForeignKey(ProductSize, on_delete=models.CASCADE, null=True)  # Link to ProductSize
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Size: {self.size.size_type if self.size else 'N/A'})"

    def total_price(self):
        return self.product.price * self.quantity

    def clean(self):
        """Ensure size is valid for the product."""
        if self.size and self.size.product != self.product:
            raise ValidationError("Selected size does not belong to this product.")

    def get_total_price(self):
        price = self.product.discount_price if self.product.discount_price else self.product.price
        return price * self.quantity   
        
class Wishlist(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product = models.ForeignKey("Product", on_delete=models.CASCADE)
    size = models.CharField(max_length=10, blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("customer", "product", "size")

    def __str__(self):
        return f"{self.customer.login.username} - {self.product.name}"
    

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('Net Banking', 'Net Banking'),
        ('Credit/Debit card', 'Credit/Debit Card'),
        ('cod', 'Cash on Delivery'),
    ]
    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    delivery_address = models.TextField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivered_at = models.DateTimeField(null=True, blank=True)
    

    def __str__(self):
        return f"Order {self.order_id} by {self.customer.name}"
    
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    size = models.CharField(max_length=10, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Size: {self.size})"
    

class Bank(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    
class Review(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review by {self.customer.name} for {self.product.name}"
    
class ReturnRequest(models.Model):
    RETURN_STATUSES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processed', 'Processed'),
    ]
    
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name='return_request')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=RETURN_STATUSES, default='requested')
    reason = models.TextField(blank=True, null=True)  # Optional: reason for return

    def __str__(self):
        return f"Return for {self.order_item} - {self.status}"    