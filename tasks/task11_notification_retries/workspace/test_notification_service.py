import pytest

from delivery_gateway import MemoryDeliveryGateway
from notification_service import NotificationService
from receipt_store import ReceiptStore


def _service():
    gateway = MemoryDeliveryGateway()
    store = ReceiptStore()
    return NotificationService(gateway, store), gateway


def test_first_submission_returns_gateway_receipt():
    service, gateway = _service()

    assert service.submit("req-1", "alex@example.test", "Ready") == "receipt-1"
    assert len(gateway.sent_messages()) == 1


def test_recipient_history_preserves_accepted_message():
    service, _ = _service()
    service.submit("req-1", "alex@example.test", "Ready")

    record = service.history_for("alex@example.test")[0]

    assert (record.request_key, record.message, record.receipt) == (
        "req-1",
        "Ready",
        "receipt-1",
    )


@pytest.mark.parametrize(
    ("request_key", "recipient", "message", "expected"),
    [
        ("", "alex@example.test", "Ready", "request key"),
        ("req-1", "", "Ready", "recipient"),
    ],
)
def test_required_fields_are_validated(request_key, recipient, message, expected):
    service, gateway = _service()

    with pytest.raises(ValueError, match=expected):
        service.submit(request_key, recipient, message)

    assert gateway.sent_messages() == ()


def test_same_request_retry_reuses_original_receipt_without_resending():
    service, gateway = _service()
    first = service.submit("req-1", "alex@example.test", "Ready")

    retried = service.submit("req-1", "alex@example.test", "Ready")

    assert retried == first
    assert len(gateway.sent_messages()) == 1


def test_conflicting_reuse_of_request_key_is_rejected_without_resending():
    service, gateway = _service()
    service.submit("req-1", "alex@example.test", "Ready")

    with pytest.raises(ValueError, match="request key"):
        service.submit("req-1", "alex@example.test", "Changed")

    assert len(gateway.sent_messages()) == 1
