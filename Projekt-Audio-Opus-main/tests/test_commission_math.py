import pytest

from core import commission_math


# ==========================================================
# parse_number
# ==========================================================

@pytest.mark.parametrize(
    "text, expected",
    [
        ("5000", 5000.0),
        ("5000,50", 5000.5),
        ("5000.50", 5000.5),
        ("  10 ", 10.0),
        ("", None),
        ("   ", None),
        (None, None),
        ("abc", None),
    ],
)
def test_parse_number(text, expected):
    assert commission_math.parse_number(text) == expected


# ==========================================================
# format_money / format_percent
# ==========================================================

def test_format_money_uses_polish_style():
    assert commission_math.format_money(10000) == "10 000,00 zł"
    assert commission_math.format_money(0) == "0,00 zł"
    assert commission_math.format_money(1600.5) == "1 600,50 zł"


def test_format_money_handles_invalid_value():
    assert commission_math.format_money(None) == "0,00 zł"
    assert commission_math.format_money("abc") == "0,00 zł"


def test_format_percent_strips_trailing_zeros():
    assert commission_math.format_percent(20) == "20%"
    assert commission_math.format_percent(12.5) == "12,5%"
    assert commission_math.format_percent(0) == "0%"


def test_format_percent_handles_invalid_value():
    assert commission_math.format_percent(None) == "0%"


# ==========================================================
# split_fixed (prowizja "od razu")
# ==========================================================
#
# cut_percent to prowizja platformy (AO) - ten sam model co "Procent" przy
# produkcie i report_generator.compute_settlement_rows dla instant.
# ==========================================================

def test_split_fixed_typical_case():
    result = commission_math.split_fixed(10000, 30)

    assert result["platform_amount"] == pytest.approx(3000)
    assert result["client_amount"] == pytest.approx(7000)
    assert result["excess"] == 0


def test_split_fixed_zero_percent_all_to_client():
    result = commission_math.split_fixed(10000, 0)

    assert result["platform_amount"] == 0
    assert result["client_amount"] == 10000


def test_split_fixed_hundred_percent_all_to_platform():
    result = commission_math.split_fixed(10000, 100)

    assert result["platform_amount"] == 10000
    assert result["client_amount"] == 0


@pytest.mark.parametrize("percent", [-1, 100.01, 200])
def test_split_fixed_rejects_out_of_range_percent(percent):
    assert commission_math.split_fixed(10000, percent) is None


def test_split_fixed_matches_the_instant_settlement_model():
    """Kalkulator "Od razu" musi liczyć tak samo jak produkt instant w
    report_generator.compute_settlement_rows - ten sam procent, ten sam
    wynik dla platformy i klienta."""
    from core import report_generator

    product = {"title": "X", "cut": 30, "settlement type": "instant", "threshold": 0}
    item = {
        "product": product,
        "platform": {"name": "L"},
        "revenue": 10000.0,
    }
    _, rows = report_generator.compute_settlement_rows(
        {"id": 1, "name": "K", "cut": 0}, [item]
    )

    calculator_result = commission_math.split_fixed(10000, 30)

    assert calculator_result["platform_amount"] == pytest.approx(rows[0]["fee"])
    assert calculator_result["client_amount"] == pytest.approx(rows[0]["for_client"])


# ==========================================================
# split_threshold (prowizja "po progu")
# ==========================================================

def test_split_threshold_typical_case():
    # Przykład z dokumentacji: próg 5000, platforma 20%, sprzedaż 7000.
    result = commission_math.split_threshold(7000, 5000, 20)

    assert result["excess"] == pytest.approx(2000)
    assert result["platform_amount"] == pytest.approx(400)
    assert result["client_amount"] == pytest.approx(1600)


def test_split_threshold_amount_below_threshold_gives_nothing():
    result = commission_math.split_threshold(3000, 5000, 20)

    assert result == {
        "client_amount": 0.0,
        "platform_amount": 0.0,
        "excess": 0.0,
    }


def test_split_threshold_amount_equal_to_threshold_gives_nothing():
    result = commission_math.split_threshold(5000, 5000, 20)

    assert result["excess"] == 0.0


def test_split_threshold_zero_threshold_behaves_like_full_split():
    result = commission_math.split_threshold(1000, 0, 25)

    assert result["excess"] == pytest.approx(1000)
    assert result["platform_amount"] == pytest.approx(250)
    assert result["client_amount"] == pytest.approx(750)


# ==========================================================
# describe_fixed / describe_threshold
# ==========================================================

def test_describe_fixed_mentions_amounts_and_percent():
    text = commission_math.describe_fixed(10000, 30, 3000, 7000)

    assert "10 000,00 zł" in text
    assert "30%" in text
    assert "3 000,00 zł" in text
    assert "7 000,00 zł" in text


def test_describe_threshold_below_threshold_mentions_platform_keeps_all():
    text = commission_math.describe_threshold(3000, 5000, 20, 0, 0, 0)

    assert "nie przekracza progu" in text
    assert "3 000,00 zł" in text


