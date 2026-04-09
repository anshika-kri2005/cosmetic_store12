import json
import time
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Cart, Category, Customer, Order, OrderItem, Product, ShippingAddress


CHECKOUT_SESSION_KEY = 'checkout_state'
PENDING_RAZORPAY_SESSION_KEY = 'pending_razorpay_payment'


def _decimal_amount(value):
    return Decimal(str(value)).quantize(Decimal('0.01'))


def _build_checkout_item(product, quantity):
    unit_price = _decimal_amount(product.price)
    return {
        'product': product,
        'quantity': quantity,
        'unit_price': unit_price,
        'total_price': unit_price * quantity,
    }


def _set_checkout_state(request, source, product_id=None):
    checkout_state = {'source': source}
    if product_id:
        checkout_state['product_id'] = product_id

    request.session[CHECKOUT_SESSION_KEY] = checkout_state
    request.session.pop(PENDING_RAZORPAY_SESSION_KEY, None)
    request.session.modified = True


def _clear_checkout_state(request):
    request.session.pop(CHECKOUT_SESSION_KEY, None)
    request.session.pop(PENDING_RAZORPAY_SESSION_KEY, None)
    request.session.modified = True


def _get_checkout_context(request):
    checkout_state = request.session.get(CHECKOUT_SESSION_KEY, {})
    checkout_source = checkout_state.get('source')

    if checkout_source == 'direct' and checkout_state.get('product_id'):
        product = Product.objects.filter(id=checkout_state['product_id']).first()
        if not product:
            _clear_checkout_state(request)
            return None

        items = [_build_checkout_item(product, 1)]
        return {
            'source': 'direct',
            'items': items,
            'total_amount': items[0]['total_price'],
        }

    cart_items = list(Cart.objects.filter(user=request.user).select_related('product'))
    if not cart_items:
        if checkout_source == 'cart':
            _clear_checkout_state(request)
        return None

    items = [_build_checkout_item(item.product, item.quantity) for item in cart_items]
    return {
        'source': 'cart',
        'items': items,
        'total_amount': sum((item['total_price'] for item in items), Decimal('0.00')),
    }


def _serialize_checkout_items(items):
    return [
        {
            'product_id': item['product'].id,
            'quantity': item['quantity'],
            'unit_price': str(item['unit_price']),
        }
        for item in items
    ]


def _deserialize_checkout_items(serialized_items):
    product_ids = [item['product_id'] for item in serialized_items]
    products = Product.objects.in_bulk(product_ids)
    deserialized_items = []

    for item in serialized_items:
        product = products.get(item['product_id'])
        if not product:
            raise ValueError("One of the checkout products no longer exists.")

        quantity = int(item['quantity'])
        unit_price = _decimal_amount(item['unit_price'])
        deserialized_items.append(
            {
                'product': product,
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': unit_price * quantity,
            }
        )

    return deserialized_items


def _get_default_address(user):
    return ShippingAddress.objects.filter(user=user).order_by('-id').first()


def get_razorpay_client():
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return None

    try:
        import razorpay
    except ImportError:
        return None

    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def _create_order_from_items(
    *,
    user,
    address,
    items,
    payment_method,
    payment_status='pending',
    clear_cart=False,
    razorpay_order_id='',
    razorpay_payment_id='',
    razorpay_signature='',
):
    total_amount = sum((item['total_price'] for item in items), Decimal('0.00'))

    with transaction.atomic():
        order = Order.objects.create(
            user=user,
            address=address,
            total_amount=total_amount,
            payment_method=payment_method,
            payment_status=payment_status,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )

        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=item['product'],
                    quantity=item['quantity'],
                    price=item['unit_price'],
                )
                for item in items
            ]
        )

        if clear_cart:
            Cart.objects.filter(user=user).delete()

    return order


@login_required
def profile(request):
    addresses = ShippingAddress.objects.filter(user=request.user)

    context = {
        'user': request.user,
        'addresses': addresses,
    }

    return render(request, 'store/profile.html', context)


