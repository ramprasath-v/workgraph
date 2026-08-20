"""In-memory booking calendar with minute-based boundaries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Booking:
    booking_id: str
    start_minute: int
    end_minute: int
    title: str


class BookingCalendar:
    def __init__(self, opening_minute: int = 9 * 60, closing_minute: int = 17 * 60):
        if opening_minute >= closing_minute:
            raise ValueError("opening time must precede closing time")
        self._opening_minute = opening_minute
        self._closing_minute = closing_minute
        self._bookings: list[Booking] = []

    def add_booking(self, start_minute: int, end_minute: int, title: str) -> str:
        if not title.strip():
            raise ValueError("title is required")
        if start_minute < self._opening_minute or end_minute > self._closing_minute:
            raise ValueError("booking must be within business hours")
        if start_minute >= end_minute:
            raise ValueError("booking start must precede its end")
        if any(
            start_minute <= booking.end_minute
            and end_minute >= booking.start_minute
            for booking in self._bookings
        ):
            raise ValueError("booking overlaps an existing booking")
        booking_id = f"booking-{len(self._bookings) + 1}"
        self._bookings.append(Booking(booking_id, start_minute, end_minute, title))
        self._bookings.sort(key=lambda booking: (booking.start_minute, booking.booking_id))
        return booking_id

    def list_bookings(self) -> tuple[Booking, ...]:
        return tuple(self._bookings)
