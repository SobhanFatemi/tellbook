from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class RefundPolicy(TimeStampedModel):
    reason = models.CharField(max_length=20, unique=True)
    deduction_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)


class Refund(TimeStampedModel):
    class Reason(models.TextChoices):
        SOURCING_FAILED = "sourcing_failed", "Sourcing failed"
        EXPIRED = "expired", "Stock item expired"
        CANCELLATION = "cancellation", "Order cancelled"
        RETURN = "return", "Returned after dispatch"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"

    order = models.ForeignKey("requests_orders.Order", on_delete=models.CASCADE, related_name="refunds")
    payment = models.ForeignKey("payments.Payment", on_delete=models.CASCADE, related_name="refunds")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    original_amount = models.DecimalField(max_digits=12, decimal_places=0)
    deduction_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_note = models.TextField(blank=True)
    suggested_amount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)

    @classmethod
    def build_for_order(cls, order, reason):
        from decimal import Decimal

        quote = order.quote
        # What the buyer actually paid (after any discount code), NOT the
        # quote's pre-discount total -- otherwise a discounted order would
        # refund more than was ever paid.
        original = order.payment.base_amount if reason == cls.Reason.SOURCING_FAILED else order.total_price
        if reason == cls.Reason.SOURCING_FAILED:
            deduction = Decimal("0")
        else:
            policy = RefundPolicy.objects.filter(reason=reason).first()
            pct = policy.deduction_percentage if policy else Decimal("0")
            deduction = quote.book_cost * (pct / Decimal("100"))
        return cls(
            order=order, payment=order.payment, reason=reason,
            original_amount=original, deduction_amount=deduction,
            refund_amount=max(original - deduction, Decimal("0")),
        )
