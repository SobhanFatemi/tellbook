from uuid import uuid4
from rest_framework.test import APITestCase
from accounts.models import User
from catalog.models import Book
from publisher_catalog.models import Edition, Publisher
from merchandise.models import Product, BundleComponent
from requests_orders.models import Order
from core.models import StoreSettings
from shipping.models import Shipment


class DeliveryChoiceTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user('09121110000', full_name='نام خریدار')
        self.client.force_authenticate(self.buyer)
        self.settings = StoreSettings.objects.create(pk=1)
        self.edition = Edition.objects.create(book=Book.objects.create(title='کتاب'), publisher=Publisher.objects.create(name='ناشر'), price=200000)
        self.product = Product.objects.create(title='پوستر', category='پوستر', price=70000, is_active=True)
        self.address = dict(full_name='گیرنده', phone=self.buyer.phone, province='تهران', city='تهران', address_line='خیابان نمونه', postal_code='1234567890')

    def purchase(self, lines, fee, **extra):
        return self.client.post('/api/products/checkout/', dict(key=str(uuid4()), lines=lines, delivery_mode='ship_when_ready', address=self.address, expected_shipping_fee=fee, **extra), format='json')

    def books(self, qty):
        return [{'edition_id': self.edition.pk, 'quantity': qty, 'expected_price': 200000}]

    def test_six_inclusive_seven_higher_and_accessories_do_not_count(self):
        for count, fee in [(6, 175000), (7, 250000)]:
            lines = self.books(count) + [{'product_id': self.product.pk, 'quantity': 20, 'expected_price': 70000}]
            result = self.purchase(lines, fee)
            self.assertEqual(result.status_code, 201, result.data)
            shipment = Order.objects.get(pk=result.data['id']).payment.shipment
            self.assertEqual(shipment.book_count, count)
            self.assertEqual(shipment.shipping_fee, fee)
            self.assertEqual(shipment.address_line, self.address['address_line'])

    def test_bundle_books_and_standalone_accessory_fee(self):
        bundle = Product.objects.create(title='پک', category='پک', price=900000, is_bundle=True, is_active=True)
        BundleComponent.objects.create(bundle=bundle, edition=self.edition, quantity=4)
        result = self.purchase([{'product_id': bundle.pk, 'quantity': 2, 'expected_price': 900000}], 250000)
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(Shipment.objects.get().book_count, 8)
        result = self.purchase([{'product_id': self.product.pk, 'quantity': 1, 'expected_price': 70000}], 175000)
        self.assertEqual(result.status_code, 201, result.data)

    def test_cannot_underpay_or_forge_count_and_fee_is_snapshotted(self):
        result = self.purchase(self.books(7), 175000, book_count=1)
        self.assertEqual(result.status_code, 409)
        self.assertFalse(Order.objects.exists())
        result = self.purchase(self.books(1), 175000)
        self.assertEqual(result.status_code, 201, result.data)
        self.settings.shipping_fee = 190000
        self.settings.save()
        self.assertEqual(Shipment.objects.get().shipping_fee, 175000)
        self.assertEqual(self.purchase(self.books(1), 175000).status_code, 409)

    def test_courier_zero_fee_uses_buyers_own_name_and_still_requires_payment(self):
        result = self.client.post('/api/products/checkout/', {'key': str(uuid4()), 'lines': self.books(1), 'delivery_mode': 'courier', 'collector_name': 'شخص دیگر', 'expected_shipping_fee': 0}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        order = Order.objects.get(pk=result.data['id'])
        self.assertEqual(order.payment.base_amount, 200000)
        self.assertEqual(order.payment.status, 'pending_proof')
        self.assertEqual(order.payment.shipment.recipient_name, self.buyer.full_name)
        self.assertEqual(order.payment.shipment.delivery_method, 'courier')
        self.assertEqual(order.payment.shipment.shipping_fee, 0)

    def test_telegram_username_validation_and_normalization(self):
        staff = User.objects.create_user('09122220000', role='creator')
        self.client.force_authenticate(staff)
        result = self.client.patch('/api/admin/store-settings/', {'support_telegram': '@dayana_books'}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['support_telegram'], 'dayana_books')
        self.assertEqual(self.client.patch('/api/admin/store-settings/', {'support_telegram': 'https://bad.test'}, format='json').status_code, 400)

    def test_paid_ready_shelf_courier_needs_no_second_receipt(self):
        from merchandise.services import fulfill_purchase
        from django.db import transaction
        result = self.client.post('/api/products/checkout/', {'key': str(uuid4()), 'lines': self.books(1)}, format='json')
        order = Order.objects.get(pk=result.data['id'])
        order.status = 'paid'
        order.save()
        payment = order.payment
        payment.status = 'verified'
        payment.save()
        with transaction.atomic():
            fulfill_purchase(order, indices=[0])
        result = self.client.post('/api/shipping/ship-shelf/', {'stock_item_ids': [order.stock_items.get().pk], 'delivery_method': 'courier', 'expected_shipping_fee': 0}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data['status'], 'preparing')
        self.assertEqual(result.data['payment']['status'], 'verified')
        self.assertEqual(result.data['recipient_name'], self.buyer.full_name)
        self.assertEqual(result.data['shipping_fee'], '0')
        staff = User.objects.create_user('09123330000', role='creator')
        self.client.force_authenticate(staff)
        url = f"/api/shipping/{result.data['id']}/mark-shipped/"
        self.assertEqual(self.client.post(url, {}).status_code, 400)
        self.assertEqual(self.client.post(url, {'tracking_code': 'PEIK-123'}).status_code, 200)
