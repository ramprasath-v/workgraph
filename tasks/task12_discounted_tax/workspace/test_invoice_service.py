from decimal import Decimal

import pytest

from audit_log import AuditLog
from catalog import ProductCatalog
from discount_policy import PercentageDiscount
from invoice_models import LineItem
from invoice_repository import InvoiceRepository
from invoice_service import InvoiceService
from notification_sink import NotificationSink
from tax_policy import TaxPolicy


def _service():
    repository = InvoiceRepository()
    audit_log = AuditLog()
    notifications = NotificationSink()
    service = InvoiceService(
        ProductCatalog({"PEN": Decimal("2.50"), "BOOK": Decimal("12.00")}),
        PercentageDiscount(),
        TaxPolicy(Decimal("0.10")),
        repository,
        audit_log,
        notifications,
    )
    return service, repository, audit_log, notifications


def test_invoice_without_discount_has_expected_amounts():
    service, _, _, _ = _service()

    invoice = service.create_invoice("inv-1", [LineItem("BOOK", 1)])

    assert (invoice.subtotal, invoice.discount, invoice.tax, invoice.total) == (
        Decimal("12.00"),
        Decimal("0.00"),
        Decimal("1.20"),
        Decimal("13.20"),
    )


def test_unknown_product_is_rejected():
    service, _, _, _ = _service()

    with pytest.raises(ValueError, match="unknown product"):
        service.create_invoice("inv-1", [LineItem("MISSING", 1)])


def test_invalid_discount_rate_is_rejected():
    service, _, _, _ = _service()

    with pytest.raises(ValueError, match="discount rate"):
        service.create_invoice(
            "inv-1", [LineItem("BOOK", 1)], Decimal("1.01")
        )


def test_successful_invoice_is_persisted_audited_and_announced():
    service, repository, audit_log, notifications = _service()

    invoice = service.create_invoice("inv-1", [LineItem("PEN", 2)])

    assert repository.get("inv-1") == invoice
    assert audit_log.events() == (("invoice_created", "inv-1"),)
    assert notifications.events() == (("invoice_created", "inv-1"),)


def test_tax_is_calculated_from_discounted_amount():
    service, _, _, _ = _service()

    invoice = service.create_invoice(
        "inv-1", [LineItem("BOOK", 1)], Decimal("0.25")
    )

    assert (invoice.discount, invoice.tax, invoice.total) == (
        Decimal("3.00"),
        Decimal("0.90"),
        Decimal("9.90"),
    )


def test_discounted_tax_uses_combined_line_subtotal_and_rounding():
    service, _, _, _ = _service()

    invoice = service.create_invoice(
        "inv-2",
        [LineItem("BOOK", 1), LineItem("PEN", 3)],
        Decimal("0.10"),
    )

    assert (invoice.subtotal, invoice.discount, invoice.tax, invoice.total) == (
        Decimal("19.50"),
        Decimal("1.95"),
        Decimal("1.76"),
        Decimal("19.31"),
    )
