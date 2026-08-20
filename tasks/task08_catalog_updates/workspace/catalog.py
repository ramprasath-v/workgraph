"""Small in-memory product catalog with customer-facing price views."""


class ProductCatalog:
    """Store prices in cents and expose stable public lookup methods."""

    def __init__(self, prices: dict[str, int]):
        if not prices:
            raise ValueError("at least one product is required")
        self._prices = dict(prices)
        for product, cents in self._prices.items():
            self._validate_product(product)
            self._validate_price(cents)
        self._display_prices = {
            product: self._format_price(cents)
            for product, cents in self._prices.items()
        }

    def update_price(self, product: str, cents: int) -> int:
        """Update an existing product and return its new price in cents."""

        self._require_known_product(product)
        self._validate_price(cents)
        self._prices[product] = cents
        return cents

    def price_cents(self, product: str) -> int:
        """Return the authoritative numeric price for a product."""

        self._require_known_product(product)
        return self._prices[product]

    def display_price(self, product: str) -> str:
        """Return the customer-facing formatted price for a product."""

        self._require_known_product(product)
        return self._display_prices[product]

    def catalog_rows(self) -> tuple[tuple[str, str], ...]:
        """Return product names and formatted prices in sorted order."""

        return tuple(sorted(self._display_prices.items()))

    @staticmethod
    def _format_price(cents: int) -> str:
        return f"${cents / 100:.2f}"

    @staticmethod
    def _validate_product(product: str) -> None:
        if not isinstance(product, str) or not product.strip():
            raise ValueError("product must be a non-empty string")

    @staticmethod
    def _validate_price(cents: int) -> None:
        if not isinstance(cents, int) or isinstance(cents, bool) or cents <= 0:
            raise ValueError("price must be a positive integer number of cents")

    def _require_known_product(self, product: str) -> None:
        self._validate_product(product)
        if product not in self._prices:
            raise KeyError(product)
