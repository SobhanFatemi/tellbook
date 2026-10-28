from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.db import transaction
from requests_orders.services import create_order
from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate
from .views import PaymentReceiptView

from accounts.models import User
from catalog.models import Book
from catalog.pricing import get_display_price
from publisher_catalog.models import Edition, Publisher
from requests_orders.models import BookRequest, Order, Quote
from stock.models import StockItem
from .models import Payment
from .tasks import auto_cancel_unpaid_payments


def receipt():
    data = BytesIO()
    Image.new('RGB', (4, 4), 'white').save(data, format='PNG')
    return SimpleUploadedFile('receipt.png', data.getvalue(), content_type='image/png')


class CheckoutPaymentTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user('09121234567', email='buyer@example.com')
        self.staff = User.objects.create_user('09121234568', role='creator', email='staff@example.com')
        self.book = Book.objects.create(title='Test book', discount_type='percentage', discount_value=20, discount_active=True)
        self.stock = StockItem.objects.create(book=self.book, unit_price=100000)
        self.client.force_authenticate(self.buyer)

    def buy(self):
        # Historical reserved purchases must still settle safely after removal
        # of the public pre-owned-stock purchase endpoint.
        with transaction.atomic():
            quote = Quote.objects.create(book=self.book, book_cost=Decimal(str(self.stock.effective_price)), estimated_days=0)
            return create_order(quote, self.buyer, stock_item=self.stock)

    def upload(self, order):
        return self.client.post(f'/api/payments/{order.pk}/proof/', {'proof_image': receipt()}, format='multipart')

    def approve(self, order):
        self.client.force_authenticate(self.staff)
        return self.client.post(f'/api/payments/{order.payment.pk}/verify/', {'approve': True})

    def test_purchase_matches_display_and_reserves_without_starting_storage(self):
        expected = self.stock.effective_price
        order = self.buy()
        self.assertEqual(order.total_price, expected)
        self.assertEqual(order.total_price, Decimal('80000'))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.status, StockItem.Status.RESERVED)
        self.assertIsNone(self.stock.expires_at)
        self.assertAlmostEqual((order.payment.auto_cancel_at - timezone.now()).total_seconds(), 1800, delta=5)
        self.assertEqual(self.client.get('/api/stock/shelf/mine/').data, [])
        self.assertEqual(self.client.post(f'/api/orders/buy/stock/{self.book.pk}/', {}).status_code, 410)

    def test_removed_stock_purchase_cannot_create_order(self):
        response = self.client.post(f'/api/orders/buy/stock/{self.book.pk}/', {})
        self.assertEqual(response.status_code, 410)
        self.assertFalse(Quote.objects.exists())
        self.assertFalse(Order.objects.exists())

    def test_legacy_stock_does_not_set_public_catalog_price(self):
        StockItem.objects.create(book=self.book, unit_price=50000)
        self.assertIsNone(get_display_price(self.book).price)
        self.assertFalse(self.book.is_available)
        publisher = Publisher.objects.create(name='Publisher')
        Edition.objects.create(book=self.book, publisher=publisher, price=200000)
        self.assertEqual(get_display_price(self.book).price, 160000)

    def test_edition_checkout_honors_book_discount(self):
        publisher = Publisher.objects.create(name='Publisher')
        edition = Edition.objects.create(book=self.book, publisher=publisher, price=200000)
        response = self.client.post(f'/api/orders/buy/edition/{edition.pk}/', {})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data['total_price']), Decimal('160000'))

    def test_receipt_pauses_expiry_and_approval_starts_storage(self):
        order = self.buy()
        self.assertEqual(self.upload(order).status_code, 200)
        payment = Payment.objects.get(order=order)
        self.assertIsNone(payment.auto_cancel_at)
        # A stale scheduled candidate must still not cancel an uploaded receipt.
        Payment.objects.filter(pk=payment.pk).update(auto_cancel_at=timezone.now() - timedelta(days=1))
        self.assertEqual(auto_cancel_unpaid_payments()['cancelled'], 0)
        self.assertEqual(self.approve(order).status_code, 200)
        order.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.STOCK_READY)
        self.assertAlmostEqual((self.stock.expires_at - timezone.now()).total_seconds(), 30 * 86400, delta=5)
        self.assertEqual(self.approve(order).status_code, 409)

    def test_expired_reservation_releases_copy_once(self):
        order = self.buy()
        Payment.objects.filter(order=order).update(auto_cancel_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.upload(order).status_code, 409)
        self.assertEqual(auto_cancel_unpaid_payments()['cancelled'], 1)
        self.assertEqual(auto_cancel_unpaid_payments()['cancelled'], 0)
        order.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.stock.status, StockItem.Status.AVAILABLE)
        self.assertIsNone(self.stock.buyer_id)
        self.assertIsNone(self.stock.source_order_id)

    def test_missing_receipt_and_wrong_owner_are_rejected(self):
        order = self.buy()
        self.assertEqual(self.client.post(f'/api/payments/{order.pk}/proof/', {}).status_code, 400)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.upload(order).status_code, 404)

    def test_verified_receipt_cannot_be_replaced(self):
        order = self.buy()
        self.upload(order)
        self.approve(order)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.upload(order).status_code, 409)

    def test_rejection_requires_reason_and_allows_new_receipt(self):
        order = self.buy()
        self.upload(order)
        self.client.force_authenticate(self.staff)
        url = f'/api/payments/{order.payment.pk}/verify/'
        self.assertEqual(self.client.post(url, {'approve': False}).status_code, 400)
        self.assertEqual(self.client.post(url, {'approve': False, 'reason': 'Wrong amount'}).status_code, 200)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.upload(order).status_code, 200)

    def test_receipt_download_requires_owner_or_staff(self):
        order = self.buy()
        self.upload(order)
        url = f'/api/payments/{order.payment.pk}/receipt/'
        request = APIRequestFactory().get(url)
        force_authenticate(request, self.buyer)
        response = PaymentReceiptView.as_view()(request, payment_id=order.payment.pk)
        self.assertEqual(response.status_code, 200)
        response.file_to_stream.close()
        stranger = User.objects.create_user('09121234569')
        self.client.force_authenticate(stranger)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 401)
        payment = Payment.objects.get(order=order)
        with self.assertRaises(ValueError):
            _ = payment.proof_image.url

    def test_failed_transition_rolls_back_payment_and_stock(self):
        order = self.buy()
        self.upload(order)
        self.client.force_authenticate(self.staff)
        with patch.object(Order, 'transition_to', side_effect=RuntimeError('Failure')):
            with self.assertRaises(RuntimeError):
                self.approve(order)
        self.assertEqual(Payment.objects.get(order=order).status, Payment.Status.PENDING_VERIFICATION)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.status, StockItem.Status.RESERVED)

    def test_failed_request_cannot_accept_old_quote(self):
        request = BookRequest.objects.create(buyer=self.buyer, title='Unavailable', status='failed', failure_reason='Unavailable')
        quote = Quote.objects.create(request=request, book_cost=100000, estimated_days=5)
        response = self.client.post(f'/api/orders/quotes/{quote.pk}/accept/', {})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Order.objects.exists())
        quote.refresh_from_db()
        self.assertIsNone(quote.accepted_at)

    def test_accept_quote_only_once(self):
        request = BookRequest.objects.create(buyer=self.buyer, title='Requested book')
        quote = Quote.objects.create(request=request, book=self.book, book_cost=100000, estimated_days=5)
        url = f'/api/orders/quotes/{quote.pk}/accept/'
        self.assertEqual(self.client.post(url, {}).status_code, 201)
        self.assertEqual(self.client.post(url, {}).status_code, 409)
        self.assertEqual(Order.objects.count(), 1)

    def test_unpaid_order_cannot_claim_stock_through_staff_action(self):
        order = self.buy()
        spare = StockItem.objects.create(book=self.book, unit_price=100000)
        self.client.force_authenticate(self.staff)
        response = self.client.post(f'/api/orders/{order.pk}/mark-sourced/', {'stock_item_id': spare.pk})
        self.assertEqual(response.status_code, 409)
        spare.refresh_from_db()
        self.assertEqual(spare.status, StockItem.Status.AVAILABLE)

    def test_payment_summary_contains_real_payment_id(self):
        order = self.buy()
        data = self.client.get('/api/orders/mine/').data[0]
        self.assertEqual(data['payment']['id'], order.payment.pk)
        self.assertEqual(data['quote']['book_title'], self.book.title)
