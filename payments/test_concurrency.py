from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Book
from requests_orders.models import Order, Quote
from stock.models import StockItem


class StockConcurrencyTests(TransactionTestCase):
    def test_two_buyers_cannot_purchase_the_same_copy(self):
        buyers = [User.objects.create_user(f'0912123456{i}') for i in range(2)]
        book = Book.objects.create(title='One physical copy')
        StockItem.objects.create(book=book, unit_price=100000)
        start = Barrier(2)

        def purchase(buyer):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(buyer)
                start.wait(timeout=10)
                return client.post(f'/api/orders/buy/stock/{book.pk}/', {}).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(purchase, buyers))
        self.assertEqual(sorted(statuses), [410, 410])
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Quote.objects.count(), 0)
