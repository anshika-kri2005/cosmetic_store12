from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, Customer, Order, Cart, OrderItem, ShippingAddress
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum, F
from django.template.response import TemplateResponse
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
    search_fields = ('user__username', 'full_name', 'pincode')

# ---------------- Order ----------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total_amount', 'payment_method', 'created_at', 'view_report')
    
    list_editable = ('status',) 
    
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'id')
    actions = ['mark_as_shipped', 'mark_as_delivered']

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
    search_fields = ('user__username', 'product__name')

    # Calculate total price per cart item
    def total_price(self, obj):
        return obj.product.price * obj.quantity
    total_price.short_description = 'Total Price'



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

