from decimal import Decimal

from django.db import connection
from django.utils import timezone

from .models import DiscountCode


class DiscountCodeError(Exception):
    """Raised when a code can't be applied; message is safe to show the buyer."""


def _usage_querysets(code, buyer):
    # Import locally to avoid a hard import cycle at module load time
    # (requests_orders imports discounts, so discounts can't import
    # requests_orders at the top level).
    from requests_orders.models import Order

    used_qs = Order.objects.filter(discount_code=code).exclude(status=Order.Status.CANCELLED)
    per_user_qs = used_qs.filter(buyer=buyer)
    return used_qs, per_user_qs


def validate_discount_code(raw_code, order_total, buyer):
    """
    Look up and validate a code against an order total for a specific buyer.
    Returns the DiscountCode and the computed discount amount (>= 0) on
    success. Raises DiscountCodeError with a buyer-facing message otherwise.

    An order that never got paid (CANCELLED) doesn't count against
    usage_limit/per_user_limit -- the code was never actually redeemed.
    """
    try:
        queryset = DiscountCode.objects.select_for_update() if connection.in_atomic_block else DiscountCode.objects
        code = queryset.get(code__iexact=raw_code)
    except DiscountCode.DoesNotExist:
        raise DiscountCodeError("Discount code not found.")

    if not code.is_active:
        raise DiscountCodeError("This discount code is no longer active.")

    now = timezone.now()
    if code.valid_from and now < code.valid_from:
        raise DiscountCodeError("This discount code is not active yet.")
    if code.valid_until and now > code.valid_until:
        raise DiscountCodeError("This discount code has expired.")

    if order_total < code.min_order_value:
        raise DiscountCodeError(
            f"Order total must be at least {code.min_order_value} to use this code."
        )

    used_qs, per_user_qs = _usage_querysets(code, buyer)
    if code.usage_limit is not None and used_qs.count() >= code.usage_limit:
        raise DiscountCodeError("This discount code has reached its usage limit.")
    if per_user_qs.count() >= code.per_user_limit:
        raise DiscountCodeError("You've already used this discount code.")

    discount_amount = code.compute_discount(order_total)
    return code, discount_amount


def apply_discount_code(raw_code, order_total, buyer):
    """
    Same validation as validate_discount_code, but returns a
    (discount_code_or_None, discount_amount) pair for use at order-creation
    time, where raw_code may be blank/None (meaning: no code requested).
    """
    if not raw_code:
        return None, Decimal("0")
    code, amount = validate_discount_code(raw_code, order_total, buyer)
    return code, amount
