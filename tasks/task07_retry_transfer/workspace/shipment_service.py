class ShipmentService:
    """Small fulfillment service used by the webhook receiver."""

    def __init__(self):
        self.created_shipments = []

    def create_shipment(self, order_number):
        tracking_number = f"TRK-{len(self.created_shipments) + 1:04d}"
        self.created_shipments.append(
            {"order_number": order_number, "tracking_number": tracking_number}
        )
        return tracking_number
