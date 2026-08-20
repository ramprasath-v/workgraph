"""Tax calculation policy."""

from decimal import Decimal

from money import round_money


class TaxPolicy:
    def __init__(self, rate: Decimal):
        if rate < Decimal("0"):
            raise ValueError("tax rate cannot be negative")
        self._rate = rate

    def calculate(self, taxable_amount: Decimal) -> Decimal:
        return round_money(taxable_amount * self._rate)
