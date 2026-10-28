from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from catalog.models import Book
from core.models import TimeStampedModel
from publisher_catalog.models import Edition


class BookRequest(TimeStampedModel):
    class Source(models.TextChoices):
        DB_SEARCH = "db_search", "Found in database"
        BUYER_ENTERED = "buyer_entered", "Buyer entered (unmatched)"
        STAFF_ENTERED = "staff_entered", "Staff entered"
        FEATURED = "featured", "From featured book"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SOURCING = "sourcing", "Sourcing"
        FAILED = "failed", "Failed"
        READY = "ready", "Ready"

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="requests")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requests_created_for_others",
    )

    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True, related_name="requests")
    title = models.CharField(max_length=500, blank=True)
    author = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    reference_image = models.ImageField(upload_to="request_references/", blank=True, null=True)

    source = models.CharField(max_length=20, choices=Source.choices, default=Source.BUYER_ENTERED)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    estimated_days_remaining = models.PositiveSmallIntegerField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    def clean(self):
        if self.status == self.Status.FAILED and not self.failure_reason:
            raise ValidationError("failure_reason is required when status is FAILED.")


class Quote(TimeStampedModel):
    request = models.OneToOneField(
        BookRequest, on_delete=models.CASCADE, related_name="quote", null=True, blank=True
    )
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True)
    book_cost = models.DecimalField(max_digits=12, decimal_places=0)
    service_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    estimated_days = models.PositiveSmallIntegerField()

    is_auto_quoted = models.BooleanField(default=False)
    source_listing = models.ForeignKey(
        Edition, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes"
    )
    quoted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    @property
    def total_price(self):
        return self.book_cost + self.service_fee + self.shipping_fee


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        PAID = "paid", "Paid"
        SOURCING = "sourcing", "Sourcing"
        FAILED = "failed", "Failed"
        STOCK_READY = "stock_ready", "Stock ready"
        SHIPPED = "shipped", "Shipped"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"  # Closed order; verified-payment refunds are tracked separately.

    VALID_TRANSITIONS = {
        Status.AWAITING_PAYMENT: {Status.PAID, Status.CANCELLED},
        Status.PAID: {Status.SOURCING, Status.STOCK_READY},
        Status.SOURCING: {Status.FAILED, Status.STOCK_READY},
        Status.FAILED: {Status.REFUNDED},
        Status.STOCK_READY: {Status.SHIPPED, Status.REFUNDED},
        Status.SHIPPED: set(),
        Status.REFUNDED: set(),
        Status.CANCELLED: set(),
    }

    class DiscountSource(models.TextChoices):
        NONE = "none", "None"
        CODE = "code", "Discount code"
        POINTS = "points", "Points"

    quote = models.OneToOneField(Quote, on_delete=models.PROTECT, related_name="order")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT)

    failure_reason = models.TextField(blank=True)

    discount_source = models.CharField(max_length=10, choices=DiscountSource.choices, default=DiscountSource.NONE)
    discount_code = models.ForeignKey(
        "discounts.DiscountCode", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=0)

    def transition_to(self, new_status):
        if new_status not in self.VALID_TRANSITIONS.get(self.status, set()):
            raise ValidationError(f"Cannot move Order from {self.status} to {new_status}.")
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        from notifications.services import NotificationService
        transaction.on_commit(lambda: NotificationService.notify_creator_order_update(self))


class OrderCancellation(TimeStampedModel):
    """Immutable staff decision; actual transfers remain in the refund ledger."""
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='cancellation')
    reason = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    return_confirmed_at = models.DateTimeField(null=True, blank=True)
    previous_status = models.CharField(max_length=20)
