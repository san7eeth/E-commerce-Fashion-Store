from django.urls import path,include
from ecommerceapp import views



urlpatterns = [
    path('', views.index,name='index'),
    path('about',views.about,name='about'),
    path('shop',views.shop,name='shop'),
    path('cart',views.cart,name='cart'),
    path('contact',views.contact,name='ContactUs'),

    #admin
    path('adminhome/users/', views.admin_users, name='admin_users'),
    path('adminhome/orders/', views.admin_orders, name='admin_orders'),
    path('adminhome/products/', views.admin_products, name='admin_products'),
    path('adminhome/brand-verification/', views.brand_verification, name='brand_verification'),
    path('adminhome/reviews/', views.admin_reviews, name='admin_reviews'),
    path('admin/users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),

    
    #cutomer urls
    # path('customer/home/', views.customer_home, name='customer_home'),
    path('customer/shop/', views.customer_shop, name='customer_shop'),
    path('customer/cart/', views.customer_cart, name='customer_cart'),
    path('customer/about-us/', views.customer_aboutus, name='customer_aboutus'),
    path('customer/contact-us/', views.customer_contactus, name='customer_contactus'),
    path("customer/account/", views.customeraccount, name="customeraccount"),

    #brand urls
    # path("brand/home/", views.brand_home, name="brand_home"),
    path("account/", views.brand_account, name="brand_account"),
    path("brand/products/", views.brand_products, name="brand_products"),
    path("brand/orders/", views.brand_orders, name="brand_orders"),
    path("brand/reviews/", views.brand_reviews, name="brand_reviews"),
    path('brand/review/delete/<int:review_id>/', views.delete_review, name='delete_review'),
    path('brand/update-order-status/<uuid:order_id>/', views.update_order_status, name='update_order_status'),
    path("edit-product/<str:product_id>/", views.edit_product, name="edit_product"),
    path('return/<int:return_id>/status/', views.update_return_status, name='update_return_status'),
    path('orders/report/', views.download_orders_report, name='download_orders_report'),


    #shopping
    path('product/<uuid:product_id>/', views.product_page, name='product_page'),
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('update-cart/', views.update_cart, name='update_cart'),
    path('remove-from-cart/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart-size/', views.update_cart_size, name='update_cart_size'),
    path("add-to-wishlist/", views.add_to_wishlist, name="add_to_wishlist"),
    path("remove-from-wishlist/", views.remove_from_wishlist, name="remove_from_wishlist"),
    path('brand/product/delete/<uuid:product_id>/', views.delete_product, name='delete_product'),
    path('checkout/', views.checkout, name='checkout'),
    path('order_confirmation/', views.order_confirmation, name='order_confirmation'),
    path('order-success/<uuid:order_id>/', views.order_success, name='order_success'),
    path('cancel-order/<uuid:order_id>/', views.cancel_order, name='cancel_order'),
    path('manage-review/<uuid:order_id>/<int:order_item_id>/', views.manage_review, name='manage_review'),
    path('download-invoice/<uuid:order_id>/', views.download_invoice, name='download_invoice'),
    path('order/<uuid:order_id>/item/<int:item_id>/return/', views.request_return, name='request_return'),
    
]