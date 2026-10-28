from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from catalog.models import Book


class HomepageTests(TestCase):
    def setUp(self):
        self.books = [Book.objects.create(title=f'Book {n}') for n in range(20)]
        self.review = Book.objects.create(title='Review', needs_review=True)
        self.staff = User.objects.create_user('09121234568', role='creator')
        self.client = APIClient()

    def test_random_is_bounded_and_excludes_review(self):
        response = self.client.get('/api/catalog/homepage/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mode'], 'random')
        ids = [book['id'] for book in response.data['books']]
        self.assertEqual(len(set(ids)), 12)
        self.assertNotIn(self.review.pk, ids)

    def test_selection_and_clear_preserve_books(self):
        self.client.force_authenticate(self.staff)
        for book in self.books[:2]:
            response = self.client.patch('/api/catalog/admin/homepage/', {'book_id': book.pk, 'selected': True}, format='json')
            self.assertEqual(response.status_code, 200)
        response = self.client.get('/api/catalog/homepage/')
        self.assertEqual(response.data['mode'], 'manual')
        self.assertEqual({b['id'] for b in response.data['books']}, {b.pk for b in self.books[:2]})
        self.assertEqual(self.client.get('/api/catalog/admin/homepage/').data['selected_count'], 2)
        self.assertEqual(self.client.delete('/api/catalog/admin/homepage/').status_code, 200)
        self.assertEqual(self.client.get('/api/catalog/homepage/').data['mode'], 'random')
        self.assertEqual(Book.objects.count(), 21)

    def test_only_staff_can_select_and_unreviewed_books_are_rejected(self):
        self.assertEqual(self.client.delete('/api/catalog/admin/homepage/').status_code, 401)
        buyer = User.objects.create_user('09121234567')
        self.client.force_authenticate(buyer)
        self.assertEqual(self.client.patch('/api/catalog/admin/homepage/', {'book_id': self.books[0].pk, 'selected': True}, format='json').status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.patch('/api/catalog/admin/homepage/', {'book_id': self.review.pk, 'selected': True}, format='json').status_code, 400)
