from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import User
from requests_orders.models import Order, Quote, OrderCancellation
from payments.models import Payment
from refunds.models import Refund
from shipping.models import Shipment
from stock.models import StockItem


class CancellationTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user('09121234568', role='creator')
        self.buyer = User.objects.create_user('09121234567')
        self.client.force_authenticate(self.staff)
        self.order = self.make_order()
        self.url = f'/api/orders/{self.order.pk}/cancel/'

    def make_order(self, status='paid'):
        quote = Quote.objects.create(book_cost=200000, estimated_days=1)
        order = Order.objects.create(quote=quote, buyer=self.buyer, total_price=200000, status=status)
        Payment.objects.create(order=order, base_amount=200000, status='verified' if status != 'awaiting_payment' else 'pending_proof')
        return order

    def parcel(self, orders, status='preparing', linked=False):
        shipment = Shipment.objects.create(buyer=self.buyer, shipping_fee=175000, status=status, tracking_code='TRACK' if status == 'shipped' else '')
        if linked:
            payment = orders[0].payment
            payment.shipment = shipment
            payment.base_amount += 175000
            payment.save()
        else:
            Payment.objects.create(shipment=shipment, base_amount=175000, status='verified')
        for order in orders:
            StockItem.objects.create(source_order=order, buyer=self.buyer, shipment=shipment, status='shipped' if status == 'shipped' else 'ready_to_ship', unit_price=200000)
        return shipment

    def cancel(self, **kwargs):
        return self.client.post(self.url, {'reason': 'Buyer cancellation', **kwargs})

    def test_unpaid_closes_without_refund(self):
        self.order.status = 'awaiting_payment'
        self.order.save()
        payment = self.order.payment
        payment.status = 'pending_proof'
        payment.save()
        self.assertEqual(self.cancel().status_code, 200)
        self.assertFalse(Refund.objects.exists())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.order.cancellation.created_by, self.staff)

    def test_pending_receipt_must_be_resolved_first(self):
        payment = self.order.payment
        payment.status = 'pending_verification'
        payment.save()
        self.assertEqual(self.cancel().status_code, 409)
        self.assertFalse(OrderCancellation.objects.exists())

    def test_existing_obligations_are_not_refunded_twice(self):
        Refund.objects.create(order=self.order, payment=self.order.payment, reason='expired', original_amount=50000, deduction_amount=10000, refund_amount=40000)
        self.assertEqual(Decimal(self.client.get(self.url).data['refund_amount']), 150000)
        self.assertEqual(self.cancel().status_code, 200)
        self.assertEqual(self.cancel().status_code, 409)
        self.assertEqual(sum(Refund.objects.values_list('original_amount', flat=True)), 200000)

    def test_empty_unshipped_parcel_refunds_separate_shipping(self):
        parcel = self.parcel([self.order])
        self.assertEqual(self.cancel().status_code, 200)
        parcel.refresh_from_db()
        self.assertEqual(parcel.status, 'cancelled')
        self.assertEqual(sum(Refund.objects.values_list('refund_amount', flat=True)), 375000)
        self.assertFalse(StockItem.objects.filter(buyer=self.buyer).exists())

    def test_shared_parcel_and_other_order_survive(self):
        other = self.make_order()
        parcel = self.parcel([self.order, other])
        self.assertEqual(self.cancel().status_code, 200)
        parcel.refresh_from_db()
        self.assertEqual(parcel.status, 'preparing')
        self.assertEqual(parcel.stock_items_set.count(), 1)
        self.assertEqual(parcel.stock_items_set.get().source_order, other)
        self.assertEqual(Refund.objects.get().refund_amount, 200000)
        self.assertEqual(parcel.payment.status, 'verified')

    def test_return_requires_confirmation_and_preserves_tracking(self):
        parcel = self.parcel([self.order], status='shipped', linked=True)
        self.assertTrue(self.client.get(self.url).data['requires_return'])
        self.assertEqual(self.cancel().status_code, 409)
        self.assertEqual(self.cancel(return_confirmed=True).status_code, 200)
        parcel.refresh_from_db()
        self.assertEqual(parcel.status, 'shipped')
        self.assertEqual(parcel.tracking_code, 'TRACK')
        refund = Refund.objects.get()
        self.assertEqual(refund.refund_amount, 200000)  # delivered service retained
        self.assertEqual(refund.reason, 'return')
        self.assertIsNotNone(self.order.cancellation.return_confirmed_at)
        self.assertEqual(self.client.post(f'/api/refunds/{refund.pk}/process/', {}).status_code, 200)

    def test_combined_payment_refunds_shipping_before_dispatch(self):
        self.parcel([self.order], linked=True)
        self.assertEqual(self.cancel().status_code, 200)
        self.assertEqual(Refund.objects.get().refund_amount, 375000)

    def test_unconfirmed_return_record_cannot_be_processed(self):
        refund = Refund.objects.create(order=self.order, payment=self.order.payment, reason='return', original_amount=200000, refund_amount=200000)
        self.assertEqual(self.client.post(f'/api/refunds/{refund.pk}/process/', {}).status_code, 409)

    def test_buyer_cannot_cancel_or_preview_admin_operation(self):
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.cancel().status_code, 403)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from rest_framework.test import APIClient, APITransactionTestCase


class ConcurrentCancellationTests(APITransactionTestCase):
    def test_two_admin_submissions_create_one_refund(self):
        staff = User.objects.create_user('09121234568', role='creator')
        buyer = User.objects.create_user('09121234567')
        quote = Quote.objects.create(book_cost=200000, estimated_days=1)
        order = Order.objects.create(quote=quote, buyer=buyer, total_price=200000, status='paid')
        Payment.objects.create(order=order, base_amount=200000, status='verified')
        barrier = Barrier(2)
        def cancel(_):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=staff.pk))
                barrier.wait(timeout=10)
                return client.post(f'/api/orders/{order.pk}/cancel/', {'reason': 'Requested cancellation'}).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(cancel, [0, 1]))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(Refund.objects.count(), 1)
        self.assertEqual(OrderCancellation.objects.count(), 1)
