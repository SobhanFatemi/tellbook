from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from notifications.models import NotificationLog
from .models import OTPCode, User


@override_settings(DEBUG=True, OTP_DELIVERY_MODE='development', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DevelopmentPhoneOTPTests(APITestCase):
    phone = '09121234567'

    def setUp(self):
        cache.clear()

    def request_code(self):
        response = self.client.post('/api/accounts/otp/request/', {'phone': self.phone})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['channel'], 'development')
        self.assertEqual(response['Cache-Control'], 'no-store')
        return response.data['challenge_id'], response.data['development_code']

    def verify(self, challenge, code):
        return self.client.post('/api/accounts/otp/verify/', {'phone': self.phone, 'challenge_id': challenge, 'code': code})

    def test_new_account_created_only_after_code_verification(self):
        challenge, code = self.request_code()
        self.assertFalse(User.objects.exists())
        self.assertNotEqual(OTPCode.objects.get().code, code)
        self.assertFalse(NotificationLog.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        response = self.verify(challenge, code)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(User.objects.get().email)
        self.assertEqual(response.data['user']['role'], 'buyer')
        self.assertIn('access', response.data)
        self.assertEqual(self.verify(challenge, code).status_code, 400)

    def test_existing_creator_with_no_email_can_login_without_changing_role(self):
        User.objects.create_user(self.phone, role='creator')
        challenge, code = self.request_code()
        response = self.verify(challenge, code)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['role'], 'creator')
        self.assertIsNone(User.objects.get().email)

    def test_login_does_not_use_or_change_contact_email(self):
        User.objects.create_user(self.phone, email='saved@example.com')
        response = self.client.post('/api/accounts/otp/request/', {'phone': self.phone, 'email': 'ignored@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.verify(response.data['challenge_id'], response.data['development_code']).status_code, 200)
        self.assertEqual(User.objects.get().email, 'saved@example.com')
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_invalidates_older_challenge(self):
        old_challenge, old_code = self.request_code()
        new_challenge, new_code = self.request_code()
        self.assertEqual(self.verify(old_challenge, old_code).status_code, 400)
        self.assertEqual(self.verify(new_challenge, new_code).status_code, 200)

    def test_five_wrong_guesses_burn_code(self):
        challenge, code = self.request_code()
        wrong_code = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.verify(challenge, wrong_code).status_code, 400)
        self.assertTrue(OTPCode.objects.get().is_used)
        self.assertEqual(self.verify(challenge, code).status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_expired_code_rejected(self):
        challenge, code = self.request_code()
        OTPCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.verify(challenge, code).status_code, 400)

    def test_disabled_account_cannot_redeem_code(self):
        user = User.objects.create_user(self.phone, email='reader@example.com')
        challenge, code = self.request_code()
        user.is_active = False
        user.save()
        self.assertEqual(self.verify(challenge, code).status_code, 403)

    @override_settings(DEBUG=False)
    def test_production_never_exposes_development_code(self):
        response = self.client.post('/api/accounts/otp/request/', {'phone': self.phone})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('development_code', response.data)
        self.assertFalse(OTPCode.objects.exists())

    @override_settings(OTP_DELIVERY_MODE='sms')
    def test_unconfigured_sms_does_not_fall_back_to_email_or_dev_mode(self):
        response = self.client.post('/api/accounts/otp/request/', {'phone': self.phone})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('development_code', response.data)
        self.assertFalse(OTPCode.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_development_challenge_cannot_be_redeemed_after_mode_disabled(self):
        challenge, code = self.request_code()
        with override_settings(DEBUG=False):
            self.assertEqual(self.verify(challenge, code).status_code, 503)
        with override_settings(OTP_DELIVERY_MODE='sms'):
            self.assertEqual(self.verify(challenge, code).status_code, 503)
        self.assertFalse(User.objects.exists())

    def test_request_throttle(self):
        for _ in range(5):
            self.request_code()
        response = self.client.post('/api/accounts/otp/request/', {'phone': self.phone})
        self.assertEqual(response.status_code, 429)

    def test_phone_and_code_validation(self):
        response = self.client.post('/api/accounts/otp/request/', {'phone': 'not-a-phone'})
        self.assertEqual(response.status_code, 400)
        challenge, _ = self.request_code()
        self.assertEqual(self.verify(challenge, 'abc123').status_code, 400)

    def test_current_user_is_private(self):
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 401)
        user = User.objects.create_user(self.phone, email='reader@example.com')
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get('/api/accounts/me/').data['id'], user.id)
