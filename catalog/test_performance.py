from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from publisher_catalog.models import Edition, Publisher, EditionContribution
from .models import Book, BookContribution, Person
from .serializers import BookSerializer
from .querysets import with_card_data


class BookCardQueriesTests(TestCase):
    def test_cards_use_four_queries_and_preserve_freshness_and_credits(self):
        publisher = Publisher.objects.create(name='Test publisher')
        person = Person.objects.create(name='Test author')
        for i in range(15):
            book = Book.objects.create(title=f'Book {i}')
            BookContribution.objects.create(book=book, person=person, role='author')
            edition = Edition.objects.create(book=book, publisher=publisher, price=200000, last_synced_at=timezone.now())
            EditionContribution.objects.create(edition=edition, person=person, role='translator')
        Edition.objects.create(book=book, publisher=Publisher.objects.create(name='Stale publisher'), price=100000, last_synced_at=timezone.now()-timedelta(days=100))
        Edition.objects.filter(price=100000).update(last_synced_at=timezone.now()-timedelta(days=100))
        expected = BookSerializer(Book.objects.order_by('pk'), many=True).data
        with self.assertNumQueries(4):
            actual = BookSerializer(with_card_data(Book.objects.order_by('pk')), many=True).data
        self.assertEqual(actual, expected)
        self.assertEqual(actual[-1]['price_info']['price'], 200000)
