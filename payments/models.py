from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from .storage import PrivateReceiptStorage


class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING_PROOF = "pending_proof", "Waiting for buyer's receipt"
        PENDING_VERIFICATION = "pending_verification", "Waiting for verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    order = models.OneToOneField("requests_orders.Order", on_delete=models.CASCADE, related_name="payment", null=True, blank=True)
    shipment = models.OneToOneField("shipping.Shipment", on_delete=models.PROTECT, related_name="payment", null=True, blank=True)
    base_amount = models.DecimalField(max_digits=12, decimal_places=0)  # this IS the amount to transfer, exactly

    proof_image = models.ImageField(storage=PrivateReceiptStorage(), upload_to="payment_proofs/", blank=True, null=True)
    proof_image_hash = models.CharField(max_length=64, blank=True, db_index=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=25, choices=Status.choices, default=Status.PENDING_PROOF)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=300, blank=True)
    auto_cancel_at = models.DateTimeField(null=True, blank=True)

    @property
    def amount_expected(self):
        return self.base_amount

    @property
    def buyer(self):
        return self.order.buyer if self.order_id else self.shipment.buyer

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(order__isnull=False) | models.Q(shipment__isnull=False), name="payment_has_order_or_shipment")]
