"""Long-running import preparation/application use a dedicated Celery queue."""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import PublisherImportBatch as Batch

logger = logging.getLogger(__name__)


def record_failure(batch_id, exc):
    from rest_framework.exceptions import ValidationError
    detail = str(exc.detail[0]) if isinstance(exc, ValidationError) and isinstance(exc.detail, list) else str(exc) if isinstance(exc, ValueError) else "پردازش فایل انجام نشد. فایل و تنظیمات را بررسی و دوباره تلاش کنید."
    Batch.objects.filter(pk=batch_id).update(status=Batch.Status.FAILED, error_message=detail[:2000], updated_at=timezone.now())
    logger.exception('Catalog import failed: batch %s', batch_id)


@shared_task(bind=True)
def process_publisher_import(self, batch_id):
    # Claim once: duplicate task delivery never replaces a prepared/applied batch.
    with transaction.atomic():
        batch = Batch.objects.select_for_update().get(pk=batch_id)
        if batch.status != Batch.Status.PENDING:
            return
        batch.status = Batch.Status.PROCESSING
        batch.save(update_fields=["status", "updated_at"])
    try:
        from .staging import prepare_batch
        prepare_batch(batch_id)
    except Exception as exc:
        record_failure(batch_id, exc)


@shared_task(bind=True)
def apply_publisher_import(self, batch_id):
    try:
        from .staging import apply_batch
        apply_batch(batch_id)
    except Exception as exc:
        record_failure(batch_id, exc)
