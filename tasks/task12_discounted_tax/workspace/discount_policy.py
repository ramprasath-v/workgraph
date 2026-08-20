"""Percentage discount calculation and validation."""

from decimal import Decimal

from money import round_money


class PercentageDiscount:
    def calculate(self, subtotal: Decimal, rate: Decimal) -> Decimal:
        if rate < Decimal("0") or rate > Decimal("1"):
            raise ValueError("discount rate must be between zero and one")
        return round_money(subtotal * rate)
