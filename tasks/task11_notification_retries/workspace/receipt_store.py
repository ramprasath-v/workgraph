"""Records accepted notification requests and delivery receipts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DispatchRecord:
    request_key: str
    recipient: str
    message: str
    receipt: str


class ReceiptStore:
    def __init__(self):
        self._records: dict[str, DispatchRecord] = {}

    def save(self, record: DispatchRecord) -> None:
        self._records[record.request_key] = record

    def get(self, request_key: str) -> DispatchRecord | None:
        return self._records.get(request_key)

    def for_recipient(self, recipient: str) -> tuple[DispatchRecord, ...]:
        return tuple(
            record
            for record in self._records.values()
            if record.recipient == recipient
        )
