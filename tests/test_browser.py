"""Opt-in real frontend/backend browser journey using an isolated test database."""
import os
import re
import subprocess
import signal
import time
import unittest
import urllib.request
from pathlib import Path

from django.core.cache import cache
from django.test import LiveServerTestCase, override_settings
from django.conf import settings

from accounts.models import User
from catalog.models import Book, FeaturedBook
from payments.models import Payment
from requests_orders.models import Order, Quote
from stock.models import StockItem


@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1', 'Set RUN_BROWSER_TESTS=1 to run Chromium integration tests.')
@override_settings(DEBUG=True, OTP_DELIVERY_MODE="development")
class BuyerStaffBrowserTests(LiveServerTestCase):
    def test_phone_login_purchase_receipt_review_and_session_isolation(self):
        from playwright.sync_api import sync_playwright
        from payments.tests import receipt

        cache.clear()
        artifacts = Path(settings.BASE_DIR) / ".artifacts"
        artifacts.mkdir(exist_ok=True)
        staff = User.objects.create_user('09121234568', role='creator')
        book = Book.objects.create(title='کتاب آزمایشی 1984', description='توضیحات کتاب')
        display_title = 'کتاب آزمایشی ۱۹۸۴'
        from publisher_catalog.models import Publisher, Edition
        publisher = Publisher.objects.create(name='ناشر آزمایشی')
        Edition.objects.create(book=book, publisher=publisher, price=100000)
        FeaturedBook.objects.create(book=book, caption='Test book')
        # Deliberately offset order and payment IDs to catch the former admin bug.
        unused_quote = Quote.objects.create(book=book, book_cost=100000, estimated_days=0)
        Order.objects.create(quote=unused_quote, buyer=staff, total_price=100000)
        review_book = Book.objects.create(title='کتاب نیازمند بررسی', needs_review=True)
        source_book = Book.objects.create(title='کتاب موجود برای انتخاب')
        source_quote = Quote.objects.create(book=source_book, book_cost=100000, estimated_days=0)
        source_order = Order.objects.create(quote=source_quote, buyer=staff, total_price=100000, status='paid')
        Payment.objects.create(order=source_order, base_amount=100000, status='verified')
        from PIL import Image, ImageDraw
        from io import BytesIO
        photo_data = []
        for color, label in [('#375a73', 'TEST PHOTO 1'), ('#8c3128', 'TEST PHOTO 2')]:
            photo = Image.new('RGB', (800, 650), color)
            ImageDraw.Draw(photo).text((100, 290), label, fill='white', font_size=56)
            stream = BytesIO()
            photo.save(stream, format='PNG')
            photo_data.append(stream.getvalue())
        env = {**os.environ, 'DEV_API_TARGET': self.live_server_url, 'VITE_API_BASE_URL': '/api'}
        log = open('/tmp/tellbook-vite-browser.log', 'w')
        server = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5179', '--strictPort'], cwd=settings.BASE_DIR, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            for _ in range(100):
                try:
                    
                    if server.poll() is not None:
                        self.fail('Vite exited before startup; see test log')
                    urllib.request.urlopen('http://127.0.0.1:5179', timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            else:
                self.fail('Vite did not start; see /tmp/tellbook-vite-browser.log')
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                failed = []
                page.on('requestfailed', lambda request: failed.append(request.url))

                def login(target, phone):
                    target.goto('http://127.0.0.1:5179/login')
                    target.wait_for_load_state('networkidle')
                    target.get_by_label('شماره موبایل').fill(phone)
                    self.assertEqual(target.locator('input[type=email]').count(), 0)
                    request_button = target.get_by_role('button', name='دریافت کد تایید', exact=True)
                    self.assertEqual(request_button.evaluate('el => getComputedStyle(el).backgroundColor'), 'rgb(140, 49, 40)')
                    request_button.click()
                    target.get_by_label('کد تایید').wait_for()
                    code = target.get_by_label('کد ورود آزمایشی').inner_text()
                    if phone == '09121234567':
                        target.evaluate('window.scrollTo(0, 0)')
                        target.screenshot(path=str(artifacts / 'development-login-desktop.png'), full_page=True)
                    target.get_by_label('کد تایید').fill(code)
                    target.get_by_role('button', name='ورود', exact=True).click()
                    target.wait_for_url(lambda url: '/login' not in url)
                    target.wait_for_load_state('networkidle')

                login(page, '09121234567')
                page.goto(f'http://127.0.0.1:5179/books/{book.pk}')
                page.wait_for_load_state('networkidle')
                page.get_by_role('button', name='افزودن به سبد خرید', exact=True).click()
                page.wait_for_url('**/cart')
                page.get_by_role('radio', name=re.compile('روی قفسه نگه دارید')).check()
                page.get_by_role('button', name='ثبت سفارش و پرداخت', exact=True).click()
                page.wait_for_url('**/cart?order=*')
                page.wait_for_load_state('networkidle')
                page.get_by_text(display_title, exact=False).first.wait_for()
                page.get_by_text('مهلت ارسال رسید', exact=False).wait_for()
                data = receipt().read()
                page.locator('input[type=file]').set_input_files({'name': 'receipt.png', 'mimeType': 'image/png', 'buffer': data})
                page.get_by_role('button', name='ارسال رسید', exact=True).click()
                page.get_by_text('رسیدت رسید!', exact=False).wait_for()
                def buyer_order():
                    token = page.evaluate("localStorage.getItem('tellbook_access')")
                    response = page.request.get('http://127.0.0.1:5179/api/orders/mine/', headers={'Authorization': f'Bearer {token}'})
                    self.assertEqual(response.status, 200)
                    return response.json()[0]
                order = buyer_order()
                self.assertIn(book.title, order['items'][0]['title'])
                self.assertEqual(order['payment']['status'], Payment.Status.PENDING_VERIFICATION)
                self.assertNotEqual(order['payment']['id'], order['id'])

                staff_context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                staff_page = staff_context.new_page()
                staff_page.on('pageerror', lambda error: errors.append(str(error)))
                login(staff_page, staff.phone)
                staff_page.goto('http://127.0.0.1:5179/admin/orders')
                staff_page.wait_for_load_state('networkidle')
                with staff_page.expect_download() as download:
                    staff_page.get_by_role('button', name='دریافت رسید پرداخت').click()
                self.assertIsNone(download.value.failure())
                staff_page.get_by_role('button', name='تایید پرداخت', exact=True).click()
                staff_page.get_by_role('button', name='تایید پرداخت', exact=True).wait_for(state='hidden')
                self.assertEqual(buyer_order()['payment']['status'], Payment.Status.VERIFIED)
                staff_page.get_by_role('button', name='آماده شد', exact=True).click()
                staff_page.get_by_role('button', name='آماده شد', exact=True).wait_for(state='hidden')
                page.goto('http://127.0.0.1:5179/shelf')
                page.wait_for_load_state('networkidle')
                page.get_by_role('heading', name=re.compile(display_title)).wait_for()
                page.evaluate('window.scrollTo(0, 0)')
                page.screenshot(path=str(artifacts / 'shelf-desktop.png'), full_page=True)

                # Opening the form used to crash on the CommonJS date-picker export.
                staff_page.goto('http://127.0.0.1:5179/admin/discounts')
                staff_page.get_by_role('button', name='کد جدید', exact=True).click()
                staff_page.get_by_label('کد', exact=True).fill('BROWSERTEST')
                staff_page.get_by_label('مبلغ تخفیف (تومان)', exact=True).fill('۵۰۰۰')
                for width in [1440, 390]:
                    staff_page.set_viewport_size({'width': width, 'height': 1000})
                    staff_page.get_by_label('شروع اعتبار', exact=True).click()
                    staff_page.locator('.rmdp-day:not(.rmdp-deactive):not(.rmdp-day-hidden)').nth(10).click()
                    self.assertFalse(staff_page.evaluate('document.documentElement.scrollWidth > window.innerWidth'))
                staff_page.get_by_role('button', name='ذخیره', exact=True).click()
                staff_page.get_by_role('button', name='ذخیره', exact=True).wait_for(state='hidden')
                def saved_discount():
                    token = staff_page.evaluate("localStorage.getItem('tellbook_access')")
                    response = staff_page.request.get('http://127.0.0.1:5179/api/discounts/', headers={'Authorization': f'Bearer {token}'})
                    self.assertEqual(response.status, 200)
                    return next(code for code in response.json() if code['code'] == 'BROWSERTEST')
                discount = saved_discount()
                self.assertEqual(int(discount['value']), 5000)
                self.assertIsNotNone(discount['valid_from'])
                staff_page.get_by_role('button', name='ویرایش', exact=True).click()
                staff_page.get_by_label('مبلغ تخفیف (تومان)', exact=True).fill('۶۰۰۰')
                staff_page.get_by_label('پایان اعتبار', exact=True).click()
                staff_page.locator('.rmdp-day:not(.rmdp-deactive):not(.rmdp-day-hidden)').nth(20).click()
                staff_page.get_by_role('button', name='ذخیره', exact=True).click()
                staff_page.get_by_role('button', name='ذخیره', exact=True).wait_for(state='hidden')
                discount = saved_discount()
                self.assertEqual(int(discount['value']), 6000)
                self.assertIsNotNone(discount['valid_until'])
                staff_page.set_viewport_size({'width': 1440, 'height': 1000})

                staff_page.goto('http://127.0.0.1:5179/admin/orders?status=paid')
                staff_page.get_by_role('button', name='کتاب دریافت شد — ثبت آماده‌بودن').click()
                self.assertEqual(staff_page.get_by_label('شماره نسخه در موجودی فروشگاه').count(), 0)
                staff_page.evaluate('window.scrollTo(0, 0)')
                staff_page.screenshot(path=str(artifacts / 'stock-picker-desktop.png'), full_page=True)
                staff_page.set_viewport_size({'width':390,'height':844})
                self.assertFalse(staff_page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                staff_page.evaluate('window.scrollTo(0, 0)')
                staff_page.screenshot(path=str(artifacts / 'stock-picker-mobile.png'), full_page=True)
                with staff_page.expect_request(f'**/api/orders/{source_order.pk}/mark-sourced/') as source_request:
                    staff_page.get_by_role('button', name='تأیید آماده‌بودن کتاب', exact=True).click()
                self.assertEqual(source_request.value.post_data_json, {})
                staff_page.get_by_role('button', name='تأیید آماده‌بودن کتاب', exact=True).wait_for(state='hidden')

                staff_page.goto('http://127.0.0.1:5179/admin/books/review')
                staff_page.get_by_role('button', name='بررسی کتاب', exact=True).click()
                staff_page.get_by_label('نویسنده‌ها (با ویرگول جدا کنید)').fill('نویسنده تأیید شده')
                staff_page.evaluate('window.scrollTo(0, 0)')
                staff_page.screenshot(path=str(artifacts / 'review-editor-mobile.png'), full_page=True)
                staff_page.set_viewport_size({'width':1440,'height':1000})
                staff_page.evaluate('window.scrollTo(0, 0)')
                staff_page.screenshot(path=str(artifacts / 'review-editor-desktop.png'), full_page=True)
                staff_page.get_by_role('button', name='تأیید و نمایش در فروشگاه').click()
                staff_page.get_by_text('صف بازبینی خالی است', exact=True).wait_for()

                staff_page.goto('http://127.0.0.1:5179/admin/posts')
                staff_page.get_by_role('button', name='معرفی تازه', exact=True).click()
                staff_page.get_by_label('عنوان معرفی').fill('معرفی آزمایشی کتاب')
                staff_page.get_by_label('متن معرفی').fill('این نوشته فقط برای آزمایش رابط معرفی کتاب است. ' * 12)
                staff_page.get_by_label('تصاویر معرفی', exact=True).set_input_files([{'name':f'photo-{index}.png','mimeType':'image/png','buffer':data} for index, data in enumerate(photo_data)])
                staff_page.get_by_label('افزودن لینک کتاب (اختیاری)').fill('کتاب آزمایشی')
                staff_page.get_by_role('button', name='افزودن ' + display_title, exact=True).click()
                staff_page.get_by_role('button', name='ذخیره پیش‌نویس', exact=True).click()
                staff_page.get_by_role('button', name='ذخیره پیش‌نویس', exact=True).wait_for(state='hidden')
                self.assertEqual(page.request.get('http://127.0.0.1:5179/api/catalog/posts/').json(), [])
                staff_page.get_by_role('button', name='ویرایش معرفی', exact=True).click()
                for width in [1440,390]:
                    staff_page.set_viewport_size({'width':width,'height':1000})
                    self.assertFalse(staff_page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                    staff_page.evaluate('window.scrollTo(0, 0)')
                    staff_page.screenshot(path=str(artifacts / f'post-editor-{width}.png'), full_page=True)
                staff_page.get_by_role('button', name='انتشار در فروشگاه', exact=True).click()
                staff_page.get_by_role('button', name='انتشار در فروشگاه', exact=True).wait_for(state='hidden')
                posts = page.request.get('http://127.0.0.1:5179/api/catalog/posts/').json()
                self.assertEqual(len(posts), 1)
                self.assertEqual(len(posts[0]['images']), 2)
                self.assertEqual(posts[0]['books'][0]['id'], book.pk)
                page.goto('http://127.0.0.1:5179/')
                page.get_by_role('heading', name='معرفی آزمایشی کتاب', exact=True).wait_for()
                page.get_by_role('button', name='تصویر بعدی', exact=True).click()
                self.assertTrue(page.get_by_role('button', name='تصویر بعدی', exact=True).is_disabled())
                page.get_by_role('button', name='خواندن ادامه معرفی', exact=True).click()
                self.assertTrue(page.get_by_role('button', name='بستن ادامه متن', exact=True).is_visible())
                for width in [1440,390]:
                    page.set_viewport_size({'width':width,'height':1000})
                    page.locator('.book-post').screenshot(path=str(artifacts / f'book-post-{width}.png'))
                page.set_viewport_size({'width':1440,'height':1000})
                staff_page.set_viewport_size({'width':1440,'height':1000})
                # Date direction must remain correct even beside an LTR phone number.
                self.assertTrue(page.evaluate("""async () => {
                    const { formatJalaliShort } = await import('/src/utils/jalali.js');
                    const el=document.createElement('div'); el.dir='ltr'; el.textContent=formatJalaliShort('2026-10-01T12:00:00Z'); document.body.append(el);
                    const text=el.firstChild; const range=document.createRange();
                    range.setStart(text,1);range.setEnd(text,2);const day=range.getBoundingClientRect();
                    range.setStart(text,3);range.setEnd(text,6);const month=range.getBoundingClientRect();
                    el.remove(); return day.left >= month.right;
                }"""))

                staff_page.goto('http://127.0.0.1:5179/admin/settings')
                staff_page.wait_for_load_state('networkidle')
                staff_page.get_by_label('ارسال تا ۶ کتاب، شامل ۶ کتاب (تومان)').fill('50000')
                staff_page.get_by_label('نام صاحب حساب').fill('Test recipient')
                account_input = staff_page.get_by_label('شماره کارت یا حساب برای واریز')
                self.assertEqual(account_input.evaluate('el => el.inputMode'), '')
                account_input.fill('IR۱۲۳')
                self.assertEqual(account_input.input_value(), 'IR۱۲۳')
                with staff_page.expect_response('**/api/admin/store-settings/') as settings_response:
                    staff_page.get_by_role('button', name='ذخیره تنظیمات', exact=True).click()
                self.assertEqual(settings_response.value.json()['transfer_account'], 'IR123')
                staff_page.get_by_role('status').get_by_text('تنظیمات ذخیره شد.').wait_for()
                staff_page.locator('.admin-brand img').wait_for()
                self.assertTrue(staff_page.locator('.admin-brand img').evaluate('el => el.complete && el.naturalWidth > 0'))

                page.goto('http://127.0.0.1:5179/addresses')
                page.wait_for_load_state('networkidle')
                page.get_by_role('button', name='آدرس جدید', exact=True).click()
                for label, value in [('نام گیرنده', 'Test buyer'), ('شماره تماس', '09121234567'), ('استان', 'تهران'), ('شهر', 'تهران'), ('آدرس کامل', 'Test address'), ('کد پستی', '1234567890')]:
                    page.get_by_label(label, exact=True).fill(value)
                page.get_by_role('button', name='ذخیره آدرس', exact=True).click()
                page.get_by_role('button', name='ذخیره آدرس', exact=True).wait_for(state='hidden')
                page.goto('http://127.0.0.1:5179/shelf')
                page.wait_for_load_state('networkidle')
                page.get_by_role('checkbox').check()
                page.get_by_label('آدرس ارسال', exact=True).select_option(index=1)
                page.evaluate('window.scrollTo(0, 0)')
                page.screenshot(path=str(artifacts / 'shelf-selected-desktop.png'), full_page=True)
                page.get_by_role('button', name='ثبت بسته و پرداخت هزینه ارسال', exact=True).click()
                page.get_by_text('بسته', exact=False).first.wait_for()
                page.wait_for_load_state('networkidle')
                page.locator('input[type=file]').set_input_files({'name': 'shipping-receipt.png', 'mimeType': 'image/png', 'buffer': data})
                page.get_by_role('button', name='ارسال رسید', exact=True).click()
                page.get_by_text('رسیدت رسید!', exact=False).wait_for()

                staff_page.goto('http://127.0.0.1:5179/admin/shipments')
                staff_page.wait_for_load_state('networkidle')
                self.assertEqual(staff_page.get_by_role('button', name='ثبت ارسال', exact=True).count(), 0)
                staff_page.goto('http://127.0.0.1:5179/admin/orders')
                staff_page.locator('#shipping-payments').get_by_role('button', name='تایید پرداخت', exact=True).click()
                staff_page.locator('#shipping-payments').get_by_role('button', name='تایید پرداخت', exact=True).wait_for(state='hidden')
                staff_page.goto('http://127.0.0.1:5179/admin/shipments')
                staff_page.get_by_label('کد رهگیری پستی').wait_for()
                tracking_input = staff_page.get_by_label('کد رهگیری پستی')
                self.assertEqual(tracking_input.evaluate('el => el.inputMode'), '')
                tracking_input.fill('TRACK-۱۲۳')
                self.assertEqual(tracking_input.input_value(), 'TRACK-۱۲۳')
                with staff_page.expect_request('**/api/shipping/*/mark-shipped/') as dispatch_request:
                    staff_page.get_by_role('button', name='ثبت ارسال', exact=True).click()
                self.assertEqual(dispatch_request.value.post_data_json['tracking_code'], 'TRACK-123')
                staff_page.get_by_role('button', name='تایید تحویل به مشتری', exact=True).wait_for()
                staff_page.set_viewport_size({'width': 390, 'height': 844})
                staff_page.evaluate('window.scrollTo(0, 0)')
                staff_page.screenshot(path=str(artifacts / 'staff-shipping-mobile.png'), full_page=True)
                self.assertFalse(staff_page.evaluate('document.documentElement.scrollWidth > window.innerWidth'))
                page.goto('http://127.0.0.1:5179/shipments')
                page.wait_for_load_state('networkidle')
                page.get_by_text('TRACK-۱۲۳', exact=True).wait_for()
                page.set_viewport_size({'width': 390, 'height': 844})
                page.evaluate('window.scrollTo(0, 0)')
                page.screenshot(path=str(artifacts / 'buyer-shipping-mobile.png'), full_page=True)
                self.assertFalse(page.evaluate('document.documentElement.scrollWidth > window.innerWidth'))


                # Read-only route sweep at desktop/mobile, including the user's wide-screen case.
                for target, routes in [(page, ['/', '/search', f'/books/{book.pk}', '/request-a-book', '/requests', '/orders', '/shelf', '/shipments', '/addresses', '/profile']), (staff_page, ['/admin', '/admin/requests', '/admin/orders', '/admin/shipments', '/admin/refunds', '/admin/discounts', '/admin/settings', '/admin/books/review', '/admin/posts'])]:
                    for width, height in [(1440, 1000), (390, 844)]:
                        target.set_viewport_size({'width': width, 'height': height})
                        for route in routes:
                            target.goto('http://127.0.0.1:5179' + route)
                            target.wait_for_load_state('networkidle')
                            self.assertTrue(target.locator('main').is_visible(), route)
                            self.assertFalse(target.evaluate('document.documentElement.scrollWidth > window.innerWidth'), f'{route} overflows at {width}')
                            self.assertEqual(target.locator('a button, button a').count(), 0, f'Nested controls on {route}')
                            filename = route.strip('/').replace('/', '-') or 'home'
                            target.evaluate('window.scrollTo(0, 0)')
                            target.screenshot(path=str(artifacts / f'redesign-{filename}-{width}.png'), full_page=True)
                staff_page.set_viewport_size({'width': 3157, 'height': 1969})
                staff_page.goto('http://127.0.0.1:5179/admin/settings')
                staff_page.wait_for_load_state('networkidle')
                box = staff_page.locator('.settings-page').bounding_box()
                workspace = staff_page.locator('.admin-workspace').bounding_box()
                self.assertLess(abs(box['x'] + box['width']/2 - workspace['x'] - workspace['width']/2), 2)
                staff_page.evaluate('window.scrollTo(0, 0)')
                staff_page.screenshot(path=str(artifacts / 'redesign-admin-settings-3157.png'), full_page=True)
                staff_page.get_by_role('link', name='مشاهده فروشگاه', exact=True).click()
                staff_page.wait_for_url('http://127.0.0.1:5179/')
                staff_page.get_by_role('button', name=re.compile('حساب من')).click()
                staff_page.get_by_role('link', name='مدیریت فروشگاه', exact=True).wait_for()

                page.goto('http://127.0.0.1:5179/profile')
                page.get_by_role('button', name='خروج از حساب').click()
                login(page, '09121234569')
                page.goto('http://127.0.0.1:5179/orders')
                page.wait_for_load_state('networkidle')
                page.get_by_text('هنوز سفارشی نداری', exact=True).wait_for()
                self.assertEqual(page.get_by_text(display_title, exact=True).count(), 0)

                mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
                mobile_page = mobile.new_page()
                mobile_page.on('pageerror', lambda error: errors.append(str(error)))
                mobile_page.goto('http://127.0.0.1:5179/login')
                mobile_page.wait_for_load_state('networkidle')
                mobile_page.evaluate('window.scrollTo(0, 0)')
                mobile_page.screenshot(path=str(artifacts / 'login-mobile.png'), full_page=True)
                self.assertFalse(mobile_page.evaluate('document.documentElement.scrollWidth > window.innerWidth'))
                mobile_page.get_by_label('شماره موبایل').fill('09121234567')
                mobile_page.get_by_role('button', name='دریافت کد تایید', exact=True).click()
                mobile_page.get_by_label('کد تایید').wait_for()
                mobile_page.evaluate('window.scrollTo(0, 0)')
                mobile_page.screenshot(path=str(artifacts / 'development-login-mobile.png'), full_page=True)
                self.assertFalse(mobile_page.evaluate('document.documentElement.scrollWidth > window.innerWidth'))
                correct_code = mobile_page.get_by_label('کد ورود آزمایشی').inner_text().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
                mobile_page.get_by_label('کد تایید').fill('000000' if correct_code != '000000' else '111111')
                mobile_page.get_by_role('button', name='ورود', exact=True).click()
                mobile_page.get_by_role('alert').wait_for()
                self.assertTrue(mobile_page.get_by_label('کد تایید').is_visible())
                self.assertEqual(errors, [])
                self.assertEqual(failed, [])
                browser.close()
        finally:
            os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=10)
            log.close()