def test_describe_threshold_above_threshold_mentions_breakdown():
    text = commission_math.describe_threshold(7000, 5000, 20, 1600, 400, 2000)

    assert "2 000,00 zł nadwyżki" in text
    assert "20%" in text
    assert "400,00 zł" in text
    assert "1 600,00 zł" in text
    assert "-" not in text


def test_describe_threshold_uses_split_threshold_output_without_negative_amounts():
    """Regresja: describe_threshold kiedyś odejmowało próg od platform_amount,
    co przy typowych liczbach dawało ujemną kwotę w opisie."""
    result = commission_math.split_threshold(7000, 5000, 20)

    text = commission_math.describe_threshold(
        7000, 5000, 20,
        result["client_amount"], result["platform_amount"], result["excess"],
    )

    assert "400,00 zł" in text
    assert "-" not in text


# ==========================================================
# split_up_to_threshold (prowizja "do progu")
# ==========================================================

def test_split_up_to_threshold_typical_case():
    # Ten sam przykład co dla "po progu", ale odwrotna zasada: próg 5000,
    # platforma 20%, sprzedaż 7000 - prowizja liczona od kwoty do progu,
    # nadwyżka (2000) w całości dla klienta.
    result = commission_math.split_up_to_threshold(7000, 5000, 20)

    assert result["excess"] == pytest.approx(2000)
    assert result["platform_amount"] == pytest.approx(1000)
    assert result["client_amount"] == pytest.approx(6000)


def test_split_up_to_threshold_amount_below_threshold_splits_whole_amount():
    result = commission_math.split_up_to_threshold(3000, 5000, 20)

    assert result["excess"] == 0.0
    assert result["platform_amount"] == pytest.approx(600)
    assert result["client_amount"] == pytest.approx(2400)


def test_split_up_to_threshold_amount_equal_to_threshold_has_no_excess():
    result = commission_math.split_up_to_threshold(5000, 5000, 20)

    assert result["excess"] == 0.0
    assert result["platform_amount"] == pytest.approx(1000)
    assert result["client_amount"] == pytest.approx(4000)


@pytest.mark.parametrize("percent", [-1, 100.01, 200])
def test_split_up_to_threshold_rejects_out_of_range_percent(percent):
    assert commission_math.split_up_to_threshold(10000, 5000, percent) is None


# ==========================================================
# describe_up_to_threshold
# ==========================================================

def test_describe_up_to_threshold_below_threshold_splits_whole_amount():
    text = commission_math.describe_up_to_threshold(3000, 5000, 20, 2400, 600, 0)

    assert "nie przekracza progu" in text
    assert "600,00 zł" in text
    assert "2 400,00 zł" in text


def test_describe_up_to_threshold_above_threshold_mentions_excess_for_client():
    text = commission_math.describe_up_to_threshold(7000, 5000, 20, 6000, 1000, 2000)

    assert "1 000,00 zł" in text
    assert "2 000,00 zł" in text
    assert "6 000,00 zł" in text
    assert "20%" in text


# ==========================================================
# split_combined (prowizja "do i po progu")
# ==========================================================

def test_split_combined_typical_case():
    # Próg 5000, do progu 10%, po progu 20%, sprzedaż 7000.
    result = commission_math.split_combined(7000, 5000, 10, 20)

    assert result["excess"] == pytest.approx(2000)
    assert result["platform_below"] == pytest.approx(500)
    assert result["platform_above"] == pytest.approx(400)
    assert result["platform_amount"] == pytest.approx(900)
    assert result["client_amount"] == pytest.approx(6100)


def test_split_combined_amount_below_threshold_uses_only_below_percent():
    result = commission_math.split_combined(3000, 5000, 10, 20)

    assert result["excess"] == 0.0
    assert result["platform_above"] == 0.0
    assert result["platform_amount"] == pytest.approx(300)
    assert result["client_amount"] == pytest.approx(2700)


def test_split_combined_zero_above_percent_behaves_like_up_to_threshold():
    combined = commission_math.split_combined(7000, 5000, 20, 0)
    up_to = commission_math.split_up_to_threshold(7000, 5000, 20)

    assert combined["platform_amount"] == pytest.approx(up_to["platform_amount"])
    assert combined["client_amount"] == pytest.approx(up_to["client_amount"])


@pytest.mark.parametrize("below_percent,above_percent", [(-1, 10), (10, -1), (101, 10), (10, 200)])
def test_split_combined_rejects_out_of_range_percent(below_percent, above_percent):
    assert commission_math.split_combined(10000, 5000, below_percent, above_percent) is None


# ==========================================================
# describe_combined
# ==========================================================

def test_describe_combined_below_threshold_uses_only_below_percent():
    text = commission_math.describe_combined(3000, 5000, 10, 20, 2700, 300, 0, 300, 0)

    assert "10%" in text
    assert "300,00 zł" in text
    assert "2 700,00 zł" in text
    assert "20%" not in text


def test_describe_combined_above_threshold_mentions_both_parts():
    text = commission_math.describe_combined(7000, 5000, 10, 20, 6100, 900, 2000, 500, 400)

    assert "10%" in text
    assert "20%" in text
    assert "500,00 zł" in text
    assert "400,00 zł" in text
    assert "900,00 zł" in text
    assert "6 100,00 zł" in text
