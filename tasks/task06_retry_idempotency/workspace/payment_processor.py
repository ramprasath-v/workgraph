class PaymentProcessor:
    """Apply validated payment events to an in-memory account total."""

    def __init__(self):
        self.total_charged = 0.0
        self.applied_events = []

    @staticmethod
    def _validate(event_id, amount):
        if not isinstance(event_id, str):
            raise TypeError("event_id must be a string")
        if not event_id.strip():
            raise ValueError("event_id must not be empty")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("amount must be numeric")
        if amount <= 0:
            raise ValueError("amount must be positive")

    def process_event(self, event_id, amount):
        self._validate(event_id, amount)
        numeric_amount = float(amount)
        self.total_charged += numeric_amount
        self.applied_events.append((event_id, numeric_amount))
        return self.total_charged

    @property
    def charge_count(self):
        return len(self.applied_events)
