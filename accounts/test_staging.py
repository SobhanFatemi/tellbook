from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import User


@override_settings(
    DEBUG=False, STAGING_TEST_MODE=True, STAGING_GATE_SECRET='a-test-proxy-secret-that-is-at-least-32-characters',
    OTP_DELIVERY_MODE='development',
    MIDDLEWARE=['core.staging_access.StagingAccessMiddleware'] + settings.MIDDLEWARE,
    SIMPLE_JWT={**settings.SIMPLE_JWT, 'AUTH_HEADER_NAME':'HTTP_X_TELLBOOK_AUTHORIZATION'},
)
class PrivateStagingTests(TestCase):
    def setUp(self):
        # SimpleJWT caches imported settings; mirror the staging process's
        # startup header setting in this shared-process test suite.
        from unittest.mock import patch
        header = patch('rest_framework_simplejwt.authentication.api_settings.AUTH_HEADER_NAME', 'HTTP_X_TELLBOOK_AUTHORIZATION')
        header.start()
        self.addCleanup(header.stop)
        cache.clear()
        self.client=APIClient()
        self.gate={'HTTP_X_TELLBOOK_STAGING_GATE':'a-test-proxy-secret-that-is-at-least-32-characters'}

    def test_direct_backend_cannot_expose_codes_or_data(self):
        self.assertEqual(self.client.get('/api/store/').status_code,403)
        response=self.client.post('/api/accounts/otp/request/',{'phone':'09121234567'},format='json')
        self.assertEqual(response.status_code,403)
        self.assertNotIn('development_code',response.data if hasattr(response,'data') else response.json())
        self.assertEqual(self.client.get('/healthz/').status_code,200)

    def test_private_otp_and_custom_jwt_header_work_without_debug(self):
        response=self.client.post('/api/accounts/otp/request/',{'phone':'09121234567'},format='json',**self.gate)
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response['Cache-Control'],'no-store')
        response=self.client.post('/api/accounts/otp/verify/',{'phone':'09121234567','challenge_id':response.data['challenge_id'],'code':response.data['development_code']},format='json',**self.gate)
        self.assertEqual(response.status_code,200,response.data)
        access=response.data['access']
        # Basic credentials belong to Caddy; JWT remains independent.
        response=self.client.get('/api/accounts/me/',HTTP_AUTHORIZATION='Basic dGVzdGVyOnRlc3Q=',HTTP_X_TELLBOOK_AUTHORIZATION='Bearer '+access,**self.gate)
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['role'],'buyer')
        self.assertEqual(self.client.get('/api/accounts/me/',HTTP_AUTHORIZATION='Bearer '+access,**self.gate).status_code,401)

    @override_settings(STAGING_TEST_MODE=False)
    def test_gate_alone_does_not_enable_public_test_login(self):
        response=self.client.post('/api/accounts/otp/request/',{'phone':'09121234567'},format='json',**self.gate)
        self.assertEqual(response.status_code,503)

    def test_explicit_staff_bootstrap_is_staging_only(self):
        call_command('staging_staff','09121234567')
        self.assertEqual(User.objects.get(phone='09121234567').role,'creator')
        with override_settings(STAGING_TEST_MODE=False), self.assertRaises(CommandError):
            call_command('staging_staff','09121234568')
        self.assertFalse(User.objects.filter(phone='09121234568').exists())
