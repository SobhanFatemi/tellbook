"""Private shared testing deployment. Never use displayed OTPs for a public launch."""
import os
from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
STAGING_GATE_SECRET = os.environ.get('STAGING_GATE_SECRET', '')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', '')
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('change-'):
    raise ImproperlyConfigured('Set a random DJANGO_SECRET_KEY of at least 50 characters.')
if len(STAGING_GATE_SECRET) < 32:
    raise ImproperlyConfigured('Set an independent random STAGING_GATE_SECRET of at least 32 characters.')
if not SITE_DOMAIN or any(char in SITE_DOMAIN for char in '/*: ,\n'):
    raise ImproperlyConfigured('SITE_DOMAIN must be a hostname without a scheme, port or wildcard.')
if not os.environ.get('POSTGRES_PASSWORD') or os.environ['POSTGRES_PASSWORD'] == 'bookstore':
    raise ImproperlyConfigured('Set a non-default POSTGRES_PASSWORD.')

ALLOWED_HOSTS = [SITE_DOMAIN, 'localhost', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = [f'https://{SITE_DOMAIN}']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r'^healthz/$']
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# The edge password gate is mandatory; this second check blocks accidental
# direct backend exposure. Caddy overwrites this header after authentication.
STAGING_TEST_MODE = True
OTP_DELIVERY_MODE = 'development'
MIDDLEWARE = ['core.staging_access.StagingAccessMiddleware'] + MIDDLEWARE
SIMPLE_JWT = {**SIMPLE_JWT, 'AUTH_HEADER_NAME': 'HTTP_X_TELLBOOK_AUTHORIZATION'}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                      'LOCATION': os.environ.get('DJANGO_CACHE_URL', 'redis://redis:6379/1')}}
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['CONN_HEALTH_CHECKS'] = True
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
STATIC_ROOT = Path('/app/staticfiles')
MEDIA_ROOT = Path('/app/media')
PRIVATE_MEDIA_ROOT = Path('/app/private_media')
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Private staging must not preload or impose HSTS on unrelated subdomains.
SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']