def signup_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('signup')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect('signup')

        if not phone.isdigit() or len(phone) != 10:
            messages.error(request, "Enter a valid 10-digit phone number.")
            return redirect('signup')

        if Customer.objects.filter(phone=phone).exclude(user__isnull=True).exists():
            messages.error(request, "Phone number already registered.")
            return redirect('signup')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
        )

        Customer.objects.create(
            user=user,
            name=username,
            email=email,
            phone=phone,
            address='',
        )

        messages.success(request, "Account created successfully.")
        return redirect('login')

    return render(request, "store/signup.html")


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
        'query': query,
        'page': 'home',
    }

    return render(request, 'store/index.html', context)


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=product,
    )

    if created:
        cart_item.quantity = 1
    else:
        cart_item.quantity += 1

    cart_item.save()
    messages.success(request, f"{product.name} added to cart.")
    return redirect('cart_view')


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    related_products = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:4]
    return render(
        request,
        'store/product_detail.html',
        {
            'product': product,
            'related_products': related_products,
        },
    )


def category_products(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category)
    categories = Category.objects.all()

    return render(request, 'store/index.html', {
        'products': products,
        'categories': categories,
        'selected_category': category,
    })


@login_required
def cart_view(request):
    cart_items = Cart.objects.filter(user=request.user).select_related('product')
    total = sum((_decimal_amount(item.product.price) * item.quantity for item in cart_items), Decimal('0.00'))

    context = {
        'cart_items': cart_items,
        'total': total,
    }
    return render(request, 'store/cart.html', context)


@login_required
def buy_now(request, pk):
    return redirect('checkout_direct', pk=pk)


@login_required
def checkout(request, pk=None):
    if pk:
        get_object_or_404(Product, id=pk)
        _set_checkout_state(request, 'direct', product_id=pk)
    else:
        if not Cart.objects.filter(user=request.user).exists():
            _clear_checkout_state(request)
            return redirect('cart_view')
        _set_checkout_state(request, 'cart')

    checkout_context = _get_checkout_context(request)
    if not checkout_context:
        messages.error(request, "Your checkout session could not be prepared.")
        return redirect('cart_view')

    address = _get_default_address(request.user)

    return render(request, 'store/checkout.html', {
        'cart_items': checkout_context['items'],
        'total_amount': checkout_context['total_amount'],
        'address': address,
        'razorpay_enabled': bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET),
    })


@login_required
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

        Customer.objects.update_or_create(
            user=request.user,
            defaults={
                'name': request.user.username,
                'email': request.user.email,
                'phone': request.POST['phone'],
                'address': ", ".join(
                    filter(
                        None,
                        [
                            request.POST['house_no'],
                            request.POST['street'],
                            request.POST.get('landmark'),
                            request.POST['district'],
                            request.POST['state'],
                            request.POST['country'],
                            request.POST['pincode'],
                        ],
                    )
                ),
            },
        )

        return redirect('checkout')

    return render(request, 'store/shipping_address.html')


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
            from django.core.mail import send_mail

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


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(Cart, id=item_id, user=request.user)
    item.delete()

    if not Cart.objects.filter(user=request.user).exists():
        request.session.pop(CHECKOUT_SESSION_KEY, None)
        request.session.modified = True

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
        cart_item.delete()

    if not Cart.objects.filter(user=request.user).exists():
        request.session.pop(CHECKOUT_SESSION_KEY, None)
        request.session.modified = True

    return redirect('cart_view')


@login_required
@require_POST
def place_order(request):
    checkout_context = _get_checkout_context(request)
    if not checkout_context:
        messages.error(request, "Your checkout is empty.")
        return redirect('cart_view')

    address = _get_default_address(request.user)
    if not address:
        messages.error(request, "Order place karne se pehle shipping address add kijiye.")
        return redirect('shipping_address')

    payment_method = request.POST.get('payment') or 'cod'
    if payment_method == 'razorpay':
        messages.error(request, "Please use Pay Now to complete Razorpay payment.")
        return redirect('checkout')

    order = _create_order_from_items(
        user=request.user,
        address=address,
        items=checkout_context['items'],
        payment_method='cod',
        payment_status='pending',
        clear_cart=checkout_context['source'] == 'cart',
    )
    _clear_checkout_state(request)

    return redirect('order_success', order_id=order.id)


