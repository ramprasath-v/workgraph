"""In-memory invoice persistence."""

from invoice_models import Invoice


class InvoiceRepository:
    def __init__(self):
        self._invoices: dict[str, Invoice] = {}

    def save(self, invoice: Invoice) -> None:
        self._invoices[invoice.invoice_id] = invoice

    def get(self, invoice_id: str) -> Invoice | None:
        return self._invoices.get(invoice_id)
