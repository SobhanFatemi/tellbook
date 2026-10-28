from rest_framework.test import APITestCase
from catalog.models import Book, Person, BookContribution


class CatalogSearchTests(APITestCase):
    def search(self, **params):
        return self.client.get('/api/catalog/search/', params)

    def test_persian_variants_numbers_and_spacing(self):
        book = Book.objects.create(title='كتابِ شازده\u200cكوچولو ۲')
        for query in ['کتاب شازده کوچولو 2', 'شازده کوچولو ٢', 'کتابِ شازده']:
            self.assertEqual([row['id'] for row in self.search(q=query).data['results']], [book.pk])
        self.assertEqual(self.search(q='شازده 3').data['count'], 0)

    def test_author_and_exact_title_ranking(self):
        longer = Book.objects.create(title='الف کتاب شب')
        exact = Book.objects.create(title='شب')
        author_book = Book.objects.create(title='آثار منتخب')
        person = Person.objects.create(name='علي کريمي')
        BookContribution.objects.create(book=author_book, person=person, role='author')
        self.assertEqual(self.search(q='شب').data['results'][0]['id'], exact.pk)
        self.assertEqual(self.search(q='علی کریمی').data['results'][0]['id'], author_book.pk)

    def test_every_result_is_reachable_without_duplicates(self):
        Book.objects.bulk_create([Book(title=f'Book {i:03}') for i in range(61)])
        Book.objects.create(title='Hidden', needs_review=True)
        ids = []
        for page in [1, 2, 3]:
            response = self.search(page=page)
            self.assertEqual(response.data['count'], 61)
            ids.extend(row['id'] for row in response.data['results'])
        self.assertEqual(len(set(ids)), 61)
        self.assertEqual(len(ids), 61)

    def test_invalid_filters_are_validation_errors(self):
        for params in [{'publisher_id':'oops'}, {'min_price':-1}, {'min_price':2,'max_price':1}, {'print_year': 'bad'}]:
            self.assertEqual(self.search(**params).status_code, 400)
