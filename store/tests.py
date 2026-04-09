from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Category, Order, OrderItem, Product, Review, ShippingAddress


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


class ReviewFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='review-user', password='testpass123')
        self.category = Category.objects.create(name='Makeup', description='Cosmetics')
        self.product = Product.objects.create(
            name='Lip Tint',
            brand='Bloom',
            price=299,
            quantity=8,
            category=self.category,
        )
        self.address = ShippingAddress.objects.create(
            user=self.user,
            full_name='Review User',
            phone='9999999999',
            house_no='44A',
            street='Rose Lane',
            landmark='Pink Plaza',
            pincode='122001',
            district='Gurugram',
            state='Haryana',
            country='India',
        )
        self.order = Order.objects.create(
            user=self.user,
            address=self.address,
            total_amount=Decimal('299.00'),
            payment_method='cod',
            payment_status='paid',
            status='delivered',
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price=Decimal('299.00'),
        )

    def test_user_can_submit_review_from_my_orders(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('submit_review', args=[self.order.id, self.product.id]),
            data={'rating': 5, 'comment': 'Loved the texture and shade.'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Review.objects.filter(
                user=self.user,
                product=self.product,
                rating=5,
                comment='Loved the texture and shade.',
            ).exists()
        )
        self.assertContains(response, 'Your review has been shared.')

    def test_product_detail_shows_review_summary(self):
        Review.objects.create(
            user=self.user,
            product=self.product,
            rating=4,
            comment='Great product.',
        )

        response = self.client.get(reverse('product_detail', args=[self.product.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Customer Reviews')
        self.assertContains(response, 'Great product.')


class AdminReportsTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='admin-user',
            password='testpass123',
            is_staff=True,
        )

    def test_staff_user_can_open_admin_reports_dashboard(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse('admin_reports_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reports Dashboard')
