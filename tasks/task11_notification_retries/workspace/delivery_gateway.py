"""Deterministic outbound notification gateway used by the service."""


class MemoryDeliveryGateway:
    def __init__(self):
        self._sent: list[tuple[str, str, str]] = []

    def send(self, recipient: str, message: str) -> str:
        receipt = f"receipt-{len(self._sent) + 1}"
        self._sent.append((receipt, recipient, message))
        return receipt

    def sent_messages(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(self._sent)
