"""Product-price lookup."""

from decimal import Decimal


class ProductCatalog:
    def __init__(self, prices: dict[str, Decimal]):
        self._prices = dict(prices)

    def price_for(self, product_code: str) -> Decimal:
        try:
            return self._prices[product_code]
        except KeyError as exc:
            raise ValueError(f"unknown product: {product_code}") from exc
