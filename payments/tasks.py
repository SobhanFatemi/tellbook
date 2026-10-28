"""Release unpaid purchases; submitted receipts never expire during review."""
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from requests_orders.models import Order
from stock.models import StockItem
from shipping.services import cancel_shipment
from .models import Payment
from .services import accepts_receipt, lock_payment


@shared_task
def auto_cancel_unpaid_payments():
    candidates = list(Payment.objects.filter(
        status__in=[Payment.Status.PENDING_PROOF, Payment.Status.REJECTED],
        auto_cancel_at__lte=timezone.now(),
    ).values_list('pk', flat=True))
    cancelled = 0
    for payment_id in candidates:
        with transaction.atomic():
            payment = lock_payment(payment_id)
            if not accepts_receipt(payment) or not payment.auto_cancel_at or payment.auto_cancel_at > timezone.now():
                continue
            if payment.order_id:
                from merchandise.services import release_purchase
                release_purchase(payment.order)
                for item in StockItem.objects.select_for_update().filter(source_order_id=payment.order_id, status=StockItem.Status.RESERVED):
                    item.release_expired()
                payment.order.transition_to(Order.Status.CANCELLED)
            if payment.shipment_id:
                cancel_shipment(payment.shipment)
            payment.status = Payment.Status.REJECTED
            payment.rejection_reason = 'Payment window expired.'
            payment.auto_cancel_at = None
            payment.save()
            cancelled += 1
    return {'cancelled': cancelled}
