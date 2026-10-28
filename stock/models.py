from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import Book
from core.models import TimeStampedModel

HOLD_PERIOD_DAYS = 30


class StockItem(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Awaiting payment"
        ON_HOLD = "on_hold", "On hold"
        READY_TO_SHIP = "ready_to_ship", "Ready to ship"
        SHIPPED = "shipped", "Shipped"

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="stock_items", null=True, blank=True)
    merchandise_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="claimed_stock"
    )
    source_order = models.ForeignKey(
        "requests_orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_items"
    )

    acquired_at = models.DateTimeField(default=timezone.now)
    reserved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    unit_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    discounted_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    discount_reason = models.CharField(max_length=200, blank=True)

    shipment = models.ForeignKey(
        "shipping.Shipment", on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_items_set"
    )

    @property
    def title(self):
        return self.merchandise_data.get("title", "") or (self.book.title if self.book_id else "")

    @property
    def effective_price(self):
        if self.merchandise_data:
            return self.unit_price
        return self.discounted_price if self.discounted_price is not None else self.book.apply_discount(self.unit_price)

    def reserve_for_checkout(self, buyer, order):
        self.buyer = buyer
        self.source_order = order
        self.reserved_at = timezone.now()
        self.expires_at = None  # The storage clock starts only after payment.
        self.status = self.Status.RESERVED
        self.save()

    def claim_for_buyer(self, buyer, order=None):
        self.buyer = buyer
        self.source_order = order
        self.reserved_at = timezone.now()
        self.expires_at = self.reserved_at + timedelta(days=HOLD_PERIOD_DAYS)
        self.status = self.Status.READY_TO_SHIP
        if order and order.payment.shipment_id:
            self.shipment_id = order.payment.shipment_id
        self.save()
        StockEvent.objects.create(stock_item=self, event_type=StockEvent.EventType.SOLD)

    def put_on_hold(self):
        self.status = self.Status.ON_HOLD
        self.save(update_fields=["status", "updated_at"])

    def release_expired(self):
        self.buyer = None
        self.source_order = None
        self.shipment = None
        self.reserved_at = None
        self.expires_at = None
        self.status = self.Status.AVAILABLE
        self.save()
        StockEvent.objects.create(stock_item=self, event_type=StockEvent.EventType.EXPIRED)

    class Meta:
        indexes = [models.Index(fields=["status"]), models.Index(fields=["expires_at"])]


class StockEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        EXPIRED = "expired", "Expired"
        REFUNDED = "refunded", "Refunded"
        SOLD = "sold", "Sold"
        SHIPPED = "shipped", "Shipped"

    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    note = models.CharField(max_length=300, blank=True)
