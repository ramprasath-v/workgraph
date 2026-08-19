from shipment_service import ShipmentService


class DeliveryReceiver:
    """Translate incoming fulfillment deliveries into shipment requests."""

    def __init__(self, shipment_service=None):
        self.shipment_service = shipment_service or ShipmentService()

    @staticmethod
    def _validate(delivery_token, order_number):
        for name, value in (
            ("delivery_token", delivery_token),
            ("order_number", order_number),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if not value.strip():
                raise ValueError(f"{name} must not be empty")

    def receive(self, delivery_token, order_number):
        self._validate(delivery_token, order_number)
        tracking_number = self.shipment_service.create_shipment(order_number)
        return {
            "status": "created",
            "order_number": order_number,
            "tracking_number": tracking_number,
        }
