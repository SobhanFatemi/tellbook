from datetime import timedelta
from uuid import uuid4

from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import User
from catalog.models import Book
from publisher_catalog.models import Edition, Publisher
from requests_orders.models import Order
from payments.models import Payment
from payments.tasks import auto_cancel_unpaid_payments
from payments.tests import receipt
from stock.tasks import expire_stock_items
from stock.models import StockItem
from shipping.models import ShippingAddress, Shipment
from core.models import StoreSettings
from .models import Product, BundleComponent


class ProductPurchaseTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user('09121111111')
        self.staff = User.objects.create_user('09122222222', role='creator')
        self.client.force_authenticate(self.buyer)
        self.poster = Product.objects.create(title='پوستر', category='پوستر', price=75000, quantity=3, is_active=True)
        self.bookmark = Product.objects.create(title='بوکمارک', category='بوکمارک', price=69000, quantity=3, is_active=True)
        self.bundle = Product.objects.create(title='پک پاییز', category='پک', price=130000, is_bundle=True, is_active=True, featured=True)
        BundleComponent.objects.create(bundle=self.bundle, product=self.poster, quantity=1)
        BundleComponent.objects.create(bundle=self.bundle, product=self.bookmark, quantity=1)
        StoreSettings.objects.create(pk=1, shipping_fee=50000)
        self.address = ShippingAddress.objects.create(user=self.buyer, full_name='Test', phone=self.buyer.phone, province='تهران', city='تهران', address_line='خیابان تست', postal_code='1111111111')

    def payload(self, products=None, **kwargs):
        return {'key': str(uuid4()), 'lines': [{'product_id': p.pk, 'quantity': n, 'expected_price': p.price} for p,n in (products or [(self.bundle,1)])], **kwargs}

    def buy(self, payload=None):
        response = self.client.post('/api/products/checkout/', payload or self.payload(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Order.objects.get(pk=response.data['id'])

    def approve(self, order):
        self.client.force_authenticate(self.buyer)
        response = self.client.post(f'/api/payments/{order.pk}/proof/', {'proof_image': receipt()}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(self.staff)
        response = self.client.post(f'/api/payments/{order.payment.pk}/verify/', {'approve': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(self.buyer)
        order.refresh_from_db()

    def mark_ready(self, order, indices):
        self.client.force_authenticate(self.staff)
        response = self.client.post(f'/api/products/admin/orders/{order.pk}/ready/', {'indices': indices}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(self.buyer)
        order.refresh_from_db()

    def test_eight_identical_books_ready_together(self):
        book = Book.objects.create(title='Eight copies')
        publisher = Publisher.objects.create(name='Test publisher')
        edition = Edition.objects.create(book=book, publisher=publisher, price=320000)
        order = self.buy({'key': str(uuid4()), 'lines': [{'edition_id': edition.pk, 'quantity': 8, 'expected_price': 320000}]})
        self.approve(order)
        self.mark_ready(order, list(range(8)))
        self.assertEqual(order.stock_items.count(), 8)
        self.assertEqual(order.status, 'stock_ready')
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f'/api/products/admin/orders/{order.pk}/ready/', {'indices': list(range(8))}, format='json').status_code, 400)
        self.assertEqual(order.stock_items.count(), 8)

    def test_manual_availability_and_idempotency(self):
        self.poster.quantity = 0  # Legacy count must not restrict new purchases.
        self.poster.save()
        payload = self.payload([(self.bundle, 2), (self.poster, 1)])
        order = self.buy(payload)
        self.assertEqual(self.buy(payload).pk, order.pk)
        self.buy()
        self.assertEqual(Order.objects.count(), 2)
        self.poster.is_active = False
        self.poster.save()
        denied = self.client.post('/api/products/checkout/', self.payload(), format='json')
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(self.client.get('/api/products/?featured=1').data, [])
        self.assertEqual(order.merchandise.units[0]['allocations'], {})

    def test_reservation_expiry_restores_once(self):
        order = self.buy()
        Payment.objects.filter(order=order).update(auto_cancel_at=timezone.now()-timedelta(seconds=1))
        auto_cancel_unpaid_payments()
        auto_cancel_unpaid_payments()
        self.poster.refresh_from_db()
        self.assertEqual(self.poster.quantity, 3)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

    def test_receipt_pauses_expiry_and_bundle_is_one_shelf_unit(self):
        order = self.buy()
        self.client.post(f'/api/payments/{order.pk}/proof/', {'proof_image': receipt()}, format='multipart')
        Payment.objects.filter(order=order).update(auto_cancel_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(auto_cancel_unpaid_payments()['cancelled'], 0)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f'/api/payments/{order.payment.pk}/verify/', {'approve': True}).status_code, 200)
        self.client.force_authenticate(self.buyer)
        self.assertFalse(order.stock_items.exists())
        self.mark_ready(order, [0])
        shelf = self.client.get('/api/stock/shelf/mine/').data
        self.assertEqual(len(shelf), 1)
        self.assertEqual(shelf[0]['title'], 'پک پاییز')
        self.assertEqual(len(shelf[0]['merchandise_data']['contents']), 2)
        self.assertAlmostEqual((order.stock_items.get().expires_at-timezone.now()).total_seconds(), 30*86400, delta=5)

    def test_price_change_and_private_component_cannot_be_bought(self):
        payload = self.payload()
        payload['lines'][0]['expected_price'] = 1
        self.assertEqual(self.client.post('/api/products/checkout/', payload, format='json').status_code, 400)
        self.poster.sold_separately = False
        self.poster.save()
        self.assertEqual(self.client.get(f'/api/products/{self.poster.pk}/').status_code, 404)
        self.assertEqual(self.client.post('/api/products/checkout/', self.payload([(self.poster, 1)]), format='json').status_code, 400)
        self.buy()  # still purchasable inside its bundle

    def test_sourced_bundle_only_ready_after_staff_confirmation_and_snapshot_stable(self):
        self.bookmark.fulfillment = 'source'
        self.bookmark.quantity = 0
        self.bookmark.save()
        order = self.buy()
        self.bundle.components.all().delete()
        self.bundle.title = 'Changed'
        self.bundle.save()
        self.approve(order)
        self.assertEqual(order.status, 'paid')
        self.assertFalse(order.stock_items.exists())
        self.assertEqual(self.client.post(f'/api/products/admin/orders/{order.pk}/ready/', {'indices': [0]}, format='json').status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f'/api/products/admin/orders/{order.pk}/ready/', {'indices': [0]}, format='json').status_code, 200)
        self.assertEqual(order.stock_items.get().title, 'پک پاییز')
        self.assertEqual(len(order.stock_items.get().merchandise_data['contents']), 2)
        self.assertEqual(self.client.post(f'/api/products/admin/orders/{order.pk}/ready/', {'indices': [0]}, format='json').status_code, 400)

    def test_mixed_books_and_accessories_share_payment(self):
        book = Book.objects.create(title='کتاب')
        edition = Edition.objects.create(book=book, publisher=Publisher.objects.create(name='ناشر'), price=200000)
        payload = self.payload()
        payload['lines'].append({'edition_id': edition.pk, 'quantity': 1, 'expected_price': 200000})
        order = self.buy(payload)
        self.assertEqual(order.payment.base_amount, 330000)
        self.assertEqual(len(order.merchandise.units), 2)
        self.assertTrue(order.merchandise.requires_sourcing)

    def test_partial_shipping_and_expiry_only_refunds_remaining_unit(self):
        order = self.buy(self.payload([(self.bundle, 1), (self.poster, 1)]))
        self.approve(order)
        self.mark_ready(order, [0, 1])
        items = list(order.stock_items.order_by('pk'))
        response = self.client.post(f'/api/shipping/ship-shelf/{self.address.pk}/', {'stock_item_ids': [items[0].pk], 'expected_shipping_fee': 50000}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        shipment = Shipment.objects.get(pk=response.data['id'])
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f'/api/shipping/{shipment.pk}/mark-shipped/', {'tracking_code': '123'}).status_code, 409)
        shipment.payment.status = 'verified'
        shipment.payment.save()
        shipment.status = 'preparing'
        shipment.save()
        self.assertEqual(self.client.post(f'/api/shipping/{shipment.pk}/mark-shipped/', {'tracking_code': '123'}).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'stock_ready')
        StockItem.objects.filter(pk=items[1].pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        expire_stock_items()
        expire_stock_items()
        self.assertEqual(order.refunds.count(), 1)
        self.assertEqual(order.refunds.get().refund_amount, 75000)
        order.refresh_from_db()
        self.assertEqual(order.status, 'shipped')

    def test_failed_sourcing_refunds_shipping_and_releases_inventory(self):
        self.bookmark.fulfillment = 'source'
        self.bookmark.quantity = 0
        self.bookmark.save()
        order = self.buy(self.payload(delivery_mode='ship_when_ready', address_id=self.address.pk, expected_shipping_fee=50000))
        self.approve(order)
        self.client.force_authenticate(self.staff)
        response = self.client.post(f'/api/orders/{order.pk}/fail/', {'failure_reason': 'ناموجود'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(order.refunds.get().refund_amount, 180000)
        self.poster.refresh_from_db()
        self.assertEqual(self.poster.quantity, 3)

    def test_admin_validation_permissions_images_and_components(self):
        self.assertEqual(self.client.get('/api/products/admin/').status_code, 403)
        self.client.force_authenticate(self.staff)
        data = {'title': 'New', 'category': 'پک', 'price': 100, 'quantity': 0, 'lead_days': 0, 'is_bundle': True, 'is_active': True, 'components': []}
        self.assertEqual(self.client.post('/api/products/admin/', data, format='json').status_code, 400)
        data['components'] = [{'product': self.bundle.pk, 'quantity': 1}]
        self.assertEqual(self.client.post('/api/products/admin/', data, format='json').status_code, 400)
        data['components'] = [{'product': self.poster.pk, 'quantity': 1}]
        result = self.client.post('/api/products/admin/', data, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        result = self.client.post(f'/api/products/admin/{result.data["id"]}/images/', {'image': receipt(), 'caption': 'test'}, format='multipart')
        self.assertEqual(result.status_code, 201, result.data)


    def test_ready_unit_enters_shelf_while_other_unit_is_sourced(self):
        self.bookmark.fulfillment = 'source'
        self.bookmark.quantity = 0
        self.bookmark.save()
        order = self.buy(self.payload([(self.poster, 1), (self.bookmark, 1)]))
        self.approve(order)
        self.assertEqual(order.status, 'paid')
        self.assertFalse(order.stock_items.exists())
        self.mark_ready(order, [0])
        shelf = self.client.get('/api/stock/shelf/mine/').data
        self.assertEqual(len(shelf), 1)
        self.assertEqual(shelf[0]['title'], self.poster.title)
        self.assertNotIn('allocations', shelf[0]['merchandise_data'])
        first_deadline = order.stock_items.get().expires_at
        self.client.force_authenticate(self.staff)
        result = self.client.post(f'/api/products/admin/orders/{order.pk}/ready/', {'indices': [1]}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        order.refresh_from_db()
        self.assertEqual(order.status, 'stock_ready')
        self.assertEqual(order.stock_items.count(), 2)
        self.assertEqual(order.stock_items.order_by('pk').first().expires_at, first_deadline)

    def test_sourcing_failure_preserves_already_ready_item(self):
        self.bookmark.fulfillment = 'source'
        self.bookmark.quantity = 0
        self.bookmark.save()
        order = self.buy(self.payload([(self.poster, 1), (self.bookmark, 1)]))
        self.approve(order)
        self.mark_ready(order, [0])
        self.client.force_authenticate(self.staff)
        result = self.client.post(f'/api/orders/{order.pk}/fail/', {'failure_reason': 'ناموجود'})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(order.refunds.get().refund_amount, 69000)
        order.refresh_from_db()
        self.assertEqual(order.status, 'stock_ready')
        self.assertEqual(order.stock_items.get().status, 'ready_to_ship')

    def test_expired_accessory_does_not_create_inventory(self):
        self.bookmark.fulfillment = 'source'
        self.bookmark.quantity = 0
        self.bookmark.save()
        order = self.buy(self.payload([(self.bookmark, 1)]))
        self.approve(order)
        self.client.force_authenticate(self.staff)
        self.client.post(f'/api/products/admin/orders/{order.pk}/ready/', {'indices': [0]}, format='json')
        order.stock_items.update(expires_at=timezone.now()-timedelta(seconds=1))
        expire_stock_items()
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.quantity, 0)
        self.client.force_authenticate(self.buyer)
        next_order = self.buy(self.payload([(self.bookmark, 1)]))
        self.approve(next_order)
        self.assertEqual(next_order.status, 'paid')
        self.assertFalse(next_order.stock_items.exists())

    def test_stale_admin_edit_cannot_overwrite_newer_changes(self):
        self.client.force_authenticate(self.staff)
        original = next(p for p in self.client.get('/api/products/admin/').data if p['id'] == self.poster.pk)
        self.client.force_authenticate(self.buyer)
        self.poster.description = 'newer edit'
        self.poster.save()
        self.client.force_authenticate(self.staff)
        result = self.client.patch(f'/api/products/admin/{self.poster.pk}/', {'description': 'stale edit', 'expected_updated_at': original['updated_at']}, format='json')
        self.assertEqual(result.status_code, 409)
        current = next(p for p in self.client.get('/api/products/admin/').data if p['id'] == self.poster.pk)
        result = self.client.patch(f'/api/products/admin/{self.poster.pk}/', {'description': 'updated', 'expected_updated_at': current['updated_at']}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.poster.refresh_from_db()
        self.assertEqual(self.poster.description, 'updated')

    def test_sourced_book_expiry_refunds_without_creating_sellable_copy(self):
        book = Book.objects.create(title='کتاب تخفیف‌دار', discount_type='percentage', discount_value=20, discount_active=True)
        edition = Edition.objects.create(book=book, publisher=Publisher.objects.create(name='ناشر تازه'), price=200000)
        payload = {'key': str(uuid4()), 'lines': [{'edition_id': edition.pk, 'quantity': 1, 'expected_price': 160000}]}
        order = self.buy(payload)
        self.approve(order)
        self.client.force_authenticate(self.staff)
        result = self.client.post(f'/api/products/admin/orders/{order.pk}/ready/', {'indices': [0]}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        order.stock_items.update(expires_at=timezone.now()-timedelta(seconds=1))
        expire_stock_items()
        self.assertFalse(StockItem.objects.filter(book=book, status='available').exists())
        self.assertEqual(order.refunds.get().refund_amount, 160000)

    def test_mixed_prepaid_order_waits_for_sourcing_and_keeps_single_shipping_fee(self):
        self.bookmark.fulfillment = 'source'
        self.bookmark.quantity = 0
        self.bookmark.save()
        order = self.buy(self.payload([(self.poster, 1), (self.bookmark, 1)], delivery_mode='ship_when_ready', address_id=self.address.pk, expected_shipping_fee=50000))
        self.approve(order)
        self.mark_ready(order, [0])
        shipment = Shipment.objects.get(pk=order.payment.shipment_id)
        self.assertEqual(shipment.status, 'waiting_books')
        self.assertEqual(order.stock_items.count(), 1)
        self.client.force_authenticate(self.staff)
        result = self.client.post(f'/api/orders/{order.pk}/fail/', {'failure_reason': 'تهیه نشد'})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(order.refunds.get().refund_amount, 69000)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, 'preparing')
        result = self.client.post(f'/api/shipping/{shipment.pk}/mark-shipped/', {'tracking_code': '123'})
        self.assertEqual(result.status_code, 200, result.data)

    def test_ready_unit_can_ship_before_sourced_unit(self):
        self.bookmark.fulfillment = 'source'
        self.bookmark.quantity = 0
        self.bookmark.save()
        order = self.buy(self.payload([(self.poster, 1), (self.bookmark, 1)]))
        self.approve(order)
        self.mark_ready(order, [0])
        result = self.client.post(f'/api/shipping/ship-shelf/{self.address.pk}/', {'stock_item_ids': [order.stock_items.get().pk], 'expected_shipping_fee': 50000}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        shipment = Shipment.objects.get(pk=result.data['id'])
        shipment.payment.status = 'verified'
        shipment.payment.save()
        shipment.status = 'preparing'
        shipment.save()
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f'/api/shipping/{shipment.pk}/mark-shipped/', {'tracking_code': '123'}).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.client.post(f'/api/orders/{order.pk}/fail/', {'failure_reason': 'ناموجود'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.refunds.get().refund_amount, 69000)
