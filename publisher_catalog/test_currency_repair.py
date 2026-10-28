import json
import tempfile
from pathlib import Path
from io import StringIO
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from django.core.management import call_command
from django.utils import timezone
from accounts.models import User
from catalog.models import Book
from publisher_catalog.models import Publisher, Edition
from requests_orders.models import Quote, Order
from payments.models import Payment


class CurrencyRepairTests(TestCase):
    def test_preserves_consistency_manual_changes_and_repeat_runs(self):
        folder = Path(tempfile.mkdtemp())
        book = Book.objects.create(title='Legacy')
        publisher = Publisher.objects.create(name='Publisher')
        edition = Edition.objects.create(book=book, publisher=publisher, price=2000000, price_review_note='source mismatch')
        buyer = User.objects.create_user('09121234567')
        quote = Quote.objects.create(book=book, source_listing=edition, book_cost=2000000, estimated_days=1)
        order = Order.objects.create(buyer=buyer, quote=quote, total_price=2000000, status='sourcing')
        payment = Payment.objects.create(order=order, base_amount=2000000, status='verified')
        audit = folder/'source.json'
        audit.write_text(json.dumps({'applied': True, 'entries':[{'edition':edition.pk,'book':book.pk,'before':'2000000','status':'unresolved'}]}))
        cutoff = timezone.now().isoformat()
        def run(name, apply=False):
            call_command('finish_legacy_toman_conversion', source_audit=str(audit), legacy_before=cutoff, report=str(folder/name), apply=apply, stdout=StringIO())
        run('dry.json')
        edition.refresh_from_db()
        self.assertEqual(edition.price,2000000)
        run('apply.json',True)
        for model, field in [(edition,'price'),(quote,'book_cost'),(order,'total_price'),(payment,'base_amount')]:
            model.refresh_from_db()
            self.assertEqual(getattr(model,field),Decimal(200000))
        self.assertEqual(edition.price_review_note,'source mismatch')
        self.assertEqual(payment.status,'verified')
        client = APIClient()
        detail = client.get(f'/api/catalog/{book.pk}/').data
        self.assertEqual(Decimal(str(detail['price_info']['price'])), Decimal(200000))
        self.assertEqual(Decimal(str(detail['editions'][0]['price'])), Decimal(200000))
        client.force_authenticate(buyer)
        orders = client.get('/api/orders/mine/').data
        self.assertEqual(Decimal(str(orders[0]['total_price'])), Decimal(200000))
        self.assertEqual(Decimal(str(orders[0]['payment']['amount_expected'])), Decimal(200000))
        staff = User.objects.create_user('09121234568', role='creator')
        client.force_authenticate(staff)
        self.assertEqual(Decimal(str(client.get('/api/orders/all/').data[0]['total_price'])), Decimal(200000))
        admin_book = client.get(f'/api/catalog/admin/books/{book.pk}/').data
        self.assertEqual(Decimal(str(admin_book['editions'][0]['price'])), Decimal(200000))
        run('again.json',True)
        self.assertEqual(json.loads((folder/'again.json').read_text())['changes'],[])
        edition.price=300000
        edition.save()
        run('manual.json',True)
        edition.refresh_from_db()
        self.assertEqual(edition.price,300000)
