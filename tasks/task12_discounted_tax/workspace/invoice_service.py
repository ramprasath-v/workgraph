"""Invoice calculation application service."""

from decimal import Decimal

from audit_log import AuditLog
from catalog import ProductCatalog
from discount_policy import PercentageDiscount
from invoice_models import Invoice, LineItem
from invoice_repository import InvoiceRepository
from money import round_money
from notification_sink import NotificationSink
from tax_policy import TaxPolicy


class InvoiceService:
    def __init__(
        self,
        catalog: ProductCatalog,
        discount_policy: PercentageDiscount,
        tax_policy: TaxPolicy,
        repository: InvoiceRepository,
        audit_log: AuditLog,
        notifications: NotificationSink,
    ):
        self._catalog = catalog
        self._discount_policy = discount_policy
        self._tax_policy = tax_policy
        self._repository = repository
        self._audit_log = audit_log
        self._notifications = notifications

    def create_invoice(
        self,
        invoice_id: str,
        items: list[LineItem],
        discount_rate: Decimal = Decimal("0"),
    ) -> Invoice:
        if not invoice_id.strip():
            raise ValueError("invoice id is required")
        if not items:
            raise ValueError("at least one line item is required")
        subtotal = Decimal("0")
        for item in items:
            if item.quantity < 1:
                raise ValueError("line item quantity must be positive")
            subtotal += self._catalog.price_for(item.product_code) * item.quantity
        subtotal = round_money(subtotal)
        discount = self._discount_policy.calculate(subtotal, discount_rate)
        tax = self._tax_policy.calculate(subtotal)
        total = round_money(subtotal - discount + tax)
        invoice = Invoice(invoice_id, subtotal, discount, tax, total)
        self._repository.save(invoice)
        self._audit_log.record("invoice_created", invoice_id)
        self._notifications.emit("invoice_created", invoice_id)
        return invoice
