from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from requests_orders.models import BookRequest
from core.models import AdminSectionRead


class AdminActivityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(phone='09120000001', role='creator')
        self.other = User.objects.create_user(phone='09120000002', role='creator')
        self.buyer = User.objects.create_user(phone='09120000003')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.item = BookRequest.objects.create(buyer=self.buyer, title='آزمون')

    def snapshot(self):
        response = self.client.get('/api/admin/activity/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def read(self, snapshot, section='requests'):
        return self.client.post('/api/admin/activity/', {'section': section, 'snapshot': snapshot['snapshot']})

    def test_seen_state_is_per_user_and_section(self):
        snapshot = self.snapshot()
        self.assertEqual(snapshot['counts']['requests'], 1)
        self.assertEqual(self.read(snapshot).status_code, 200)
        self.assertEqual(self.snapshot()['counts']['requests'], 0)
        self.assertFalse(AdminSectionRead.objects.filter(section='orders').exists())
        self.client.force_authenticate(self.other)
        self.assertEqual(self.snapshot()['counts']['requests'], 1)
        self.assertEqual(self.read(snapshot).status_code, 400)

    def test_new_changes_survive_snapshot_and_reappear_once(self):
        old = self.snapshot()
        self.item.title = 'تغییر'
        self.item.save()
        self.read(old)
        self.assertEqual(self.snapshot()['counts']['requests'], 1)
        fresh = self.snapshot()
        self.read(fresh)
        self.read(old)
        self.assertEqual(self.snapshot()['counts']['requests'], 0)
        self.item.save()
        self.item.save()
        self.assertEqual(self.snapshot()['counts']['requests'], 1)
        self.item.status = 'ready'
        self.item.save()
        self.assertEqual(self.snapshot()['counts']['requests'], 0)

    def test_invalid_snapshot_and_buyer_access(self):
        self.assertEqual(self.read({'snapshot':'invalid'}).status_code, 400)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get('/api/admin/activity/').status_code, 403)
        self.assertEqual(self.read({'snapshot':'invalid'}).status_code, 403)

    def test_receipt_update_counts_order_without_order_save(self):
        from requests_orders.models import Order, Quote
        from payments.models import Payment
        quote = Quote.objects.create(book_cost=100000, estimated_days=2)
        order = Order.objects.create(quote=quote, buyer=self.buyer, total_price=100000)
        payment = Payment.objects.create(order=order, base_amount=100000)
        self.read(self.snapshot(), 'orders')
        self.assertEqual(self.snapshot()['counts']['orders'], 0)
        payment.status = Payment.Status.PENDING_VERIFICATION
        payment.save()
        self.assertEqual(self.snapshot()['counts']['orders'], 1)

    def test_standalone_shipping_receipt_counts_in_orders(self):
        from shipping.models import Shipment
        from payments.models import Payment
        shipment = Shipment.objects.create(buyer=self.buyer, recipient_name='Test', recipient_phone=self.buyer.phone, shipping_fee=175000)
        payment = Payment.objects.create(shipment=shipment, base_amount=175000, status='pending_verification')
        self.assertEqual(self.snapshot()['counts']['orders'], 1)
        self.read(self.snapshot(), 'orders')
        self.assertEqual(self.snapshot()['counts']['orders'], 0)
        payment.save()
        self.assertEqual(self.snapshot()['counts']['orders'], 1)
