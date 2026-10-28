from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from accounts.models import User
from .models import Product, BundleComponent, Purchase


class ManualAvailabilityConcurrencyTests(TransactionTestCase):
    def test_bundle_and_single_purchase_are_not_limited_by_legacy_quantity(self):
        buyers = [User.objects.create_user(f'0912123400{i}') for i in range(2)]
        component = Product.objects.create(title='Last poster', category='poster', price=50000, quantity=1, is_active=True)
        bundle = Product.objects.create(title='Bundle', category='bundle', price=45000, is_active=True, is_bundle=True)
        BundleComponent.objects.create(bundle=bundle, product=component)
        start = Barrier(2)
        def purchase(args):
            buyer, product = args
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(buyer)
                start.wait(timeout=10)
                return client.post('/api/products/checkout/', {'key': str(uuid4()), 'lines': [{'product_id': product.pk, 'quantity': 1, 'expected_price': product.price}]}, format='json').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(purchase, zip(buyers, [component, bundle])))
        self.assertEqual(sorted(statuses), [201, 201])
        self.assertEqual(Purchase.objects.count(), 2)
        component.refresh_from_db()
        self.assertEqual(component.quantity, 1)
