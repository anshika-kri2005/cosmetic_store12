from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db.models import Q
from .models import Product, Category
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.mail import send_mail
from django.conf import settings
from .models import Cart,Order, OrderItem , ShippingAddress
from django.http import JsonResponse
import random
from django.http import HttpResponse
from django.template.loader import get_template
from datetime import datetime
import openpyxl
from django.db.models import Sum, F, Count


# =========================
# SIGNUP
# =========================
@login_required
def profile(request):
    addresses = ShippingAddress.objects.filter(user=request.user)

    context = {
        'user': request.user,
        'addresses': addresses
    }

    return render(request, 'store/profile.html', context)


def signup_view(request):

    if request.method == "POST":

        username = request.POST.get('username')
        email = request.POST.get('email')   # ✅ NEW
        phone = request.POST.get('phone')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # 🔐 Password match check
        if password1 != password2:
            messages.error(request, "Passwords do not match ❌")
            return redirect('signup')

        # 👤 Username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists ❌")
            return redirect('signup')

        # 📧 Email exists (IMPORTANT)
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered ❌")
            return redirect('signup')

        # 📱 Phone validation (10 digits)
        if not phone.isdigit() or len(phone) != 10:
            messages.error(request, "Enter valid 10-digit phone number ❌")
            return redirect('signup')

        # ✅ Create user
        user = User.objects.create_user(
            username=username,
            email=email,   # ✅ SAVE EMAIL
            password=password1
        )

        user.save()

        messages.success(request, "Account created successfully ✅")
        return redirect('login')

    return render(request, "store/signup.html")


# =========================
# HOME PAGE
# =========================


def home(request):
    query = request.GET.get('q')

    products = Product.objects.all()

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    categories = Category.objects.all()

    cart_items_count = 0

    if request.user.is_authenticated:
        cart_items_count = Cart.objects.filter(user=request.user).count()

    context = {
        'products': products,
        'categories': categories,
        'cart_items_count': cart_items_count,
        'query': query,   # 🔥 important
        'page': 'home'
    }

    return render(request, 'store/index.html', context)


# =========================
# ADD TO CART
# =========================
@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=product
    )

    if created:
        cart_item.quantity = 1
    else:
        cart_item.quantity += 1

    cart_item.save()
    messages.success(request, f"{product.name} added to cart")

    return redirect('cart_view')

# =========================
# PRODUCT DETAIL
# =========================
def product_detail(request, pk):   # 👈 pk MUST be here
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'store/product_detail.html', {'product': product})


def category_products(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category)
    categories = Category.objects.all()

    return render(request, 'store/index.html', {
        'products': products,
        'categories': categories,
        'selected_category': category
    })


# =========================
# CART VIEW
# =========================
@login_required
def cart_view(request):
    cart_items = Cart.objects.filter(user=request.user)

    total = sum(item.total_price() for item in cart_items)

    context = {
        'cart_items': cart_items,
        'total': total
    }
    return render(request, 'store/cart.html', context)


@login_required
def buy_now(request, pk):
    return redirect('checkout', pk=pk)


@login_required
def checkout(request, pk=None):

    # Direct Buy
    if pk:
        product = get_object_or_404(Product, id=pk)
        cart_items = [{
            'product': product,
            'quantity': 1,
            'total_price': product.price
        }]

    # From Cart
    else:
        cart = Cart.objects.filter(user=request.user)

        if not cart.exists():
            return redirect('cart_view')

        cart_items = []
        for item in cart:
            cart_items.append({
                'product': item.product,
                'quantity': item.quantity,
                'total_price': item.product.price * item.quantity
            })

    address = ShippingAddress.objects.filter(user=request.user).last()
    total_amount = sum(item['total_price'] for item in cart_items)

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'total_amount': total_amount,
        'address': address   # ← THIS WAS MISSING
    })


def shipping_address(request):

    if request.method == "POST":

        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        latitude = float(latitude) if latitude else None
        longitude = float(longitude) if longitude else None

        ShippingAddress.objects.create(
            user=request.user,

            full_name=request.POST['full_name'],
            phone=request.POST['phone'],

            house_no=request.POST['house_no'],
            street=request.POST['street'],
            landmark=request.POST.get('landmark'),

            pincode=request.POST['pincode'],
            district=request.POST['district'],
            state=request.POST['state'],
            country=request.POST['country'],

            latitude=latitude,
            longitude=longitude,
        )

        return redirect('checkout') 

    return render(request, 'store/shipping_address.html')



