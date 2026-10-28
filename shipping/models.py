from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class ShippingAddress(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    province = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address_line = models.CharField(max_length=500)
    postal_code = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)


class Shipment(TimeStampedModel):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting shipping payment"
        WAITING_BOOKS = "waiting_books", "Paid, awaiting books"
        CANCELLED = "cancelled", "Cancelled"
        PREPARING = "preparing", "Preparing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipments")
    recipient_name = models.CharField(max_length=200)
    recipient_phone = models.CharField(max_length=15)
    province = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address_line = models.CharField(max_length=500)
    postal_code = models.CharField(max_length=10)

    shipping_fee = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)

    delivery_method = models.CharField(max_length=10, choices=[('postal', 'Postal'), ('courier', 'Buyer courier')], default='postal')
    book_count = models.PositiveIntegerField(default=0)

    tracking_code = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def from_address(cls, buyer, address):
        return cls(
            buyer=buyer, recipient_name=address.full_name, recipient_phone=address.phone,
            province=address.province, city=address.city,
            address_line=address.address_line, postal_code=address.postal_code,
        )
