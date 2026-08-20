"""Application service for durable notification dispatch."""

from delivery_gateway import MemoryDeliveryGateway
from receipt_store import DispatchRecord, ReceiptStore


class NotificationService:
    def __init__(self, gateway: MemoryDeliveryGateway, store: ReceiptStore):
        self._gateway = gateway
        self._store = store

    def submit(self, request_key: str, recipient: str, message: str) -> str:
        if not request_key.strip():
            raise ValueError("request key is required")
        if not recipient.strip():
            raise ValueError("recipient is required")
        if not message.strip():
            raise ValueError("message is required")
        receipt = self._gateway.send(recipient, message)
        self._store.save(
            DispatchRecord(request_key, recipient, message, receipt)
        )
        return receipt

    def history_for(self, recipient: str) -> tuple[DispatchRecord, ...]:
        return self._store.for_recipient(recipient)
