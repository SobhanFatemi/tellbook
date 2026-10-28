from io import BytesIO
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from catalog.models import Book
from .models import Publisher, Edition, PublisherImportProfile as Profile, PublisherImportBatch as Batch
from .tasks import process_publisher_import, apply_publisher_import


def workbook(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    stream = BytesIO()
    wb.save(stream)
    return SimpleUploadedFile('catalog.xlsx', stream.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


class CatalogManagementTests(TestCase):
    def test_missing_worksheet_names_the_problem_and_blank_sheet_recovers(self):
        client=APIClient()
        client.force_authenticate(User.objects.create_user('09120000001',role='creator'))
        rows=[['عنوان','قیمت'],['کتاب',3500000]]
        response=client.post('/api/publishers/preview-columns/', {'file':workbook(rows),'sheet_name':'تست نشر ماهی'},format='multipart')
        self.assertEqual(response.status_code,400)
        self.assertIn('برگه «تست نشر ماهی»',response.data['detail'])
        self.assertEqual(response.data['available_sheets'],['Sheet'])
        response=client.post('/api/publishers/preview-columns/', {'file':workbook(rows),'sheet_name':''},format='multipart')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['columns'],['عنوان','قیمت'])
        self.assertFalse(Batch.objects.exists())

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user('09121234568', role='creator')
        self.client.force_authenticate(self.staff)
        self.publisher = Publisher.objects.create(name='ناشر آزمایشی')
        self.book = Book.objects.create(title='باغ آبی', description='متن اصلی')
        self.edition = Edition.objects.create(book=self.book, publisher=self.publisher, price=100000, isbn='1234')
        self.profile = Profile.objects.create(publisher=self.publisher, price_unit='rial', column_mapping={'title':'عنوان', 'price':'قیمت', 'isbn':'شابک', 'description':'شرح'})

    def upload(self, rows=None, complete=False):
        response = self.client.post(f'/api/publishers/import-profiles/{self.profile.pk}/upload/', {'file':workbook(rows or [['عنوان','قیمت','شابک','شرح'], ['باغ آبی',2000000,'1234','متن فایل']]), 'complete_catalog':str(complete).lower(), 'price_unit':'rial'}, format='multipart')
        self.assertEqual(response.status_code, 202, response.data)
        batch = Batch.objects.get(pk=response.data['batch_id'])
        self.assertEqual(batch.status, 'review', batch.error_message)
        return batch

    def confirm(self, batch):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/publishers/import-batches/{batch.pk}/confirm/', {'revision':batch.revision}, format='json')
        batch.refresh_from_db()
        return response

    def test_preview_does_not_write_and_confirm_converts_once(self):
        batch = self.upload()
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.price, 100000)
        self.assertFalse(batch.complete_catalog)
        self.assertEqual(batch.rows.get().data['price'], '200000')
        self.assertEqual(self.confirm(batch).status_code, 202)
        self.assertEqual(batch.status, 'done', batch.error_message)
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.price, 200000)
        apply_publisher_import(batch.pk)
        self.assertEqual(self.confirm(batch).status_code, 200)
        self.assertEqual(Edition.objects.count(), 1)

    def test_manual_corrections_and_cover_survive_reimport(self):
        response = self.client.patch(f'/api/catalog/{self.book.pk}/edit/', {'title':'عنوان اصلاح شده', 'description':'متن دستی', 'authors':['نویسنده درست']}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(f'/api/publishers/editions/{self.edition.pk}/edit/', {'translator_names':['مترجم درست'], 'cover_image_url':'https://example.com/cover.jpg'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        batch = self.upload()
        self.assertEqual(self.confirm(batch).status_code, 202)
        self.assertEqual(batch.status, 'done', batch.error_message)
        self.book.refresh_from_db()
        self.edition.refresh_from_db()
        self.assertEqual((self.book.title, self.book.description), ('عنوان اصلاح شده','متن دستی'))
        self.assertEqual(self.edition.cover_image_url, 'https://example.com/cover.jpg')
        self.assertEqual(self.edition.price, 200000)
        self.assertEqual(self.edition.edition_contributions.get().person.name, 'مترجم درست')

    def test_complete_catalog_is_explicit_scoped_and_skipped_matches_stay(self):
        absent = Edition.objects.create(book=Book.objects.create(title='غایب'), publisher=self.publisher, price=20)
        other = Edition.objects.create(book=self.book, publisher=Publisher.objects.create(name='ناشر دیگر'), price=30)
        delta = self.upload()
        self.assertEqual(delta.deactivations, [])
        full = self.upload([['عنوان','قیمت','شابک','شرح'], ['باغ آبی',2000000,'1234',''], ['داستان کاملاً متفاوت',3000000,'9999','']], True)
        self.assertEqual([x['id'] for x in full.deactivations], [absent.pk])
        row = full.rows.get(book=self.book)
        response = self.client.patch(f'/api/publishers/import-batches/{full.pk}/rows/{row.pk}/', {'decision':'skip'}, format='json')
        self.assertEqual(response.status_code, 200)
        full.refresh_from_db()
        self.assertEqual([x['id'] for x in full.deactivations], [absent.pk])
        self.assertEqual(self.confirm(full).status_code, 202)
        self.assertEqual(full.status, 'done', full.error_message)
        absent.refresh_from_db(); other.refresh_from_db(); self.edition.refresh_from_db()
        self.assertFalse(absent.is_active)
        self.assertTrue(other.is_active)
        self.assertTrue(self.edition.is_active)
        self.assertEqual(self.edition.price, 100000)

    def test_stale_preview_and_revision_rejected(self):
        batch = self.upload()
        response = self.client.post(f'/api/publishers/import-batches/{batch.pk}/confirm/', {'revision':batch.revision-1}, format='json')
        self.assertEqual(response.status_code, 409)
        self.client.patch(f'/api/catalog/{self.book.pk}/edit/', {'description':'تغییر بعدی'}, format='json')
        self.assertEqual(self.confirm(batch).status_code, 400)
        self.assertEqual(batch.status, 'review')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/publishers/import-batches/{batch.pk}/rebuild/')
        self.assertEqual(response.status_code, 202)
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'review', batch.error_message)
        self.assertEqual(self.confirm(batch).status_code, 202)
        self.assertEqual(batch.status, 'done', batch.error_message)

    def test_pending_match_needs_human_decision(self):
        batch = self.upload([['عنوان','قیمت','شابک','شرح'], ['باغ آبی تازه',2000000,'','']])
        row = batch.rows.get()
        self.assertEqual(row.decision, 'pending')
        self.assertEqual(self.confirm(batch).status_code, 400)
        response = self.client.patch(f'/api/publishers/import-batches/{batch.pk}/rows/{row.pk}/', {'decision':'match','book_id':self.book.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        batch.refresh_from_db()
        self.assertEqual(self.confirm(batch).status_code, 202)
        self.assertEqual(batch.status, 'done', batch.error_message)

    def test_invalid_rows_block_full_catalog_and_duplicates_cannot_apply(self):
        batch = self.upload([['عنوان','قیمت','شابک','شرح'], ['باغ آبی',2000000,'1234',''], ['نامعتبر',-10,'','']], True)
        self.assertEqual(batch.rows.filter(decision='skip').count(), 1)
        self.assertEqual(self.confirm(batch).status_code, 400)
        duplicate = self.upload([['عنوان','قیمت','شابک','شرح'], ['باغ آبی',2000000,'1234',''], ['باغ آبی',3000000,'1234','']])
        self.assertEqual(self.confirm(duplicate).status_code, 400)
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.price, 100000)

    def test_profile_snapshot_is_immutable_and_unknown_unit_blocks(self):
        batch = self.upload()
        self.client.patch(f'/api/publishers/import-profiles/{self.profile.pk}/', {'price_unit':'toman'}, format='json')
        self.assertEqual(self.confirm(batch).status_code, 202)
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.price, 200000)
        self.profile.price_unit='unknown'; self.profile.save()
        response=self.client.post(f'/api/publishers/import-profiles/{self.profile.pk}/upload/', {'file':workbook([['عنوان','قیمت']])}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_editing_creation_validation_and_buyer_permissions(self):
        response=self.client.post('/api/catalog/admin/books/', {'title':'کتاب دستی','authors':['نویسنده']}, format='json')
        self.assertEqual(response.status_code,201,response.data)
        book_id=response.data['id']
        response=self.client.post('/api/catalog/admin/editions/', {'book':book_id,'publisher':self.publisher.pk,'price':'150000','translator_names':['مترجم'], 'clear_cover':False}, format='json')
        self.assertEqual(response.status_code,201,response.data)
        edition_id=response.data['id']
        response=self.client.get(f'/api/catalog/admin/books/{book_id}/')
        self.assertEqual(response.data['editions'][0]['translators'],['مترجم'])
        self.assertEqual(self.client.post('/api/catalog/admin/editions/', {'book':book_id,'publisher':self.publisher.pk,'price':'150000'},format='json').status_code,400)
        self.assertEqual(self.client.patch(f'/api/publishers/editions/{edition_id}/edit/', {'price':-1},format='json').status_code,400)
        self.client.force_authenticate(User.objects.create_user('09121234567'))
        for url in ['/api/catalog/admin/books/',f'/api/catalog/admin/books/{book_id}/','/api/publishers/','/api/publishers/import-batches/']:
            self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.patch(f'/api/publishers/{self.publisher.pk}/', {'name':'bad'},format='json').status_code,403)

    def test_upload_requires_its_own_currency_and_can_override_profile(self):
        url=f'/api/publishers/import-profiles/{self.profile.pk}/upload/'
        rows=[['عنوان','قیمت','شابک','شرح'],['باغ آبی',250000,'1234','']]
        response=self.client.post(url,{'file':workbook(rows)},format='multipart')
        self.assertEqual(response.status_code,400)
        response=self.client.post(url,{'file':workbook(rows),'price_unit':'toman'},format='multipart')
        self.assertEqual(response.status_code,202,response.data)
        batch=Batch.objects.get(pk=response.data['batch_id'])
        self.assertEqual(batch.profile_snapshot['price_unit'],'toman')
        self.assertEqual(batch.rows.get().data['price'],'250000')

    def test_price_review_bulk_disable_is_scoped_stale_safe_and_staff_only(self):
        self.edition.price=35000;self.edition.save()
        expensive=Edition.objects.create(book=Book.objects.create(title='قیمت عادی'),publisher=self.publisher,price=800000)
        mismatch=Edition.objects.create(book=Book.objects.create(title='نیازمند تطبیق'),publisher=self.publisher,price=2000000,price_review_note='بررسی فایل')
        url='/api/publishers/price-review/'
        result=self.client.get(url).data
        self.assertEqual(result['active_count'],2)
        self.assertEqual({row['id'] for row in result['results']},{self.edition.pk,mismatch.pk})
        self.edition.price=40000;self.edition.save()
        payload={'threshold':result['threshold'],'confirmation_token':result['confirmation_token']}
        self.assertEqual(self.client.post(url,payload,format='json').status_code,409)
        result=self.client.get(url).data
        payload['confirmation_token']=result['confirmation_token']
        response=self.client.post(url,payload,format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['disabled_count'],2)
        expensive.refresh_from_db();self.assertTrue(expensive.is_active)
        self.assertEqual(self.client.get(url).data['count'],0)
        self.assertEqual(self.client.get(url,{'status':'inactive'}).data['count'],2)
        self.assertEqual(self.client.get(url,{'threshold':'bad'}).status_code,400)
        self.client.force_authenticate(User.objects.create_user('09121234567'))
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.post(url,payload,format='json').status_code,403)

    def test_confirmed_price_edit_clears_source_mismatch(self):
        self.edition.price_review_note='نامشخص';self.edition.save()
        url=f'/api/publishers/editions/{self.edition.pk}/edit/'
        self.assertEqual(self.client.patch(url,{'cover_type':'شومیز'},format='json').status_code,200)
        self.edition.refresh_from_db();self.assertTrue(self.edition.price_review_note)
        self.assertEqual(self.client.patch(url,{'price':200000},format='json').status_code,200)
        self.edition.refresh_from_db();self.assertEqual(self.edition.price_review_note,'')

    def test_legacy_reconciliation_is_exact_audited_and_idempotent(self):
        import tempfile
        from pathlib import Path
        from django.core.management import call_command
        self.edition.price=2000000;self.edition.save()
        batch=Batch.objects.create(profile=self.profile,publisher=self.publisher,status='done',file=workbook([['عنوان','قیمت','شابک','شرح'],['باغ آبی',2000000,'1234','']]))
        with tempfile.TemporaryDirectory() as directory:
            call_command('reconcile_rial_prices',batch=[batch.pk],audit=str(Path(directory)/'preview.json'))
            self.edition.refresh_from_db();self.assertEqual(self.edition.price,2000000)
            call_command('reconcile_rial_prices',batch=[batch.pk],audit=str(Path(directory)/'applied.json'),apply=True)
            self.edition.refresh_from_db();self.assertEqual(self.edition.price,200000)
            call_command('reconcile_rial_prices',batch=[batch.pk],audit=str(Path(directory)/'again.json'),apply=True)
            self.edition.refresh_from_db();self.assertEqual(self.edition.price,200000)

    def test_review_threshold_is_saved_for_the_store_and_dashboard(self):
        url='/api/publishers/price-review/'
        response=self.client.patch(url,{'threshold':'150000'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.get(url).data['threshold'],'150000')
        self.assertEqual(self.client.get('/api/admin/dashboard/').data['price_review_threshold'],'150000')
        self.assertEqual(self.client.get('/api/admin/dashboard/').data['counts']['price_review'],1)
        self.assertEqual(self.client.patch(url,{'threshold':0},format='json').status_code,400)
        self.client.force_authenticate(User.objects.create_user('09121234567'))
        self.assertEqual(self.client.patch(url,{'threshold':500},format='json').status_code,403)
