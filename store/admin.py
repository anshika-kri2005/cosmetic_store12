from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Cart,
    Category,
    Customer,
    Order,
    OrderItem,
    Product,
    Review,
    ShippingAddress,
    Wishlist,
)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.index_template = 'admin/custom_index.html'


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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'name', 'brand', 'price', 'quantity', 'category', 'image_tag')
    list_editable = ('price', 'quantity')
    list_filter = ('category', 'brand')
    search_fields = ('name', 'brand', 'product_id')

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" />', obj.image.url)
        return "-"

    image_tag.short_description = 'Image'


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'user', 'address')
    search_fields = ('name', 'email', 'phone', 'user__username', 'user__email')


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'phone', 'house_no', 'landmark', 'street', 'district', 'state', 'pincode')
    list_filter = ('state', 'district')
    search_fields = ('user__username', 'user__email', 'full_name', 'phone', 'pincode')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'item_summary',
        'status',
        'total_amount',
        'payment_method',
        'payment_status',
        'created_at',
        'address_summary',
        'view_report',
    )
    list_editable = ('status', 'payment_status')
    list_filter = ('status', 'payment_method', 'payment_status', 'created_at')
    search_fields = (
        'user__username',
        'user__email',
        'id',
        'address__full_name',
        'address__phone',
        'razorpay_order_id',
        'razorpay_payment_id',
    )
    actions = [
        'mark_as_shipped',
        'mark_as_delivered',
        'mark_payment_pending',
        'mark_payment_authorized',
        'mark_payment_paid',
        'mark_payment_failed',
    ]
    autocomplete_fields = ('user', 'address')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at',)
    fieldsets = (
        (
            'Order Details',
            {
                'fields': ('user', 'address', 'total_amount', 'status', 'created_at'),
            },
        ),
        (
            'Payment Details',
            {
                'fields': (
                    'payment_method',
                    'payment_status',
                    'razorpay_order_id',
                    'razorpay_payment_id',
                    'razorpay_signature',
                ),
                'description': 'Use this section to update payment progress and store gateway references.',
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('user', 'address').prefetch_related('orderitem_set__product')

    def item_summary(self, obj):
        items = [
            f"{item.product.name} x{item.quantity}"
            for item in obj.orderitem_set.all()
        ]
        return ", ".join(items) if items else "-"

    item_summary.short_description = "Items"

    def address_summary(self, obj):
        return f"{obj.address.full_name}, {obj.address.district}"

    address_summary.short_description = "Shipping"

    def view_report(self, obj):
        return format_html(
            '<a class="button" href="{}">View Reports</a>',
            reverse('admin_reports_dashboard'),
        )

    view_report.short_description = "Report"

    def mark_as_shipped(self, request, queryset):
        queryset.update(status='shipped')

    mark_as_shipped.short_description = "Mark selected orders as shipped"

    def mark_as_delivered(self, request, queryset):
        queryset.update(status='delivered')

    mark_as_delivered.short_description = "Mark selected orders as delivered"

    def mark_payment_pending(self, request, queryset):
        queryset.update(payment_status='pending')

    mark_payment_pending.short_description = "Mark selected payments as pending"

    def mark_payment_authorized(self, request, queryset):
        queryset.update(payment_status='authorized')

    mark_payment_authorized.short_description = "Mark selected payments as authorized"

    def mark_payment_paid(self, request, queryset):
        queryset.update(payment_status='paid')

    mark_payment_paid.short_description = "Mark selected payments as paid"

    def mark_payment_failed(self, request, queryset):
        queryset.update(payment_status='failed')

    mark_payment_failed.short_description = "Mark selected payments as failed"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'quantity', 'total_price')
    list_filter = ('user',)
    search_fields = ('user__username', 'user__email', 'product__name')

    def total_price(self, obj):
        return obj.product.price * obj.quantity

    total_price.short_description = 'Total Price'


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'added_at')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'rating', 'created_at', 'short_comment')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'product__name', 'comment')
    readonly_fields = ('created_at',)

    def short_comment(self, obj):
        return obj.comment[:50] + ('...' if len(obj.comment) > 50 else '')

    short_comment.short_description = 'Comment'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')
    list_filter = ('product',)
    search_fields = ('order__id', 'product__name', 'order__user__username', 'order__user__email')

