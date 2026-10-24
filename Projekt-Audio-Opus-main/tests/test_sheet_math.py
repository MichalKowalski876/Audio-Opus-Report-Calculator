import re

import pytest

from core import sheet_math


# ==========================================================
# przeliczenia jednostek
# ==========================================================

@pytest.mark.parametrize(
    "chars, expected_sheets",
    [
        (40_000, 1.0),
        (210_000, 5.25),
        (0, 0.0),
        (-100, 0.0),
        (None, 0.0),
    ],
)
def test_sheets_from_chars(chars, expected_sheets):
    assert sheet_math.sheets_from_chars(chars) == expected_sheets


def test_chars_from_sheets_roundtrips():
    assert sheet_math.chars_from_sheets(5.25) == 210_000


@pytest.mark.parametrize(
    "sheets, expected_minutes",
    [
        (1, 50),
        (5.25, 262.5),
        (0, 0.0),
        (-2, 0.0),
    ],
)
def test_reading_minutes(sheets, expected_minutes):
    assert sheet_math.reading_minutes(sheets) == expected_minutes


# ==========================================================
# calculate_cost  (stawka ZA ARKUSZ, 1 pełny arkusz = pełna stawka)
# ==========================================================

def test_calculate_cost_per_sheet_example():
    # 210 000 zzs = 5,25 arkusza, Masiak 400 + 50 zł/arkusz.
    result = sheet_math.calculate_cost(5.25, 400, 50)

    assert result["minutes"] == 262.5
    assert result["lector_amount"] == pytest.approx(2100.0)
    assert result["surcharge_amount"] == pytest.approx(262.5)
    assert result["client_net"] == pytest.approx(2362.5)
    assert result["vat_amount"] == pytest.approx(543.375)
    assert result["client_gross"] == pytest.approx(2905.875)


def test_calculate_cost_one_sheet_reproduces_rate_card():
    # 1 pełny arkusz = stawki wprost z cennika (Masiak).
    result = sheet_math.calculate_cost(1, 400, 50)

    assert result["client_net"] == pytest.approx(450.0)
    assert result["vat_amount"] == pytest.approx(103.5)
    assert result["client_gross"] == pytest.approx(553.5)


def test_calculate_cost_one_sheet_karolina_matches_rate_card():
    result = sheet_math.calculate_cost(1, 300, 0)

    assert result["client_net"] == pytest.approx(300.0)
    assert result["vat_amount"] == pytest.approx(69.0)
    assert result["client_gross"] == pytest.approx(369.0)


def test_calculate_cost_half_sheet_is_half_rate():
    full = sheet_math.calculate_cost(1, 400, 50)
    half = sheet_math.calculate_cost(0.5, 400, 50)

    assert half["client_net"] == pytest.approx(full["client_net"] / 2)


def test_calculate_cost_handles_empty_input():
    result = sheet_math.calculate_cost(0, 400, 50)

    assert result["client_net"] == 0.0
    assert result["client_gross"] == 0.0


def test_calculate_cost_respects_custom_vat_rate():
    result = sheet_math.calculate_cost(1, 400, 50, vat_rate=8)

    assert result["vat_rate"] == 8
    assert result["vat_amount"] == pytest.approx(36.0)
    assert result["client_gross"] == pytest.approx(486.0)


def test_calculate_cost_defaults_vat_to_module_constant():
    result = sheet_math.calculate_cost(1, 400, 50)

    assert result["vat_rate"] == sheet_math.VAT_RATE


def test_calculate_cost_zero_surcharge():
    result = sheet_math.calculate_cost(1, 300, 0)

    assert result["surcharge_amount"] == 0.0
    assert result["client_net"] == result["lector_amount"]


# ==========================================================
# formatowanie
# ==========================================================

def test_format_sheets():
    assert sheet_math.format_sheets(5.25) == "5,25 ark."
    assert sheet_math.format_sheets(5) == "5 ark."
    assert sheet_math.format_sheets(5.25, suffix="") == "5,25"


def test_format_chars():
    assert sheet_math.format_chars(210000) == "210 000 zzs"


def test_format_duration():
    assert sheet_math.format_duration(262.5) == "4 godz. 23 min"
    assert sheet_math.format_duration(50) == "50 min"
    assert sheet_math.format_duration(120) == "2 godz."
    assert sheet_math.format_duration(0) == "0 min"


def test_format_rate():
    assert sheet_math.format_rate(400) == "400,00 zł/ark."


def test_describe_cost_uses_polish_number_style():
    result = sheet_math.calculate_cost(5.25, 400, 50)
    text = sheet_math.describe_cost(result, "Wojtek Masiak")

    assert "5,25" in text
    assert "2 362,50 zł netto" in text
    assert "2 905,88 zł brutto" in text
    # brak liczb z kropką dziesiętną (np. "5.25")
    assert not re.search(r"\d\.\d", text)


def test_describe_cost_placeholder_when_empty():
    assert sheet_math.describe_cost(None) == (
        "Podaj objętość materiału, aby zobaczyć wyliczenie."
    )
