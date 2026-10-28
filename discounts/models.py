from django.db import models

from core.models import TimeStampedModel


class DiscountCode(TimeStampedModel):
    """
    Fixed-amount only, applies to the whole order total -- no percentage
    discounts, no per-book scoping. Simple by design: a flat amount off,
    only usable above a minimum order value.
    """
    code = models.CharField(max_length=50, unique=True)
    value = models.DecimalField(max_digits=12, decimal_places=0)  # flat Toman amount off
    min_order_value = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        help_text="Order total must be at least this much for the code to apply.",
    )
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(default=1)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def compute_discount(self, order_total):
        if order_total < self.min_order_value:
            return 0
        return min(self.value, order_total)  # never discount below zero
