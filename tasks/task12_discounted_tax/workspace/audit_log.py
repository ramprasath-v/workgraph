"""Invoice audit event collector."""


class AuditLog:
    def __init__(self):
        self._events: list[tuple[str, str]] = []

    def record(self, event: str, invoice_id: str) -> None:
        self._events.append((event, invoice_id))

    def events(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._events)
