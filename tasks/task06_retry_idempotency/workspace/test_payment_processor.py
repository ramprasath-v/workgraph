import pytest

from payment_processor import PaymentProcessor


def test_first_delivery_applies_charge():
    processor = PaymentProcessor()
    assert processor.process_event("evt-100", 25) == 25.0
    assert processor.total_charged == 25.0
    assert processor.charge_count == 1


def test_duplicate_delivery_does_not_apply_charge_twice():
    processor = PaymentProcessor()
    first_result = processor.process_event("evt-100", 25)
    retry_result = processor.process_event("evt-100", 25)

    assert retry_result == first_result
    assert processor.total_charged == 25.0
    assert processor.charge_count == 1


def test_different_event_ids_are_processed_independently():
    processor = PaymentProcessor()
    processor.process_event("evt-100", 10)
    assert processor.process_event("evt-101", 20) == 30.0
    assert processor.charge_count == 2


def test_retry_after_another_event_still_has_no_duplicate_effect():
    processor = PaymentProcessor()
    processor.process_event("evt-100", 10)
    processor.process_event("evt-101", 20)
    assert processor.process_event("evt-100", 10) == 10.0
    assert processor.total_charged == 30.0
    assert processor.charge_count == 2


def test_invalid_inputs_remain_rejected():
    processor = PaymentProcessor()
    for event_id, amount, error in (
        (None, 10, TypeError),
        ("", 10, ValueError),
        ("   ", 10, ValueError),
        ("evt-100", "10", TypeError),
        ("evt-100", True, TypeError),
        ("evt-100", 0, ValueError),
        ("evt-100", -5, ValueError),
    ):
        with pytest.raises(error):
            processor.process_event(event_id, amount)


def test_public_result_and_event_record_shape_are_preserved():
    processor = PaymentProcessor()
    result = processor.process_event("evt-200", 12.5)

    assert isinstance(result, float)
    assert result == 12.5
    assert processor.applied_events == [("evt-200", 12.5)]
