from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import Category, Product, Customer, Order, Cart, OrderItem, ShippingAddress
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum, F
from django.template.response import TemplateResponse


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'is_superuser',
        'is_active',
        'date_joined',
        'address_count',
        'order_count',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')

    def address_count(self, obj):
        return ShippingAddress.objects.filter(user=obj).count()

    def order_count(self, obj):
        return Order.objects.filter(user=obj).count()

    address_count.short_description = 'Addresses'
    order_count.short_description = 'Orders'


# ---------------- Category ----------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# ---------------- Product ----------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'name', 'brand', 'price', 'quantity', 'category', 'image_tag')
    list_editable = ('price', 'quantity')
    list_filter = ('category', 'brand')
    search_fields = ('name', 'brand', 'product_id')

    # Show image preview
    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" />', obj.image.url)
        return "-"
    image_tag.short_description = 'Image'

# ---------------- Customer ----------------
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address')
    search_fields = ('name', 'phone')

# ---------------- Shipping Address ----------------
@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'phone', 'house_no', 'street', 'district', 'state', 'pincode')
    list_filter = ('state', 'district')
    search_fields = ('user__username', 'user__email', 'full_name', 'phone', 'pincode')

# ---------------- Order ----------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total_amount', 'payment_method', 'created_at', 'address_summary', 'view_report')
    
    list_editable = ('status',) 
    
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'user__email', 'id', 'address__full_name', 'address__phone')
    actions = ['mark_as_shipped', 'mark_as_delivered']
    autocomplete_fields = ('user', 'address')

    def address_summary(self, obj):
        return f"{obj.address.full_name}, {obj.address.district}"

    address_summary.short_description = "Shipping"

    # 🔥 REPORT BUTTON
    def view_report(self, obj):
        return format_html(
            '<a class="button" href="/report/" target="_blank">View Report</a>'
        )
    view_report.short_description = "Report"

    # Quick action: mark selected orders as shipped
    def mark_as_shipped(self, request, queryset):
        queryset.update(status='shipped')
    mark_as_shipped.short_description = "Mark selected orders as shipped"

    # Quick action: mark selected orders as delivered
    def mark_as_delivered(self, request, queryset):
        queryset.update(status='delivered')
    mark_as_delivered.short_description = "Mark selected orders as delivered"

# ---------------- Cart ----------------
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'quantity', 'total_price')
    list_filter = ('user',)
    search_fields = ('user__username', 'user__email', 'product__name')

    # Calculate total price per cart item
    def total_price(self, obj):
        return obj.product.price * obj.quantity
    total_price.short_description = 'Total Price'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')
    list_filter = ('product',)
    search_fields = ('order__id', 'product__name', 'order__user__username', 'order__user__email')



class CustomAdminSite(admin.AdminSite):
    site_header = "BeautyHub Admin"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('report/', self.admin_view(self.report_view), name='report'),
        ]
        return custom_urls + urls

    def report_view(self, request):
        data = OrderItem.objects.values('product__name').annotate(
            sold=Sum('quantity'),
            revenue=Sum(F('quantity') * F('price'))
        )

        products = Product.objects.all()

        context = dict(
            self.each_context(request),
            data=data,
            products=products
        )

        return TemplateResponse(request, "store/report.html", context)

# ✅ IMPORTANT
admin_site = CustomAdminSite(name='custom_admin')

