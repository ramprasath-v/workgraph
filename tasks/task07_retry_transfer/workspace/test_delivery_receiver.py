import pytest

from delivery_receiver import DeliveryReceiver
from shipment_service import ShipmentService


def test_first_delivery_creates_one_shipment():
    service = ShipmentService()
    receiver = DeliveryReceiver(service)

    response = receiver.receive("delivery-a", "order-100")

    assert response == {
        "status": "created",
        "order_number": "order-100",
        "tracking_number": "TRK-0001",
    }
    assert len(service.created_shipments) == 1


def test_redelivery_returns_original_response_without_new_shipment():
    service = ShipmentService()
    receiver = DeliveryReceiver(service)

    first = receiver.receive("delivery-a", "order-100")
    repeated = receiver.receive("delivery-a", "order-100")

    assert repeated == first
    assert len(service.created_shipments) == 1


def test_different_delivery_tokens_are_independent():
    service = ShipmentService()
    receiver = DeliveryReceiver(service)

    first = receiver.receive("delivery-a", "order-100")
    second = receiver.receive("delivery-b", "order-100")

    assert first["tracking_number"] == "TRK-0001"
    assert second["tracking_number"] == "TRK-0002"
    assert len(service.created_shipments) == 2


def test_repeated_token_cannot_create_a_changed_second_request():
    service = ShipmentService()
    receiver = DeliveryReceiver(service)

    first = receiver.receive("delivery-a", "order-100")
    repeated = receiver.receive("delivery-a", "order-999")

    assert repeated == first
    assert service.created_shipments == [
        {"order_number": "order-100", "tracking_number": "TRK-0001"}
    ]


def test_invalid_delivery_fields_remain_rejected():
    receiver = DeliveryReceiver()
    for delivery_token, order_number, error in (
        (None, "order-100", TypeError),
        ("", "order-100", ValueError),
        ("   ", "order-100", ValueError),
        ("delivery-a", None, TypeError),
        ("delivery-a", "", ValueError),
        ("delivery-a", "   ", ValueError),
    ):
        with pytest.raises(error):
            receiver.receive(delivery_token, order_number)


def test_response_and_shipment_record_shapes_are_preserved():
    service = ShipmentService()
    receiver = DeliveryReceiver(service)
    response = receiver.receive("delivery-z", "order-700")

    assert set(response) == {"status", "order_number", "tracking_number"}
    assert service.created_shipments == [
        {"order_number": "order-700", "tracking_number": "TRK-0001"}
    ]
