"""Isolated browser test for catalog management and staged Excel imports."""
import os
import subprocess
import signal
import time
import unittest
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from django.db import connections

def db(fn):
    def run():
        try:
            return fn()
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run).result()

from django.conf import settings
from django.core.cache import cache
from django.test import LiveServerTestCase, override_settings
from accounts.models import User
from catalog.models import Book
from publisher_catalog.models import Edition, Publisher, PublisherImportBatch
from publisher_catalog.tests import workbook


@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1', 'Browser tests are opt-in.')
@override_settings(DEBUG=True, OTP_DELIVERY_MODE='development')
class CatalogBrowserTests(LiveServerTestCase):
    def test_manage_catalog_and_review_import(self):
        from playwright.sync_api import sync_playwright, expect
        cache.clear()
        User.objects.create_user('09121234568', role='creator')
        artifacts = Path(settings.BASE_DIR) / '.impeccable/review/catalog-management'
        artifacts.mkdir(parents=True, exist_ok=True)
        log = open('/tmp/tellbook-catalog-browser.log', 'w')
        server = subprocess.Popen(['npm','run','dev','--','--host','127.0.0.1','--port','5179','--strictPort'], cwd=settings.BASE_DIR, env={**os.environ,'DEV_API_TARGET':self.live_server_url,'VITE_API_BASE_URL':'/api'},stdout=log,stderr=subprocess.STDOUT, start_new_session=True)
        try:
            for _ in range(100):
                try:
                    
                    if server.poll() is not None:
                        self.fail('Vite exited before startup; see test log')
                    urllib.request.urlopen('http://127.0.0.1:5179',timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            else:
                self.fail('Vite did not start')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,channel=os.environ.get('PLAYWRIGHT_CHANNEL') or None)
                page=browser.new_page(viewport={'width':1440,'height':1000})
                page.set_default_timeout(12000)
                errors=[]; failures=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('response',lambda r:failures.append((r.status,r.url)) if r.status>=400 else None)
                def go(path):
                    page.goto('http://127.0.0.1:5179'+path)
                    page.wait_for_load_state('networkidle')
                def capture(name):
                    page.wait_for_load_state('networkidle')
                    page.evaluate('window.scrollTo(0,0)')
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'),name)
                    page.screenshot(path=str(artifacts / (name+'.png')),full_page=True)
                go('/login')
                page.get_by_label('شماره موبایل').fill('09121234568')
                page.get_by_role('button',name='دریافت کد تایید',exact=True).click()
                page.get_by_label('کد تایید').wait_for()
                page.get_by_label('کد تایید').fill(page.get_by_label('کد ورود آزمایشی').inner_text())
                page.get_by_role('button',name='ورود',exact=True).click()
                page.wait_for_url(lambda url:'/login' not in url)
                go('/admin/publishers')
                page.get_by_role('button',name='ناشر تازه',exact=True).click()
                page.get_by_label('نام ناشر',exact=True).fill('ناشر آزمایشی')
                page.get_by_role('button',name='ذخیره ناشر',exact=True).click()
                page.get_by_role('status').filter(has_text='اطلاعات ناشر ذخیره شد.').wait_for()
                page.get_by_role('button',name='ویرایش ناشر',exact=True).click()
                page.get_by_label('زمان معمول تهیه (روز)',exact=True).fill('۷')
                page.get_by_role('button',name='ذخیره ناشر',exact=True).click()
                page.get_by_role('status').filter(has_text='اطلاعات ناشر ذخیره شد.').wait_for()
                self.assertEqual(db(lambda: Publisher.objects.get().typical_lead_days),7)
                capture('publishers-desktop')
                go('/admin/books')
                page.get_by_role('button',name='کتاب تازه',exact=True).click()
                page.get_by_label('عنوان کتاب',exact=True).fill('باغ آبی')
                page.get_by_label('نویسنده‌ها (با ویرگول جدا کنید)',exact=True).fill('نویسنده آزمایشی')
                page.get_by_label('توضیحات کتاب',exact=True).fill('توضیحی که باید در اکسل بعدی حفظ شود.')
                page.get_by_role('button',name='ثبت کتاب',exact=True).click()
                page.wait_for_url('**/admin/books/*')
                page.get_by_role('button',name='افزودن نسخه ناشر',exact=True).click()
                page.get_by_label('ناشر نسخه',exact=True).select_option(label='ناشر آزمایشی')
                page.get_by_label('مترجم‌ها (با ویرگول جدا کنید)',exact=True).fill('مترجم آزمایشی')
                page.get_by_label('قیمت فروش (تومان)',exact=True).fill('۱۵۰۰۰۰')
                page.get_by_label('شابک',exact=True).fill('۹۷۸۱۲۳۴۵۶۷۸۹۰')
                page.get_by_role('button',name='ذخیره نسخه ناشر',exact=True).click()
                page.get_by_role('status').filter(has_text='نسخه ناشر ذخیره شد.').wait_for()
                book=db(lambda: Book.objects.get(title='باغ آبی'))
                edition=db(lambda: Edition.objects.get(book=book))
                self.assertEqual(edition.price,150000)
                go('/admin/books')
                page.get_by_role('button',name='انتخاب برای صفحه اول',exact=True).click()
                expect(page.get_by_role('button',name='حذف از صفحه اول',exact=True)).to_be_visible()
                capture('homepage-selection-desktop')
                page.set_viewport_size({'width':390,'height':844})
                capture('homepage-selection-mobile')
                go('/')
                expect(page.get_by_text('در فهرست تلبوک',exact=True)).to_be_visible()
                capture('homepage-manual-mobile')
                page.set_viewport_size({'width':1440,'height':1000})
                capture('homepage-manual-desktop')
                go('/admin/books')
                page.get_by_role('button',name='پاک‌کردن انتخاب‌ها و نمایش تصادفی',exact=True).click()
                expect(page.get_by_role('button',name='انتخاب برای صفحه اول',exact=True)).to_be_visible()
                self.assertFalse(db(lambda: Book.objects.get(pk=book.pk).homepage_selected))
                go(f'/admin/books/{book.pk}')
                page.get_by_role('button',name='ویرایش نسخه',exact=True).click()
                page.get_by_label('قیمت فروش (تومان)',exact=True).fill('۱۶۰۰۰۰')
                page.get_by_role('button',name='ذخیره نسخه ناشر',exact=True).click()
                expect(page.get_by_role('button',name='ذخیره نسخه ناشر',exact=True)).to_have_count(0)
                capture('book-desktop')
                page.set_viewport_size({'width':390,'height':844})
                capture('book-mobile')
                page.get_by_role('button',name='باز کردن منوی مدیریت',exact=True).click()
                expect(page.get_by_role('navigation',name='منوی مدیریت')).to_be_visible()
                page.get_by_role('navigation',name='منوی مدیریت').get_by_role('link',name='فایل‌های اکسل',exact=True).click()
                expect(page.get_by_role('navigation',name='منوی مدیریت')).not_to_be_visible()
                page.set_viewport_size({'width':1440,'height':1000})
                page.wait_for_load_state('networkidle')
                page.get_by_label('ناشر فایل',exact=True).select_option(label='ناشر آزمایشی')
                page.get_by_label('نام قالب',exact=True).fill('قالب آزمایشی ریالی')
                source=workbook([['عنوان','قیمت','شابک','شرح'],['باغ آبی',2000000,'9781234567890','متن فایل'],['سفر به کوهستان',350000,'9782222222222','درباره کتاب تازه']])
                page.locator('input[type=file]').set_input_files({'name':'catalog.xlsx','mimeType':source.content_type,'buffer':source.read()})
                page.get_by_role('button',name='خواندن ستون‌ها و نمونه فایل',exact=True).click()
                page.get_by_label('عنوان کتاب',exact=True).select_option(label='عنوان')
                page.get_by_label('قیمت فروش',exact=True).select_option(label='قیمت')
                page.locator('summary').filter(has_text='ستون‌های اختیاری دیگر').click()
                page.get_by_label('شابک',exact=True).select_option(label='شابک')
                page.get_by_label('توضیحات',exact=True).select_option(label='شرح')
                page.get_by_label('واحد قیمت در همین فایل',exact=True).select_option('rial')
                expect(page.get_by_role('radio',name='فقط به‌روزرسانی کتاب‌های داخل فایل',exact=False)).to_be_checked()
                capture('import-desktop')
                page.set_viewport_size({'width':390,'height':844})
                capture('import-mobile')
                page.get_by_role('button',name='ساخت پیش‌نمایش تغییرات',exact=True).click()
                page.wait_for_url('**/admin/imports/*')
                page.get_by_role('heading',name='تأیید نهایی تغییرات',exact=True).wait_for()
                self.assertFalse(db(lambda: PublisherImportBatch.objects.get().complete_catalog))
                db(edition.refresh_from_db); self.assertEqual(edition.price,160000)
                self.assertFalse(db(lambda: Book.objects.filter(title='سفر به کوهستان').exists()))
                capture('review-mobile')
                page.set_viewport_size({'width':1440,'height':1000})
                capture('review-desktop')
                page.get_by_role('checkbox').check()
                page.get_by_role('button',name='تأیید و اعمال تغییرات',exact=True).click()
                page.get_by_role('heading',name='ورود فایل کامل شد',exact=True).wait_for()
                db(edition.refresh_from_db);db(book.refresh_from_db)
                self.assertEqual(edition.price,200000)
                self.assertEqual(book.description,'توضیحی که باید در اکسل بعدی حفظ شود.')
                self.assertTrue(db(lambda: Book.objects.filter(title='سفر به کوهستان').exists()))
                go('/admin/books')
                page.get_by_label('جست‌وجوی عنوان، نویسنده یا شابک',exact=True).fill('سفر')
                expect(page.get_by_role('heading',name='باغ آبی',exact=True)).to_have_count(0)
                expect(page.get_by_role('heading',name='سفر به کوهستان',exact=True)).to_be_visible()
                go(f'/books/{book.pk}')
                page.get_by_text('مشخصات این نسخه',exact=True).click()
                expect(page.get_by_role('heading',name='معرفی کتاب',exact=True)).to_be_visible()
                capture('store-book-desktop')
                page.set_viewport_size({'width':390,'height':844})
                capture('store-book-mobile')
                page.set_viewport_size({'width':1440,'height':1000})
                go('/admin/prices')
                expect(page.get_by_role('heading',name='سفر به کوهستان',exact=True)).to_be_visible()
                page.get_by_label('قیمت کمتر از (تومان)',exact=True).fill('۷۵۰۰۰')
                page.get_by_role('button',name='ذخیره حد بررسی فروشگاه',exact=True).click()
                page.get_by_role('status').filter(has_text='حد بررسی فروشگاه').wait_for()
                page.reload();page.wait_for_load_state('networkidle')
                expect(page.get_by_label('قیمت کمتر از (تومان)',exact=True)).to_have_value('۷۵.۰۰۰')
                page.get_by_role('button',name='غیرفعال‌کردن همه ۱ نسخه قابل سفارش',exact=True).click()
                capture('price-review-desktop')
                page.set_viewport_size({'width':390,'height':844})
                capture('price-review-mobile')
                page.get_by_role('button',name='انصراف',exact=True).click()
                self.assertTrue(db(lambda: Edition.objects.get(book__title='سفر به کوهستان').is_active))
                page.get_by_role('button',name='غیرفعال‌کردن همه ۱ نسخه قابل سفارش',exact=True).click()
                page.get_by_role('button',name='تأیید؛ همه این نسخه‌ها غیرفعال شوند',exact=True).click()
                page.get_by_role('status').filter(has_text='۱ نسخه ناشر غیرفعال شد.').wait_for()
                self.assertFalse(db(lambda: Edition.objects.get(book__title='سفر به کوهستان').is_active))
                page.get_by_label('وضعیت نسخه‌ها',exact=True).select_option('inactive')
                expect(page.get_by_role('heading',name='سفر به کوهستان',exact=True)).to_be_visible()
                self.assertEqual(errors,[])
                self.assertEqual(failures,[])
                browser.close()
        finally:
            os.killpg(server.pid, signal.SIGTERM);server.wait(timeout=10);log.close()
