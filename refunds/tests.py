from rest_framework.test import APITestCase
from accounts.models import User
from requests_orders.models import Order, Quote
from payments.models import Payment
from .models import Refund


class RefundProcessingTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user('09121234568', role='creator')
        self.buyer = User.objects.create_user('09121234567')
        quote = Quote.objects.create(book_cost=200000, estimated_days=1)
        self.order = Order.objects.create(quote=quote, buyer=self.buyer, total_price=200000)
        self.payment = Payment.objects.create(order=self.order, base_amount=200000, status='verified')
        self.refund = Refund.objects.create(order=self.order, payment=self.payment, reason='sourcing_failed', original_amount=200000, refund_amount=200000)
        self.client.force_authenticate(self.staff)
        self.url = f'/api/refunds/{self.refund.pk}/process/'

    def test_partial_refund_records_original_suggestion_and_actor(self):
        response = self.client.post(self.url, {'refund_amount': 150000, 'note': 'Agreed deduction'})
        self.assertEqual(response.status_code, 200)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.refund_amount, 150000)
        self.assertEqual(self.refund.deduction_amount, 50000)
        self.assertEqual(self.refund.suggested_amount, 200000)
        self.assertEqual(self.refund.processed_by, self.staff)
        self.assertEqual(self.refund.processing_note, 'Agreed deduction')
        self.assertEqual(self.client.post(self.url, {}).status_code, 409)

    def test_invalid_amounts_and_missing_reason_do_not_process(self):
        for payload in [{'refund_amount': -1}, {'refund_amount': 200001}, {'refund_amount': '1.5'}, {'refund_amount': 100000}]:
            self.assertEqual(self.client.post(self.url, payload).status_code, 400)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.status, 'pending')

    def test_existing_refund_caps_remaining_payment(self):
        Refund.objects.create(order=self.order, payment=self.payment, reason='expired', original_amount=100000, refund_amount=100000, status='processed')
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {'refund_amount': 100000, 'note': 'Remaining balance'}).status_code, 200)

    def test_unverified_payment_and_nonstaff_are_rejected(self):
        self.payment.status = 'pending_verification'
        self.payment.save()
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.post(self.url, {}).status_code, 403)

    def test_missing_refund_and_policy_limits(self):
        self.assertEqual(self.client.post('/api/refunds/999999/process/', {}).status_code, 404)
        for amount in [-1, 101]:
            self.assertEqual(self.client.post('/api/refunds/policies/', {'reason': 'expired', 'deduction_percentage': amount}).status_code, 400)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from rest_framework.test import APIClient, APITransactionTestCase


class ConcurrentRefundTests(APITransactionTestCase):
    def test_two_refunds_cannot_exceed_the_same_payment(self):
        staff = User.objects.create_user('09121234568', role='creator')
        buyer = User.objects.create_user('09121234567')
        quote = Quote.objects.create(book_cost=200000, estimated_days=1)
        order = Order.objects.create(quote=quote, buyer=buyer, total_price=200000)
        payment = Payment.objects.create(order=order, base_amount=200000, status='verified')
        ids = [Refund.objects.create(order=order, payment=payment, reason='expired', original_amount=150000, refund_amount=150000).pk for _ in range(2)]
        barrier = Barrier(2)

        def process(pk):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=staff.pk))
                barrier.wait(timeout=10)
                return client.post(f'/api/refunds/{pk}/process/', {}).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(process, ids))
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(Refund.objects.filter(status='processed').count(), 1)
