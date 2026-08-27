import pytest

from app.services.phone import InvalidPhoneNumberError, format_for_display, normalize_phone


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("07 12 34 56 78", "+2250712345678"),
        ("0712345678", "+2250712345678"),
        ("+2250712345678", "+2250712345678"),
        ("2250712345678", "+2250712345678"),
        ("00 225 07 12 34 56 78", "+2250712345678"),
        ("05 12 34 56 78", "+2250512345678"),
        ("01 12 34 56 78", "+2250112345678"),
    ],
)
def test_normalize_valid_ivorian_numbers(raw, expected):
    assert normalize_phone(raw) == expected


def test_normalize_invalid_number_raises():
    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone("123")


def test_normalize_empty_raises():
    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone("")


def test_normalize_generic_international_number():
    assert normalize_phone("+33612345678") == "+33612345678"


def test_format_for_display():
    assert format_for_display("+2250712345678") == "07 12 34 56 78"
