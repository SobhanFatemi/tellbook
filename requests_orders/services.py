from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from discounts.services import DiscountCodeError, apply_discount_code
from payments.models import Payment
from .models import Order

CHECKOUT_RESERVATION_MINUTES = 30
ORDER_PAYMENT_HOURS = 48


def create_order(quote, buyer, raw_code="", stock_item=None, delivery=None, book_count=1):
    """Called inside an atomic purchase with the selected quote/copy locked."""
    try:
        code, amount = apply_discount_code(raw_code, quote.total_price, buyer)
    except DiscountCodeError as exc:
        raise ValidationError({"detail": str(exc)}) from exc
    order = Order.objects.create(
        quote=quote, buyer=buyer, total_price=quote.total_price - amount,
        discount_source=Order.DiscountSource.CODE if code else Order.DiscountSource.NONE,
        discount_code=code, discount_amount=amount,
    )
    window = timedelta(minutes=CHECKOUT_RESERVATION_MINUTES) if stock_item else timedelta(hours=ORDER_PAYMENT_HOURS)
    shipment = None
    if delivery and delivery.get("delivery_mode") in ["ship_when_ready", "courier"]:
        from shipping.services import create_shipping_request
        shipment = create_shipping_request(buyer, delivery.get("address_id"), delivery["expected_shipping_fee"],
            book_count=book_count, method="courier" if delivery["delivery_mode"] == "courier" else "postal",
            address_data=delivery.get("address"), collector_name=delivery.get("collector_name", ""))
    Payment.objects.create(order=order, shipment=shipment,
                           base_amount=order.total_price + (shipment.shipping_fee if shipment else 0),
                           auto_cancel_at=timezone.now() + window)
    if stock_item:
        stock_item.reserve_for_checkout(buyer, order)
    return order


def refund_failed_sourcing(order, payment, reason):
    """Caller holds the buyer/order/payment locks in an atomic transaction."""
    if hasattr(order, "merchandise"):
        from merchandise.services import fail_pending_units
        fail_pending_units(order, reason)
        return
    from refunds.models import Refund
    from shipping.services import cancel_shipment
    if order.status == Order.Status.PAID:
        order.transition_to(Order.Status.SOURCING)
    order.transition_to(Order.Status.FAILED)
    order.failure_reason = reason
    order.save(update_fields=["failure_reason"])
    Refund.build_for_order(order, Refund.Reason.SOURCING_FAILED).save()
    order.transition_to(Order.Status.REFUNDED)
    if payment.shipment_id:
        cancel_shipment(payment.shipment)
