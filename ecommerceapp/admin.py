from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Category, ProductSize,Bank,Review, Order, OrderItem, Wishlist, Cart, CartItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_id', 'name']
    list_display = ['name', 'brand', 'category', 'price', 'color', 'image_display']
    list_filter = ['brand', 'category', 'color']
    search_fields = ['name', 'brand__brand_name', 'category__name']
    readonly_fields = ['feature_vector']
    
    def image_display(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50px" height="50px"/>', obj.image.url)
        return "No Image"
    
    image_display.allow_tags = True
    image_display.short_description = "Product Image"


@admin.register(ProductSize)
class ProductSizeAdmin(admin.ModelAdmin):
    list_display = ('product', 'size_type')  # Removed 'stock'
    list_filter = ['size_type']
    search_fields = ['product__name']

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'product', 'rating', 'comment', 'created_at', 'updated_at')
    list_filter = ('rating', 'created_at', 'updated_at')
    search_fields = ('customer__name', 'product__name', 'comment')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')  # Prevent editing timestamps

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'customer', 'delivery_address', 'payment_method', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('order_id', 'customer__name', 'delivery_address')
    date_hierarchy = 'created_at'
    list_editable = ('status',)  # Allow inline status editing
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        # Optimize query with related fields
        return super().get_queryset(request).select_related('customer')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'quantity', 'size', 'price')
    list_filter = ('order__status',)
    search_fields = ('order__order_id', 'product__name')
    raw_id_fields = ('order', 'product')  # Better for large datasets

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'product')
    search_fields = ('customer__name', 'product__name')
    raw_id_fields = ('customer', 'product')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer')
    search_fields = ('customer__name',)
    raw_id_fields = ('customer',)

    def get_queryset(self, request):
        # Include cart items in queryset
        return super().get_queryset(request).prefetch_related('items')

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'product', 'quantity', 'size')
    list_filter = ('cart__customer',)
    search_fields = ('cart__customer__name', 'product__name')
    raw_id_fields = ('cart', 'product', 'size')