# =========================
# LOGOUT
# =========================
def logout_view(request):
    logout(request)
    messages.success(request, "You have logged out successfully.")
    return redirect('home')

def contact_view(request):

    if request.method == "POST":

        name = request.POST.get("name")
        email = request.POST.get("email")
        message = request.POST.get("message")

        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            messages.error(request, "Contact service is not configured right now.")
            return redirect('contact')

        try:
            send_mail(
                subject=f"New Message from {name}",
                message=f"From: {name} <{email}>\n\n{message}",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[settings.EMAIL_HOST_USER],
            )
        except Exception:
            messages.error(request, "Message send nahi ho paya. Thodi der baad fir try kijiye.")
            return redirect('contact')

        messages.success(request, "Message sent successfully!")
        return redirect('contact')

    return render(request, 'store/contact.html')

def remove_from_cart(request, item_id):
    item = Cart.objects.get(id=item_id)
    item.delete()
    return redirect('cart_view')


@login_required
def increase_quantity(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
    cart_item.quantity += 1
    cart_item.save()
    return redirect('cart_view')


@login_required
def decrease_quantity(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)

    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
    else:
        cart_item.delete()   # agar 1 tha to remove kar do

    return redirect('cart_view')


@login_required
def place_order(request):

    cart_items = Cart.objects.filter(user=request.user)

    if not cart_items.exists():
        return redirect('cart_view')

    address = ShippingAddress.objects.filter(user=request.user).last()

    # ✅ get payment method
    payment_method = request.POST.get('payment')

    # Create Order
    order = Order.objects.create(
        user=request.user,
        address=address,
        total_amount=0,
        payment_method=payment_method   # ✅ SAVE HERE
    )

    total = 0

    # Create Order Items
    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            price=item.product.price
        )
        total += item.product.price * item.quantity

    order.total_amount = total
    order.save()

    cart_items.delete()
    print("Order created:", order.id)

    return redirect('order_success',order_id=order.id)

def payment(request):
    return render(request, 'store/payment.html')

def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'store/order_success.html', {'order': order})
    
def track_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/track_order.html', {'order': order})

@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-id')
    return render(request, 'store/my_orders.html', {'orders': orders})

def download_invoice(request, order_id):
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse("Invoice PDF feature is not available right now.", status=503)

    order = get_object_or_404(Order, id=order_id, user=request.user)

    template = get_template('store/invoice.html')
    html = template.render({'order': order})

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'

    pisa.CreatePDF(html, dest=response)

    return response



def sales_report(request):

    #Product-wise sales
    data = OrderItem.objects.values('product__name').annotate(
        sold=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price'))
    )

    #Total sold items
    total_sold = OrderItem.objects.aggregate(
        total=Sum('quantity')
    )['total'] or 0

    #Total revenue
    total_revenue = OrderItem.objects.aggregate(
        total=Sum(F('quantity') * F('price'))
    )['total'] or 0

    #Total orders
    total_orders = Order.objects.count()

    #All products (inventory)
    products = Product.objects.all()

    #Out of stock
    out_of_stock = Product.objects.filter(quantity=0)

    #Low stock (optional)
    low_stock = Product.objects.filter(quantity__lte=5, quantity__gt=0)

    context = {
        'data': data,
        'total_sold': total_sold,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'products': products,
        'out_of_stock': out_of_stock,
        'low_stock': low_stock
    }

    return render(request, 'store/report.html', context)

def export_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"

    # Header
    ws.append(['Product', 'Sold', 'Revenue'])

    data = OrderItem.objects.values('product__name').annotate(
        sold=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price'))
    )

    total = 0

    for item in data:
        ws.append([
            item['product__name'],
            item['sold'],
            float(item['revenue'])
        ])
        total += float(item['revenue'])

    ws.append([])
    ws.append(['Total Revenue', '', total])

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="report.xlsx"'

    wb.save(response)
    return response


def export_pdf(request):
    try:
        from reportlab.platypus import SimpleDocTemplate, Table
    except ImportError:
        return HttpResponse("PDF export is not available right now.", status=503)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'

    doc = SimpleDocTemplate(response)

    data_list = [['Product', 'Sold', 'Revenue']]

    data = OrderItem.objects.values('product__name').annotate(
        sold=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price'))
    )

    for item in data:
        data_list.append([
            item['product__name'],
            item['sold'],
            item['revenue']
        ])

    table = Table(data_list)
    doc.build([table])

    return response







