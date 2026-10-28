from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Book
from core.models import StoreSettings
from payments.models import Payment
from payments.tasks import auto_cancel_unpaid_payments
from payments.tests import receipt
from requests_orders.models import Order, Quote
from stock.models import StockItem
from stock.tasks import expire_stock_items
from .models import Shipment, ShippingAddress


class FulfillmentTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user('09121234567')
        self.staff = User.objects.create_user('09121234568', role='creator')
        self.stranger = User.objects.create_user('09121234569')
        self.store = StoreSettings.objects.create(pk=1, shipping_fee=50000)
        self.book = Book.objects.create(title='Shelf book')
        self.item = self.paid_copy()
        self.second = self.paid_copy()
        self.address = ShippingAddress.objects.create(user=self.buyer, full_name='Buyer', phone=self.buyer.phone, province='Tehran', city='Tehran', address_line='Test address', postal_code='1234567890')
        self.client.force_authenticate(self.buyer)

    def paid_copy(self):
        quote = Quote.objects.create(book=self.book, book_cost=100000, estimated_days=0)
        order = Order.objects.create(quote=quote, buyer=self.buyer, total_price=100000, status=Order.Status.STOCK_READY)
        Payment.objects.create(order=order, base_amount=100000, status=Payment.Status.VERIFIED)
        item = StockItem.objects.create(book=self.book, unit_price=100000)
        item.claim_for_buyer(self.buyer, order)
        return item

    def request_shipping(self, items=None, fee=50000):
        return self.client.post(f'/api/shipping/ship-shelf/{self.address.pk}/', {'stock_item_ids': items or [self.item.pk], 'expected_shipping_fee': fee}, format='json')

    def pay_shipping(self, shipment):
        response = self.client.post(f'/api/payments/{shipment.payment.pk}/upload/', {'proof_image': receipt()}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(self.staff)
        response = self.client.post(f'/api/payments/{shipment.payment.pk}/verify/', {'approve': True})
        self.assertEqual(response.status_code, 200, response.data)

    def test_selected_books_only_and_separate_payment(self):
        original_expiry = self.second.expires_at
        response = self.request_shipping()
        self.assertEqual(response.status_code, 201, response.data)
        shipment = Shipment.objects.get(pk=response.data['id'])
        self.assertIsNone(shipment.payment.order_id)
        self.assertEqual(shipment.payment.base_amount, Decimal('50000'))
        self.item.refresh_from_db(); self.second.refresh_from_db()
        self.assertEqual(self.item.shipment_id, shipment.pk)
        self.assertIsNone(self.second.shipment_id)
        self.assertEqual(self.second.expires_at, original_expiry)
        self.assertEqual(self.request_shipping().status_code, 409)

    def test_dispatch_cannot_bypass_shipping_payment(self):
        shipment = Shipment.objects.get(pk=self.request_shipping().data['id'])
        self.client.force_authenticate(self.staff)
        url = f'/api/shipping/{shipment.pk}/mark-shipped/'
        self.assertEqual(self.client.post(url, {'tracking_code': 'TRACK'}).status_code, 409)
        # Even tampering with the shipment's state cannot bypass the payment guard.
        Shipment.objects.filter(pk=shipment.pk).update(status=Shipment.Status.PREPARING)
        self.assertEqual(self.client.post(url, {'tracking_code': 'TRACK'}).status_code, 409)

    def test_paid_shipment_can_ship_and_later_selection_costs_again(self):
        shipment = Shipment.objects.get(pk=self.request_shipping().data['id'])
        self.pay_shipping(shipment)
        url = f'/api/shipping/{shipment.pk}/mark-shipped/'
        self.assertEqual(self.client.post(url, {'tracking_code': 'TRACK'}).status_code, 200)
        self.assertEqual(self.client.post(url, {'tracking_code': 'TRACK'}).status_code, 409)
        self.assertEqual(self.client.post(f'/api/shipping/{shipment.pk}/mark-delivered/').status_code, 200)
        self.client.force_authenticate(self.buyer)
        second_shipment = Shipment.objects.get(pk=self.request_shipping([self.second.pk]).data['id'])
        self.assertEqual(second_shipment.payment.status, Payment.Status.PENDING_PROOF)
        self.assertEqual(second_shipment.payment.base_amount, Decimal('50000'))

    def test_fee_changes_require_reconfirmation_but_do_not_change_existing_payment(self):
        shipment = Shipment.objects.get(pk=self.request_shipping().data['id'])
        self.store.shipping_fee = 70000; self.store.save()
        self.assertEqual(self.request_shipping([self.second.pk]).status_code, 409)
        self.assertEqual(Shipment.objects.count(), 1)
        shipment.refresh_from_db()
        self.assertEqual(shipment.shipping_fee, Decimal('50000'))
        self.assertEqual(shipment.payment.base_amount, Decimal('50000'))
        self.assertEqual(self.request_shipping([self.second.pk], 70000).status_code, 201)

    def test_missing_fee_blocks_shipping(self):
        self.store.shipping_fee = None; self.store.save()
        self.assertEqual(self.request_shipping().status_code, 400)
        self.assertFalse(Shipment.objects.exists())

    def test_unpaid_expired_foreign_and_duplicate_selections_fail(self):
        self.item.source_order.payment.status = Payment.Status.PENDING_PROOF
        self.item.source_order.payment.save()
        self.assertEqual(self.request_shipping().status_code, 409)
        self.assertEqual(self.request_shipping([self.second.pk, self.second.pk]).status_code, 400)
        self.second.buyer = self.stranger; self.second.save()
        self.assertEqual(self.request_shipping([self.second.pk]).status_code, 409)
        self.second.buyer = self.buyer; self.second.expires_at = timezone.now() - timedelta(seconds=1); self.second.save()
        self.assertEqual(self.request_shipping([self.second.pk]).status_code, 409)
        self.assertFalse(Shipment.objects.exists())

    def test_cancel_unpaid_shipping_releases_selection_without_resetting_clock(self):
        expiry = self.item.expires_at
        shipment = Shipment.objects.get(pk=self.request_shipping().data['id'])
        response = self.client.post(f'/api/shipping/{shipment.pk}/cancel/')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.shipment_id)
        self.assertEqual(self.item.expires_at, expiry)
        self.assertEqual(self.item.source_order.status, Order.Status.STOCK_READY)

    def test_submitted_shipping_receipt_cannot_be_cancelled_or_expired(self):
        shipment = Shipment.objects.get(pk=self.request_shipping().data['id'])
        self.client.post(f'/api/payments/{shipment.payment.pk}/upload/', {'proof_image': receipt()}, format='multipart')
        self.assertEqual(self.client.post(f'/api/shipping/{shipment.pk}/cancel/').status_code, 409)
        Payment.objects.filter(pk=shipment.payment.pk).update(auto_cancel_at=timezone.now() - timedelta(days=1))
        self.assertEqual(auto_cancel_unpaid_payments()['cancelled'], 0)

    def test_expired_unpaid_shipping_releases_selection(self):
        shipment = Shipment.objects.get(pk=self.request_shipping().data['id'])
        Payment.objects.filter(pk=shipment.payment.pk).update(auto_cancel_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(auto_cancel_unpaid_payments()['cancelled'], 1)
        self.item.refresh_from_db(); shipment.refresh_from_db()
        self.assertIsNone(self.item.shipment_id)
        self.assertEqual(shipment.status, Shipment.Status.CANCELLED)
        self.assertEqual(self.item.source_order.status, Order.Status.STOCK_READY)

    def test_storage_expiry_cancels_unpaid_shipping_and_refunds_book_once(self):
        shipment = Shipment.objects.get(pk=self.request_shipping().data['id'])
        self.item.expires_at = timezone.now() - timedelta(seconds=1); self.item.save(update_fields=["expires_at"])
        self.assertEqual(expire_stock_items(), {'expired': 1, 'refunded': 1})
        self.assertEqual(expire_stock_items(), {'expired': 0, 'refunded': 0})
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.CANCELLED)

    def test_historical_reserved_purchase_can_finish_prepaid_shipping(self):
        from django.db import transaction
        from requests_orders.services import create_order
        stock = StockItem.objects.create(book=self.book, unit_price=100000)
        with transaction.atomic():
            quote = Quote.objects.create(book=self.book, book_cost=100000, estimated_days=0)
            order = create_order(quote, self.buyer, stock_item=stock, delivery={
                'delivery_mode': 'ship_when_ready', 'address_id': self.address.pk, 'expected_shipping_fee': 50000,
            })
        self.assertEqual(order.total_price, Decimal('100000'))
        self.assertEqual(order.payment.base_amount, Decimal('150000'))
        shipment = order.payment.shipment
        self.pay_shipping(shipment)
        stock.refresh_from_db(); shipment.refresh_from_db()
        self.assertEqual(stock.shipment_id, shipment.pk)
        self.assertEqual(shipment.status, Shipment.Status.PREPARING)
        self.assertEqual(self.client.post(f'/api/shipping/{shipment.pk}/mark-shipped/', {'tracking_code': 'TRACK'}).status_code, 200)

    def test_logo_settings_and_fee_are_staff_only(self):
        url = '/api/admin/store-settings/'
        self.assertEqual(self.client.patch(url, {'shipping_fee': 1}).status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.patch(url, {'shipping_fee': 0}).status_code, 400)
        response = self.client.patch(url, {'logo': receipt(), 'shipping_fee': 60000}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(None)
        data = self.client.get('/api/store/').data
        self.assertTrue(data['logo'])
        self.assertEqual(Decimal(data['shipping_fee']), Decimal('60000'))

    def test_legacy_hold_endpoint_cannot_change_stock(self):
        self.assertEqual(self.client.post(f'/api/stock/{self.item.pk}/hold/').status_code, 410)

    def edition_purchase(self):
        from publisher_catalog.models import Edition, Publisher
        publisher = Publisher.objects.create(name="Test publisher")
        edition = Edition.objects.create(book=self.book, publisher=publisher, price=100000)
        response = self.client.post(f'/api/orders/buy/edition/{edition.pk}/', {
            'delivery_mode': 'ship_when_ready', 'address_id': self.address.pk, 'expected_shipping_fee': 50000,
        })
        self.assertEqual(response.status_code, 201, response.data)
        return Order.objects.get(pk=response.data['id'])

    def test_prepaid_edition_waits_for_acquisition_before_storage_and_dispatch(self):
        order = self.edition_purchase()
        shipment = order.payment.shipment
        self.pay_shipping(shipment)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.WAITING_BOOKS)
        self.assertFalse(StockItem.objects.filter(source_order=order).exists())
        self.assertEqual(self.client.post(f'/api/shipping/{shipment.pk}/mark-shipped/', {'tracking_code': 'TRACK'}).status_code, 409)
        before = timezone.now()
        response = self.client.post(f'/api/orders/{order.pk}/mark-sourced/', {'unit_price': 90000})
        self.assertEqual(response.status_code, 200, response.data)
        item = StockItem.objects.get(source_order=order)
        self.assertGreaterEqual(item.expires_at, before + timedelta(days=30))
        shipment.refresh_from_db()
        self.assertEqual(item.shipment_id, shipment.pk)
        self.assertEqual(shipment.status, Shipment.Status.PREPARING)
        self.assertEqual(self.client.post(f'/api/orders/{order.pk}/mark-sourced/', {'unit_price': 90000}).status_code, 409)

    def test_failed_direct_sourcing_refunds_prepaid_shipping_once(self):
        from refunds.models import Refund
        order = self.edition_purchase()
        shipment = order.payment.shipment
        url = f'/api/orders/{order.pk}/fail/'
        self.assertEqual(self.client.post(url, {'failure_reason': 'Unavailable'}).status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(url, {'failure_reason': 'Unavailable'}).status_code, 409)
        self.client.force_authenticate(self.buyer)
        self.pay_shipping(shipment)
        self.assertEqual(self.client.post(url, {'failure_reason': ''}).status_code, 400)
        self.assertEqual(self.client.post(url, {'failure_reason': 'Publisher unavailable'}).status_code, 200)
        order.refresh_from_db(); shipment.refresh_from_db()
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertEqual(order.failure_reason, 'Publisher unavailable')
        self.assertEqual(shipment.status, Shipment.Status.CANCELLED)
        self.assertEqual(Refund.objects.get(order=order).refund_amount, Decimal('150000'))
        self.assertEqual(self.client.post(url, {'failure_reason': 'Again'}).status_code, 409)
        self.assertEqual(Refund.objects.filter(order=order).count(), 1)