@login_required
@require_POST
def create_razorpay_order(request):
    address = _get_default_address(request.user)
    if not address:
        return JsonResponse(
            {'message': 'Please add a shipping address before paying.'},
            status=400,
        )

    checkout_context = _get_checkout_context(request)
    if not checkout_context:
        return JsonResponse({'message': 'Your checkout is empty.'}, status=400)

    client = get_razorpay_client()
    if client is None:
        return JsonResponse(
            {'message': 'Razorpay is not configured on the server yet.'},
            status=503,
        )

    amount = checkout_context['total_amount']
    amount_in_paise = int((amount * 100).quantize(Decimal('1')))
    receipt = f"beautyhub_{request.user.id}_{int(time.time())}"[:40]

    try:
        razorpay_order = client.order.create(
            data={
                'amount': amount_in_paise,
                'currency': settings.RAZORPAY_CURRENCY,
                'receipt': receipt,
                'notes': {
                    'user_id': str(request.user.id),
                    'checkout_source': checkout_context['source'],
                },
            }
        )
    except Exception:
        return JsonResponse(
            {'message': 'Unable to start Razorpay payment right now.'},
            status=502,
        )

    customer = getattr(request.user, 'customer_profile', None)

    request.session[PENDING_RAZORPAY_SESSION_KEY] = {
        'razorpay_order_id': razorpay_order['id'],
        'source': checkout_context['source'],
        'address_id': address.id,
        'items': _serialize_checkout_items(checkout_context['items']),
        'amount_in_paise': amount_in_paise,
    }
    request.session.modified = True

    return JsonResponse(
        {
            'key': settings.RAZORPAY_KEY_ID,
            'amount': amount_in_paise,
            'currency': settings.RAZORPAY_CURRENCY,
            'order_id': razorpay_order['id'],
            'name': 'BeautyHub',
            'description': 'Secure checkout payment',
            'prefill': {
                'name': address.full_name,
                'email': request.user.email or getattr(customer, 'email', ''),
                'contact': address.phone or getattr(customer, 'phone', ''),
            },
            'theme': {'color': '#ff1a66'},
        }
    )


@login_required
@require_POST
def verify_razorpay_payment(request):
    pending_payment = request.session.get(PENDING_RAZORPAY_SESSION_KEY)
    if not pending_payment:
        return JsonResponse(
            {'success': False, 'message': 'Payment session expired. Please try again.'},
            status=400,
        )

    client = get_razorpay_client()
    if client is None:
        return JsonResponse(
            {'success': False, 'message': 'Razorpay is not configured on the server yet.'},
            status=503,
        )

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'message': 'Invalid payment verification payload.'},
            status=400,
        )

    signature_payload = {
        'razorpay_order_id': payload.get('razorpay_order_id'),
        'razorpay_payment_id': payload.get('razorpay_payment_id'),
        'razorpay_signature': payload.get('razorpay_signature'),
    }

    if not all(signature_payload.values()):
        return JsonResponse(
            {'success': False, 'message': 'Missing Razorpay payment details.'},
            status=400,
        )

    if signature_payload['razorpay_order_id'] != pending_payment['razorpay_order_id']:
        return JsonResponse(
            {'success': False, 'message': 'Payment order mismatch detected.'},
            status=400,
        )

    try:
        client.utility.verify_payment_signature(signature_payload)
        payment_data = client.payment.fetch(signature_payload['razorpay_payment_id'])
    except Exception:
        return JsonResponse(
            {
                'success': False,
                'message': 'Payment verification failed. Please check the payment in Razorpay before retrying.',
            },
            status=400,
        )

    payment_status = payment_data.get('status')
    if payment_status not in {'authorized', 'captured'}:
        return JsonResponse(
            {'success': False, 'message': 'Payment was not completed successfully.'},
            status=400,
        )

    if payment_data.get('order_id') != pending_payment['razorpay_order_id']:
        return JsonResponse(
            {'success': False, 'message': 'Payment does not belong to this order.'},
            status=400,
        )

    if int(payment_data.get('amount', 0)) != pending_payment['amount_in_paise']:
        return JsonResponse(
            {'success': False, 'message': 'Payment amount mismatch detected.'},
            status=400,
        )

    try:
        items = _deserialize_checkout_items(pending_payment['items'])
    except ValueError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)

    address = get_object_or_404(
        ShippingAddress,
        id=pending_payment['address_id'],
        user=request.user,
    )

    order = _create_order_from_items(
        user=request.user,
        address=address,
        items=items,
        payment_method='razorpay',
        payment_status='paid' if payment_status == 'captured' else 'authorized',
        clear_cart=pending_payment['source'] == 'cart',
        razorpay_order_id=signature_payload['razorpay_order_id'],
        razorpay_payment_id=signature_payload['razorpay_payment_id'],
        razorpay_signature=signature_payload['razorpay_signature'],
    )
    _clear_checkout_state(request)

    return JsonResponse(
        {
            'success': True,
            'redirect_url': reverse('order_success', kwargs={'order_id': order.id}),
        }
    )


