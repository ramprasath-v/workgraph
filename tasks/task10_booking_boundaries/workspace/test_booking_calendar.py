import pytest

from booking_calendar import BookingCalendar


def test_add_booking_returns_stable_identifier_and_preserves_data():
    calendar = BookingCalendar()

    booking_id = calendar.add_booking(10 * 60, 11 * 60, "Planning")

    assert booking_id == "booking-1"
    assert calendar.list_bookings()[0].title == "Planning"


def test_true_overlap_is_rejected():
    calendar = BookingCalendar()
    calendar.add_booking(10 * 60, 11 * 60, "Planning")

    with pytest.raises(ValueError, match="overlaps"):
        calendar.add_booking(10 * 60 + 30, 11 * 60 + 30, "Review")


def test_booking_before_business_hours_is_rejected():
    calendar = BookingCalendar()

    with pytest.raises(ValueError, match="business hours"):
        calendar.add_booking(8 * 60 + 30, 9 * 60 + 30, "Early")


def test_bookings_are_listed_in_time_order():
    calendar = BookingCalendar()
    calendar.add_booking(13 * 60, 14 * 60, "Afternoon")
    calendar.add_booking(10 * 60, 11 * 60, "Morning")

    assert [booking.title for booking in calendar.list_bookings()] == [
        "Morning",
        "Afternoon",
    ]


def test_booking_can_start_exactly_when_another_ends():
    calendar = BookingCalendar()
    calendar.add_booking(10 * 60, 11 * 60, "Planning")

    second_id = calendar.add_booking(11 * 60, 12 * 60, "Review")

    assert second_id == "booking-2"


def test_booking_can_end_exactly_when_another_starts():
    calendar = BookingCalendar()
    calendar.add_booking(11 * 60, 12 * 60, "Review")

    earlier_id = calendar.add_booking(10 * 60, 11 * 60, "Planning")

    assert earlier_id == "booking-2"
