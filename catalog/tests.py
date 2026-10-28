import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from decimal import Decimal
import pandas as pd
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from catalog.models import Book, BookContribution, Person, BookPost
from publisher_catalog.models import Publisher, Edition, EditionContribution
from publisher_catalog.parsing import read_publisher_rows
from requests_orders.models import Order, Quote
from stock.models import StockItem
from payments.tests import receipt


class AdminCatalogTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('09121234568', role='creator')
        self.buyer = User.objects.create_user('09121234567')
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.book = Book.objects.create(title='کتاب آزمایشی')
        self.publisher = Publisher.objects.create(name='ناشر')
        self.edition = Edition.objects.create(book=self.book, publisher=self.publisher, price=100000, isbn='9781234567890')
        self.person = Person.objects.create(name='نویسنده')
        BookContribution.objects.create(book=self.book, person=self.person)

    def test_store_inventory_endpoints_removed(self):
        self.assertEqual(self.client.get('/api/stock/admin/available/').status_code, 404)
        self.assertEqual(self.client.get('/api/stock/in-stock/').status_code, 404)

    def test_dashboard_includes_every_order_state(self):
        for status, _ in Order.Status.choices:
            quote = Quote.objects.create(book=self.book, book_cost=100000, estimated_days=1)
            Order.objects.create(buyer=self.buyer, quote=quote, status=status, total_price=100000)
        counts = self.client.get('/api/admin/dashboard/').data['order_counts']
        self.assertEqual(counts, {status: 1 for status, _ in Order.Status.choices})

    def test_review_corrects_authors_and_publishes_only_after_approval(self):
        self.book.needs_review = True
        self.book.save()
        self.assertEqual(len(self.client.get('/api/publishers/needs-review/').data), 1)
        response = self.client.patch(f'/api/catalog/{self.book.pk}/edit/', {'authors': ['نویسنده درست'], 'needs_review': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(self.book.book_contributions.values_list('person__name', flat=True)), ['نویسنده درست'])
        self.assertEqual(len(self.client.get('/api/publishers/needs-review/').data), 0)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.patch(f'/api/catalog/{self.book.pk}/edit/', {'title': 'تغییر'}, format='json').status_code, 403)

    def test_credits_use_translator_from_displayed_edition(self):
        translator = Person.objects.create(name='مترجم')
        EditionContribution.objects.create(edition=self.edition, person=translator)
        response = self.client.get(f'/api/catalog/{self.book.pk}/')
        self.assertEqual(response.data['authors'], ['نویسنده'])
        self.assertEqual(response.data['translators'], ['مترجم'])
        self.assertEqual(response.data['credit_publisher'], 'ناشر')

    def test_posts_drafts_images_links_updates_and_permissions(self):
        url = '/api/catalog/admin/posts/'
        response = self.client.post(url, {'title':'معرفی', 'body':'درباره کتاب', 'is_published':'false', 'book_ids':json.dumps([self.book.pk]), 'uploads':[receipt(), receipt()]}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        images = response.data['images']
        self.assertEqual(len(images), 2)
        self.assertEqual(self.client.get('/api/catalog/posts/').data, [])
        response = self.client.patch(f'{url}{pk}/', {'is_published':True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(self.client.get('/api/catalog/posts/').data), 1)
        response = self.client.patch(f'{url}{pk}/', {'book_ids':'[]', 'keep_image_ids':json.dumps([images[1]['id']])}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['books'], [])
        self.assertEqual(len(response.data['images']), 1)
        self.assertEqual(self.client.patch(f'{url}{pk}/', {'keep_image_ids': []}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'{url}{pk}/', {'keep_image_ids': [9999]}, format='json').status_code, 400)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.patch(f'{url}{pk}/', {'title':'bad'}, format='json').status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.delete(f'{url}{pk}/').status_code, 204)
        self.assertFalse(BookPost.objects.exists())

    def test_post_cannot_publish_without_image_or_link_review_book(self):
        self.book.needs_review = True
        self.book.save()
        for payload in [dict(is_published=True), dict(book_ids=[self.book.pk])]:
            response = self.client.post('/api/catalog/admin/posts/', {'title':'معرفی', 'body':'متن', **payload}, format='json')
            self.assertEqual(response.status_code, 400)

    def test_import_currency_is_explicit_and_normalized_to_toman(self):
        profile = SimpleNamespace(price_unit='unknown', sheet_name=None, header_row_index=0, column_mapping={'title':'title','price':'price'}, mode='single')
        with self.assertRaises(ValueError):
            read_publisher_rows(BytesIO(), profile)
        with patch('publisher_catalog.parsing.pd.read_excel', return_value=pd.DataFrame([{'title':'کتاب','price':7800000}])):
            profile.price_unit = 'rial'
            self.assertEqual(read_publisher_rows(BytesIO(), profile)[0][0]['price'], Decimal(780000))
            profile.price_unit = 'toman'
            self.assertEqual(read_publisher_rows(BytesIO(), profile)[0][0]['price'], Decimal(7800000))

    def test_import_profile_unit_update_is_staff_only_and_never_reprices(self):
        from publisher_catalog.models import PublisherImportProfile
        profile = PublisherImportProfile.objects.create(publisher=self.publisher, column_mapping={"title":"title","price":"price"})
        url = f'/api/publishers/import-profiles/{profile.pk}/'
        self.assertEqual(self.client.patch(url, {"price_unit":"rial"}, format='json').status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.price_unit, 'rial')
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.price, 100000)
        self.assertEqual(self.client.patch(url, {"price_unit":"unknown"}, format='json').status_code, 400)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.patch(url, {"price_unit":"toman"}, format='json').status_code, 403)

    def test_verified_author_alias_does_not_return_on_reimport(self):
        from publisher_catalog.services import set_book_author
        Person.objects.create(name='جورج اوورل')
        Person.objects.create(name='جورج اورول')
        set_book_author(self.book, 'جورج اوورل')
        names = list(self.book.book_contributions.values_list('person__name', flat=True))
        self.assertIn('جورج اورول', names)
        self.assertNotIn('جورج اوورل', names)


class SearchPriceBoundsTests(TestCase):
    def test_bounds_cover_all_visible_active_editions(self):
        publisher = Publisher.objects.create(name='ناشر بازه')
        for index in range(55):
            book = Book.objects.create(title=f'کتاب {index}')
            Edition.objects.create(book=book, publisher=publisher, price=100000 + index * 10000)
        hidden = Book.objects.create(title='بازبینی', needs_review=True)
        Edition.objects.create(book=hidden, publisher=publisher, price=1)
        Edition.objects.create(book=Book.objects.create(title='غیرفعال'), publisher=publisher, price=9000000, is_active=False)
        response = APIClient().get('/api/catalog/search/filters/?q=unmatched&min_price=500000')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['price_bounds'], {'min_price': 100000, 'max_price': 640000})

    def test_empty_and_single_price_catalog(self):
        client = APIClient()
        self.assertEqual(client.get('/api/catalog/search/filters/').data['price_bounds'], {'min_price': None, 'max_price': None})
        publisher = Publisher.objects.create(name='ناشر تک قیمت')
        book = Book.objects.create(title='کتاب')
        Edition.objects.create(book=book, publisher=publisher, price=250000)
        self.assertEqual(client.get('/api/catalog/search/filters/').data['price_bounds'], {'min_price': 250000, 'max_price': 250000})