def payment(request):
    return render(request, 'store/payment.html')


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/order_success.html', {'order': order})


@login_required
def track_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/track_order.html', {'order': order})


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-id')
    return render(request, 'store/my_orders.html', {'orders': orders})


@login_required
def download_invoice(request, order_id):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return HttpResponse("Invoice PDF feature is not available right now.", status=503)

    order = get_object_or_404(
        Order.objects.select_related('address').prefetch_related('orderitem_set__product'),
        id=order_id,
        user=request.user,
    )
    order_items = list(order.orderitem_set.all())

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'

    styles = getSampleStyleSheet()
    story = []
    address = order.address

    story.append(Paragraph("BeautyHub Invoice", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            f"Invoice #{order.id}<br/>"
            f"Date: {order.created_at.strftime('%d %b %Y, %I:%M %p')}<br/>"
            f"Customer: {address.full_name}<br/>"
            f"Payment: {order.get_payment_method_display()}<br/>"
            f"Payment Status: {order.get_payment_status_display()}<br/>"
            f"Order Status: {order.get_status_display()}",
            styles['BodyText'],
        )
    )
    story.append(Spacer(1, 14))

    address_lines = [
        address.house_no,
        address.street,
        address.landmark,
        f"{address.district}, {address.state}",
        f"{address.country} - {address.pincode}",
        f"Phone: {address.phone}",
    ]
    address_text = "<br/>".join(line for line in address_lines if line)
    story.append(Paragraph("Shipping Address", styles['Heading2']))
    story.append(Paragraph(address_text, styles['BodyText']))
    story.append(Spacer(1, 14))

    table_data = [['Product', 'Qty', 'Unit Price', 'Line Total']]
    for item in order_items:
        line_total = Decimal(item.quantity) * item.price
        table_data.append(
            [
                item.product.name,
                str(item.quantity),
                f"Rs. {Decimal(item.price):.2f}",
                f"Rs. {line_total:.2f}",
            ]
        )

    if len(table_data) == 1:
        table_data.append(['No order items found', '-', '-', '-'])

    items_table = Table(table_data, colWidths=[220, 60, 100, 100])
    items_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff1a66')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f3b4c8')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor('#fff7fa')]),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 14))

    summary_data = [
        ['Subtotal', f"Rs. {order.total_amount:.2f}"],
        ['Delivery', 'Free'],
        ['Grand Total', f"Rs. {order.total_amount:.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[320, 160])
    summary_table.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f3b4c8')),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ffe3ec')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Thank you for shopping with BeautyHub.", styles['BodyText']))

    pdf_buffer = BytesIO()
    document = SimpleDocTemplate(pdf_buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    document.build(story)
    response.write(pdf_buffer.getvalue())
    pdf_buffer.close()
    return response


def sales_report(request):
    data = OrderItem.objects.values('product__name').annotate(
        sold=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price')),
    )

    total_sold = OrderItem.objects.aggregate(total=Sum('quantity'))['total'] or 0
    total_revenue = OrderItem.objects.aggregate(total=Sum(F('quantity') * F('price')))['total'] or 0
    total_orders = Order.objects.count()
    products = Product.objects.all()
    out_of_stock = Product.objects.filter(quantity=0)
    low_stock = Product.objects.filter(quantity__lte=5, quantity__gt=0)

    context = {
        'data': data,
        'total_sold': total_sold,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'products': products,
        'out_of_stock': out_of_stock,
        'low_stock': low_stock,
    }

    return render(request, 'store/report.html', context)


def export_excel(request):
    try:
        import openpyxl
    except ImportError:
        return HttpResponse("Excel export is not available right now.", status=503)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"

    ws.append(['Product', 'Sold', 'Revenue'])

    data = OrderItem.objects.values('product__name').annotate(
        sold=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price')),
    )

    total = 0.0

    for item in data:
        revenue = float(item['revenue'] or 0)
        ws.append([
            item['product__name'],
            item['sold'],
            revenue,
        ])
        total += revenue

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
        revenue=Sum(F('quantity') * F('price')),
    )

    total_revenue = 0
    for item in data:
        revenue = item['revenue'] or 0
        total_revenue += revenue
        data_list.append([
            item['product__name'],
            item['sold'],
            revenue,
        ])

    data_list.append(['Total Revenue', '', total_revenue])

    table = Table(data_list)
    doc.build([table])

    return response
