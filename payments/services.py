from django.shortcuts import get_object_or_404

from core.services import lock_buyer
from requests_orders.models import Order
from shipping.models import Shipment
from .models import Payment


def lock_payment(payment_id):
    """Consistent lock order for review, uploads, and expiry."""
    reference = get_object_or_404(Payment, pk=payment_id)
    lock_buyer(reference.buyer.pk)
    if reference.order_id:
        Order.objects.select_for_update().get(pk=reference.order_id)
    if reference.shipment_id:
        Shipment.objects.select_for_update().get(pk=reference.shipment_id)
    return Payment.objects.select_for_update().get(pk=payment_id)


def accepts_receipt(payment):
    if payment.order_id and payment.order.status != Order.Status.AWAITING_PAYMENT:
        return False
    if payment.shipment_id and payment.shipment.status != Shipment.Status.AWAITING_PAYMENT:
        return False
    return payment.status in [Payment.Status.PENDING_PROOF, Payment.Status.REJECTED]
