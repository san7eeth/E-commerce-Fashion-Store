from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

class Login(AbstractUser):
    USER_TYPE_CHOICES = [
        ('admin', 'Admin'),
        ('brand', 'Brand'),
        ('customer', 'Customer'),
    ]
    usertype = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='customer',
        verbose_name='User Type'
    )
    is_approved = models.BooleanField(default=False, verbose_name='Is Approved')
    email = models.EmailField(unique=True, verbose_name='Email Address')

    # Make Django use email instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # No extra required fields

    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name='login_groups',
        related_query_name='login',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='login_user_permissions',
        related_query_name='login',
    )

    def save(self, *args, **kwargs):
        # Set default approval based on user type only when creating
        if self._state.adding:
            if self.usertype == 'customer':
                self.is_approved = True
            elif self.usertype == 'brand':
                self.is_approved = False
        
        # Ensure username is set to email
        # self.username = self.email

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({self.usertype})"

class Customer(models.Model):
    login = models.OneToOneField(Login, on_delete=models.CASCADE, primary_key=True)
    name = models.CharField(max_length=100, verbose_name='Full Name')
    phone = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be in the format: '+999999999'.")],
        verbose_name='Phone Number'
    )
    address = models.TextField(blank=True, null=True, verbose_name='Address')
    pincode = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        validators=[RegexValidator(regex=r'^\d{6}$', message="Pincode must be 6 digits.")],
        verbose_name='Pincode'
    )
    photo = models.ImageField(
        upload_to="customer_photos/",
        blank=True,
        null=True,
        verbose_name='Profile Photo'
    )

    def __str__(self):
        return f"{self.name} ({self.login.username})"

    class Meta:
        verbose_name_plural = "Customers"

from django.db import models
from django.core.validators import RegexValidator

class Brand(models.Model):
    login = models.OneToOneField(Login, on_delete=models.CASCADE, primary_key=True)
    brand_name = models.CharField(
        max_length=100,
        verbose_name="Brand Name",
        default="Unknown Brand"
    )
    representative_name = models.CharField(
        max_length=100,
        verbose_name="Representative Name",
        default="Unknown Representative"
    )
    phone = models.CharField(
        max_length=10,
        validators=[RegexValidator(regex=r'^[6789]\d{9}$', message="Enter a valid 10-digit phone number.")],
        verbose_name="Phone Number",
        default="0000000000"
    )
    address = models.TextField(
        verbose_name="Business Address",
        default="No address provided"
    )
    pincode = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        validators=[RegexValidator(regex=r'^\d{6}$', message="Pincode must be 6 digits.")],
        verbose_name='Pincode'
    )
    logo = models.ImageField(
        upload_to="brand_logos/",
        verbose_name="Brand Logo",
        blank=True,
        null=True
    )
    
    # New fields
    pan_card = models.CharField(
        max_length=10,
        validators=[RegexValidator(
            regex=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$',
            message="Enter a valid PAN card number (format: ABCDE1234F)"
        )],
        verbose_name="PAN Card Number",
        blank=True,
        null=True
    )
    gstin = models.CharField(
        max_length=15,
        validators=[RegexValidator(
            regex=r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
            message="Enter a valid GSTIN number"
        )],
        verbose_name="GSTIN",
        blank=True,
        null=True
    )
    bank_account_number = models.CharField(
        max_length=18,
        verbose_name="Bank Account Number",
        blank=True,
        null=True
    )
    ifsc_code = models.CharField(
        max_length=11,
        validators=[RegexValidator(
            regex=r'^[A-Z]{4}0[A-Z0-9]{6}$',
            message="Enter a valid IFSC code (format: ABCD0123456)"
        )],
        verbose_name="IFSC Code",
        blank=True,
        null=True
    )
    aadhaar_photo = models.ImageField(
        upload_to="aadhaar_photos/",
        verbose_name="Aadhaar Card Photo",
        blank=True,
        null=True
    )

    def __str__(self):
        return self.brand_name

    class Meta:
        verbose_name_plural = "Brands"
