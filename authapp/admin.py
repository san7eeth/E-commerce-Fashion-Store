from django.contrib import admin
from .models import Login, Customer, Brand
from django.utils.html import format_html

@admin.register(Login)
class LoginAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'usertype', 'is_approved')
    list_filter = ('usertype', 'is_approved')
    search_fields = ('username', 'email')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'pincode', 'login')
    search_fields = ('name', 'phone', 'pincode')

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('brand_name', 'representative_name', 'phone', 'login', 'display_logo_thumbnail')
    search_fields = ('brand_name', 'representative_name', 'phone')
    list_filter = ('brand_name',)
    readonly_fields = ('display_aadhaar_photo', 'display_logo_thumbnail')
    fieldsets = (
        ('Basic Information', {
            'fields': ('login', 'brand_name', 'representative_name', 'phone', 'address', 'pincode')
        }),
        ('Financial Information', {
            'fields': ('pan_card', 'gstin', 'bank_account_number', 'ifsc_code')
        }),
        ('Documents', {
            'fields': ('display_logo_thumbnail', 'logo', 'display_aadhaar_photo', 'aadhaar_photo')
        }),
    )

    def display_aadhaar_photo(self, obj):
        if obj.aadhaar_photo:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />',
                obj.aadhaar_photo.url
            )
        return "No Aadhaar Photo Uploaded"
    display_aadhaar_photo.short_description = "Aadhaar Photo"

    def display_logo_thumbnail(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px;" />',
                obj.logo.url
            )
        return "No Logo Uploaded"
    display_logo_thumbnail.short_description = "Logo"