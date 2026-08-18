import pytest

from calculator import divide


def test_divides_positive_numbers():
    assert divide(8, 2) == 4


def test_divides_fractional_result():
    assert divide(3, 2) == 1.5


def test_zero_division_is_preserved():
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
