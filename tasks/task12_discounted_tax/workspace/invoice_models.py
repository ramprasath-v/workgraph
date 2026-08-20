"""Public invoice value objects."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LineItem:
    product_code: str
    quantity: int


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
