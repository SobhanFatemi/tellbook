from pathlib import Path
import tempfile
from django.test import TestCase
from django.core.management import call_command
from rest_framework.test import APIClient
from accounts.models import User
from catalog.models import Book
from catalog.categories import normalize_category
from publisher_catalog.parsing import clean_cell


class CategoryTests(TestCase):
    def test_conservative_normalization(self):
        for value in ['گروه 0','گروه ۰','0', '٠']:
            self.assertEqual(normalize_category(value), '')
            self.assertEqual(clean_cell('category', value), '')
        self.assertEqual(normalize_category(' رمان\u200cهاي خارجي '),'رمان خارجی')
        self.assertEqual(normalize_category('داستان خارجي'),'داستان خارجی')
        self.assertEqual(normalize_category('کودک'),'کودک')
        self.assertNotEqual(normalize_category('رمان خارجی'),normalize_category('داستان خارجی'))

    def test_existing_cleanup_manual_creation_and_public_filters(self):
        root=Path(tempfile.mkdtemp())
        placeholder=Book.objects.create(title='Unclassified',category='گروه 0')
        Book.objects.create(title='A',category='رمان هاي خارجي')
        Book.objects.create(title='B',category='رمان خارجي')
        call_command('normalize_categories', report=str(root/'preview.json'))
        placeholder.refresh_from_db()
        self.assertEqual(placeholder.category,'گروه 0')
        call_command('normalize_categories', report=str(root/'applied.json'), apply=True)
        placeholder.refresh_from_db()
        self.assertEqual(placeholder.category,'')
        client=APIClient()
        self.assertEqual(client.get('/api/catalog/search/filters/').data['categories'],['رمان خارجی'])
        staff=User.objects.create_user('09121234568',role='creator')
        client.force_authenticate(staff)
        response=client.post('/api/catalog/admin/books/', {'title':'کتاب دستی','authors':['نویسنده'],'category':'رمان هاي خارجي'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        book=Book.objects.get(pk=response.data['id'])
        self.assertEqual(book.category,'رمان خارجی')
        self.assertIn('category',book.import_locked_fields)
        self.assertEqual(book.book_contributions.get().person.name,'نویسنده')
        client.force_authenticate(None)
        self.assertEqual(len(client.get('/api/catalog/search/',{'category':'رمان هاي خارجي'}).data['results']),3)
