from datetime import datetime

import pytest

from core import settlement_numbers
from core.settlement_numbers import SettlementNumberError


@pytest.fixture
def db(tmp_path):
    return tmp_path / "db.sqlite"


def test_first_number_for_a_month(db):
    assert settlement_numbers.next_number("2026-09", database_path=db) == "2026/09/001"


def test_year_period_uses_month_zero(db):
    assert settlement_numbers.next_number("2026", database_path=db) == "2026/00/001"


def test_quarter_period_uses_its_closing_month(db):
    """Okres kwartalny (nieregularne daty) numerujemy ostatnim miesiacem
    kwartalu - Q4 zamyka sie w grudniu."""
    assert settlement_numbers.next_number("2025-Q1", database_path=db) == "2025/03/001"
    assert settlement_numbers.next_number("2025-q4", database_path=db) == "2025/12/001"


def test_empty_period_uses_generation_date(db):
    now = datetime(2026, 3, 14, 10, 0, 0)
    assert (
        settlement_numbers.next_number("", now=now, database_path=db) == "2026/03/001"
    )


def test_counter_runs_through_the_year_and_ignores_month(db):
    first = settlement_numbers.record_settlement(
        "2026/09/001", period="2026-09", client_name="A", database_path=db
    )
    assert first.seq == 1

    # Kolejne rozliczenie, nawet za inny miesiąc, dostaje następny numer w roku.
    assert settlement_numbers.next_number("2026-10", database_path=db) == "2026/10/002"

    settlement_numbers.record_settlement(
        "2026/10/002", period="2026-10", client_name="B", database_path=db
    )
    assert settlement_numbers.next_number("2026-08", database_path=db) == "2026/08/003"


def test_counter_resets_per_year(db):
    settlement_numbers.record_settlement(
        "2026/09/007", period="2026-09", client_name="A", database_path=db
    )
    settlement_numbers.record_settlement(
        "2026/12/008", period="2026-12", client_name="B", database_path=db
    )

    assert settlement_numbers.next_number("2027-01", database_path=db) == "2027/01/001"


def test_next_number_skips_manually_reserved_numbers(db):
    settlement_numbers.record_settlement(
        "2026/09/050", period="2026-09", client_name="A", database_path=db
    )
    assert settlement_numbers.next_number("2026-09", database_path=db) == "2026/09/051"


def test_is_taken_and_get(db):
    assert settlement_numbers.is_taken("2026/09/001", database_path=db) is False

    settlement_numbers.record_settlement(
        "2026/09/001",
        period="2026-09",
        client_id=7,
        client_name="Wydawnictwo X",
        total_client=1234.5,
        pdf_filename="rozliczenie_2026-09-001_X.pdf",
        database_path=db,
    )

    assert settlement_numbers.is_taken("2026/09/001", database_path=db) is True

    record = settlement_numbers.get("2026/09/001", database_path=db)
    assert record.client_id == 7
    assert record.client_name == "Wydawnictwo X"
    assert record.total_client == 1234.5
    assert record.pdf_filename == "rozliczenie_2026-09-001_X.pdf"


def test_recording_the_same_number_updates_instead_of_failing(db):
    settlement_numbers.record_settlement(
        "2026/09/001", period="2026-09", client_name="Stary", database_path=db
    )
    settlement_numbers.record_settlement(
        "2026/09/001",
        period="2026-09",
        client_name="Nowy",
        total_client=99.0,
        database_path=db,
    )

    record = settlement_numbers.get("2026/09/001", database_path=db)
    assert record.client_name == "Nowy"
    assert record.total_client == 99.0
    assert len(settlement_numbers.list_settlements(database_path=db)) == 1


@pytest.mark.parametrize(
    "raw, canonical",
    [
        ("2026/9/1", "2026/09/001"),
        ("2026/09/001", "2026/09/001"),
        (" 2026 / 09 / 1 ", "2026/09/001"),
        ("2026/09/1234", "2026/09/1234"),
    ],
)
def test_normalize_number(raw, canonical):
    assert settlement_numbers.normalize_number(raw) == canonical


@pytest.mark.parametrize("raw", ["", "abc", "2026-09-01", "2026/13/001", "2026/09/0", "26/9/1"])
def test_invalid_numbers_are_rejected(raw):
    with pytest.raises(SettlementNumberError):
        settlement_numbers.parse_number(raw)


def test_number_to_filename_part():
    assert settlement_numbers.number_to_filename_part("2026/09/001") == "2026-09-001"


def test_list_settlements_is_ordered_newest_first(db):
    settlement_numbers.record_settlement("2026/01/001", database_path=db)
    settlement_numbers.record_settlement("2026/06/012", database_path=db)
    settlement_numbers.record_settlement("2027/01/001", database_path=db)

    numbers = [record.number for record in settlement_numbers.list_settlements(database_path=db)]
    assert numbers == ["2027/01/001", "2026/06/012", "2026/01/001"]
