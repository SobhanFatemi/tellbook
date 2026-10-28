"""Public book prices come from publisher editions; paid shelf records are not inventory."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from publisher_catalog.services import get_cheapest_edition


@dataclass
class PriceInfo:
    price: Optional[Decimal]          # what the buyer actually pays, or None if request-only
    original_price: Optional[Decimal]  # pre-discount price, only set if a discount was applied
    source: str                        # "stock_override" | "stock" | "edition" | "none"
    has_discount: bool


def get_display_price(book) -> PriceInfo:
    edition = get_cheapest_edition(book)
    if not edition:
        return PriceInfo(price=None, original_price=None, source="none", has_discount=False)
    base_price = edition.price
    source = "edition"

    final_price = book.apply_discount(base_price)
    has_discount = book.discount_active and final_price != base_price

    return PriceInfo(
        price=final_price,
        original_price=base_price if has_discount else None,
        source=source,
        has_discount=has_discount,
    )
