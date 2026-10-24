import sqlite3

import pytest

from platforms.settlement_amounts import (
    ALL_PERIODS,
    SettlementAmountsError,
    available_periods,
    is_quarter,
    load_amounts,
    load_product_amounts,
    normalize_period,
    period_span,
    period_year,
)
from platforms.settlements import ensure_settlement_schema


def _ensure_schema(database_path):
    with sqlite3.connect(database_path) as connection:
        ensure_settlement_schema(connection)


def _monthly_rows(connection, rows):
    connection.executemany(
        """
        INSERT INTO monthly_book_summary (
            year, month, period, platform_id, platform_key, platform_name,
            product_id, title, isbn, client_name, net_amount, gross_amount,
            source_rows, matched, source_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, '', '', '', ?, ?, 1, 1, ?)
        """,
        rows,
    )


def _transaction_rows(connection, rows):
    connection.executemany(
        """
        INSERT INTO platform_transactions (
            platform_id, platform_key, platform_name, product_id,
            transaction_date, net_amount, gross_amount, source_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _quarterly_rows(connection, rows):
    connection.executemany(
        """
        INSERT INTO quarterly_book_settlements (
            year, quarter, period, period_start, period_end,
            platform_id, platform_key, platform_name, product_id,
            title, isbn, client_name, net_amount, gross_amount, source_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', '', ?, ?, ?)
        """,
        rows,
    )


@pytest.fixture
def database(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _ensure_schema(database_path)

    connection = sqlite3.connect(database_path)
    with connection:
        _monthly_rows(
            connection,
            [
                # Zaimportowany raport platformy.
                (2026, 8, "2026-08", 1, "legimi", "Legimi", 14, 69.99, 73.5,
                 "imported_report"),
                (2026, 7, "2026-07", 1, "legimi", "Legimi", 14, 20.0, 21.0,
                 "imported_report"),
                (2026, 8, "2026-08", 2, "storytel", "Storytel", 14, 5.0, None,
                 "imported_report"),
                (2026, 8, "2026-08", 1, "legimi", "Legimi", 6, 23.33, 24.5,
                 "imported_report"),
            ],
        )
        _transaction_rows(
            connection,
            [
                # Pozycje raportu - juz policzone w podsumowaniu miesiecznym.
                (1, "legimi", "Legimi", 14, "2026-08-04", 23.33, 24.5,
                 "imported_report"),
                (1, "legimi", "Legimi", 14, "2026-08-08", 23.33, 24.5,
                 "imported_report"),
            ],
        )
        _quarterly_rows(
            connection,
            [
                # Platforma rozliczajaca sie kwartalnie podaje nieregularne
                # zakresy dat - jedna ksiazka ma kilka pozycji w kwartale.
                (2025, 4, "2025-Q4", "2025-10-02", "2025-12-28",
                 2, "storytel", "Storytel", 14, 5.5, 6.0, "imported_report"),
                (2025, 4, "2025-Q4", "2025-11-05", "2025-12-20",
                 2, "storytel", "Storytel", 14, 2.5, 3.0, "imported_report"),
                (2025, 3, "2025-Q3", "2025-07-14", "2025-09-08",
                 2, "storytel", "Storytel", 14, 4.0, None, "imported_report"),
            ],
        )
    connection.close()
    return database_path


def test_normalize_period_accepts_year_and_month():
    assert normalize_period(None) == ALL_PERIODS
    assert normalize_period("  ") == ALL_PERIODS
    assert normalize_period("2026") == "2026"
    assert normalize_period("2026-08") == "2026-08"
    assert normalize_period("2026-08-14") == "2026-08"

    with pytest.raises(SettlementAmountsError):
        normalize_period("sierpień")


def test_available_periods_lists_months_and_quarters_from_newest(database):
    # Kwartał stoi w swoim roku, uporządkowany jak jego ostatni miesiąc.
    assert available_periods(database) == [
        "2026-08", "2026-07", "2025-Q4", "2025-Q3",
    ]


def test_available_periods_without_database(tmp_path):
    assert available_periods(tmp_path / "brak.sqlite") == []


def test_month_returns_platform_amounts(database):
    amounts = load_product_amounts(14, "2026-08", database)

    assert [(item.platform_name, item.net, item.gross) for item in amounts] == [
        ("Legimi", 69.99, 73.5),
        ("Storytel", 5.0, None),
    ]
    assert amounts[0].platform_id == 1
    assert amounts[0].periods == ("2026-08",)


def test_imported_transactions_are_not_counted_twice(database):
    legimi = next(
        item
        for item in load_product_amounts(14, "2026-08", database)
        if item.platform_name == "Legimi"
    )

    # 69.99 z podsumowania, bez ponownego doliczania pozycji źródłowych.
    assert legimi.net == 69.99


def test_year_sums_all_months(database):
    legimi = next(
        item
        for item in load_product_amounts(14, "2026", database)
        if item.platform_name == "Legimi"
    )

    assert legimi.net == 89.99
    assert legimi.gross == 94.5
    assert legimi.periods == ("2026-07", "2026-08")


def test_period_without_data_returns_nothing(database):
    assert load_product_amounts(14, "2025-01", database) == []


def test_load_amounts_reads_many_products_at_once(database):
    amounts = load_amounts([6, 14], "2026-08", database)

    assert sorted(amounts) == [6, 14]
    assert [item.net for item in amounts[6]] == [23.33]
    assert [item.platform_name for item in amounts[14]] == ["Legimi", "Storytel"]


def test_load_amounts_without_products(database):
    assert load_amounts([], "2026-08", database) == {}


def test_new_monthly_summary_adds_its_period(database):
    connection = sqlite3.connect(database)
    with connection:
        _monthly_rows(
            connection,
            [(2026, 10, "2026-10", 1, "legimi", "Legimi", 14, 145.5, 152.78,
              "imported_report")],
        )
    connection.close()

    # Miesiąc bierze się z danych, nie z kalendarza.
    assert available_periods(database)[0] == "2026-10"
    assert load_product_amounts(14, "2026-10", database)[0].net == 145.5


def test_transaction_month_without_summary_is_not_listed(database):
    connection = sqlite3.connect(database)
    with connection:
        _transaction_rows(
            connection,
            [(1, "legimi", "Legimi", 14, "2026-12-05", 7.0, 8.0,
              "imported_report")],
        )
    connection.close()

    # Okresy rozliczeń pochodzą wyłącznie z przeliczonych podsumowań.
    assert "2026-12" not in available_periods(database)


def test_deleted_entries_do_not_create_periods(database):
    connection = sqlite3.connect(database)
    with connection:
        _monthly_rows(
            connection,
            [(2025, 5, "2025-05", 1, "legimi", "Legimi", 14, 10.0, 11.0,
              "imported_report")],
        )
        connection.execute(
            "UPDATE monthly_book_summary SET deleted_at = '2026-01-01' "
            "WHERE period = '2025-05'"
        )
    connection.close()

    assert "2025-05" not in available_periods(database)


# ==========================================================
# Nieregularne okresy rozliczeń (raporty kwartalne)
# ==========================================================


def test_normalize_period_accepts_quarters():
    assert normalize_period("2025-Q4") == "2025-Q4"
    assert normalize_period("  2025-q4 ") == "2025-Q4"
    assert is_quarter("2025-Q4") is True
    assert is_quarter("2025-08") is False
    assert period_year("2025-Q4") == 2025
    assert period_year(ALL_PERIODS) is None

    for wrong in ("2025-Q0", "2025-Q5", "2025-QA", "Q4-2025"):
        with pytest.raises(SettlementAmountsError):
            normalize_period(wrong)


def test_quarter_sums_its_irregular_rows(database):
    amounts = load_product_amounts(14, "2025-Q4", database)

    # Dwie pozycje kwartału sumują się w jedną kwotę platformy.
    assert [(item.platform_name, item.net, item.gross) for item in amounts] == [
        ("Storytel", 8.0, 9.0),
    ]
    assert amounts[0].entries == 2
    assert amounts[0].periods == ("2025-Q4",)


def test_quarter_ignores_other_quarters(database):
    amounts = load_product_amounts(14, "2025-Q3", database)

    assert [(item.net, item.gross) for item in amounts] == [(4.0, None)]


def test_month_does_not_pull_quarterly_settlements(database):
    # Kwartał ma własny nieregularny zakres dat, więc nie należy do miesiąca.
    amounts = load_product_amounts(14, "2026-08", database)

    assert [item.platform_name for item in amounts] == ["Legimi", "Storytel"]
    assert next(
        item.net for item in amounts if item.platform_name == "Storytel"
    ) == 5.0


def test_year_sums_months_and_quarters(database):
    storytel = next(
        item
        for item in load_product_amounts(14, "2025", database)
        if item.platform_name == "Storytel"
    )

    # 5.5 + 2.5 (Q4) + 4.0 (Q3); rok 2025 nie ma danych miesięcznych.
    assert storytel.net == 12.0
    assert storytel.periods == ("2025-Q3", "2025-Q4")


def test_all_periods_sum_both_kinds_without_double_counting(database):
    amounts = {
        item.platform_name: item
        for item in load_product_amounts(14, ALL_PERIODS, database)
    }

    assert amounts["Legimi"].net == 89.99
    # 5.0 z miesiąca 2026-08 + 12.0 z kwartałów 2025.
    assert amounts["Storytel"].net == 17.0


def test_period_span_returns_real_dates_of_a_quarter(database):
    span = period_span("2025-Q4", database_path=database)

    assert (span.start, span.end) == ("2025-10-02", "2025-12-28")
    assert str(span) == "2025-10-02 – 2025-12-28"


def test_period_span_narrows_to_selected_products(database):
    connection = sqlite3.connect(database)
    with connection:
        _quarterly_rows(
            connection,
            [(2025, 4, "2025-Q4", "2025-10-01", "2025-12-31",
              2, "storytel", "Storytel", 6, 1.0, 1.1, "imported_report")],
        )
    connection.close()

    assert period_span("2025-Q4", database_path=database).start == "2025-10-01"
    assert period_span(
        "2025-Q4", product_ids=[14], database_path=database
    ).start == "2025-10-02"


def test_period_span_is_empty_for_a_regular_month(database):
    # Miesiąc opisuje sam siebie - nie ma nieregularnego zakresu do pokazania.
    assert period_span("2026-08", database_path=database) is None


def test_period_span_without_quarterly_data(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _ensure_schema(database_path)

    assert period_span("2025-Q4", database_path=database_path) is None


def test_deleted_quarterly_settlements_are_skipped(database):
    connection = sqlite3.connect(database)
    with connection:
        connection.execute(
            "UPDATE quarterly_book_settlements SET deleted_at = '2026-01-01' "
            "WHERE period = '2025-Q3'"
        )
    connection.close()

    assert "2025-Q3" not in available_periods(database)
    assert load_product_amounts(14, "2025-Q3", database) == []

