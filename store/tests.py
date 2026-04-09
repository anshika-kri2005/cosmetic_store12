from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Category, Order, OrderItem, Product, ShippingAddress


class InvoiceDownloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='invoice-user', password='testpass123')
        self.category = Category.objects.create(name='Skincare', description='Care products')
        self.product = Product.objects.create(
            name='Face Serum',
            brand='GlowCo',
            price=499,
            quantity=10,
            category=self.category,
        )
        self.address = ShippingAddress.objects.create(
            user=self.user,
            full_name='Invoice User',
            phone='9876543210',
            house_no='221B',
            street='Beauty Street',
            landmark='Near City Mall',
            pincode='110001',
            district='Delhi',
            state='Delhi',
            country='India',
        )
        self.order = Order.objects.create(
            user=self.user,
            address=self.address,
            total_amount=Decimal('998.00'),
            payment_method='cod',
            payment_status='pending',
            status='pending',
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal('499.00'),
        )

    def test_authenticated_user_can_download_invoice_pdf(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('download_invoice', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(f'invoice_{self.order.id}.pdf', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))
