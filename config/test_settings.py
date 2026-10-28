"""Isolated PostgreSQL tests; never send mail or enqueue external work."""
import os
import tempfile
from .settings import *  # noqa: F403

SECRET_KEY = "tellbook-isolated-test-key-never-use-in-production"

DATABASES["default"]["HOST"] = os.environ.get("TEST_POSTGRES_HOST", "127.0.0.1")
DATABASES["default"]["PORT"] = os.environ.get("TEST_POSTGRES_PORT", "5433")
DATABASES["default"]["TEST"] = {"NAME": "test_tellbook"}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
NOTIFICATION_CHANNEL = "email"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
MEDIA_ROOT = tempfile.mkdtemp(prefix="tellbook-tests-")
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

PRIVATE_MEDIA_ROOT = tempfile.mkdtemp(prefix="tellbook-private-tests-")

OTP_DELIVERY_MODE = "development"
