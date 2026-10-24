import sqlite3

import pytest
from openpyxl import Workbook, load_workbook

from platforms.column_mappings import save_column_mapping
from platforms.report_calculator import (
    ReportCalculationError,
    available_report_years,
    calculate_platform_reports,
    delete_imported_report_data,
    quarter_of_range,
    relink_unmatched_rows,
)
from platforms.xlsx_reports import (
    MONTHLY_REPORT,
    QUARTERLY_REPORT,
    TRANSACTION_REPORT,
    report_platform_key,
)


def _save_mapping(report_path, database_path, report_type, columns):
    workbook = load_workbook(report_path, data_only=True)
    try:
        sheet = workbook.active
        headers = [
            sheet.cell(row=1, column=column).value
            for column in range(1, (sheet.max_column or 1) + 1)
        ]
    finally:
        workbook.close()
    save_column_mapping(
        report_platform_key(report_path),
        headers,
        report_type,
        columns,
        database_path=database_path,
    )


def _configure_existing_report_mappings(year_directory, database_path):
    legimi_path = year_directory / "Legimi.xlsx"
    if legimi_path.is_file():
        _save_mapping(
            legimi_path,
            database_path,
            TRANSACTION_REPORT,
            {
                "title": 0,
                "isbn": 1,
                "transaction_date": 2,
                "net": 3,
                "gross": 4,
            },
        )
    storytel_path = year_directory / "Storytel.xlsx"
    if storytel_path.is_file():
        _save_mapping(
            storytel_path,
            database_path,
            MONTHLY_REPORT,
            {"title": 0, "isbn": 1, "net": 2, "vat": 3, "period": 4},
        )


def _write_legimi_report(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Tytul",
            "ISBN",
            "Data sprzedazy",
            "Wynagrodzenie netto",
            "Wynagrodzenie brutto",
        ]
    )
    sheet.append(["Pierwsza ksiazka", "978-1", "2026-01-05", 10.0, 12.3])
    sheet.append(["Pierwsza ksiazka", "978-1", "2026-01-20", 5.0, 6.15])
    sheet.append(["Pierwsza ksiazka", "978-1", "2026-02-01", 7.0, 8.61])
    workbook.save(path)


def _write_storytel_report(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Audio Book Title",
            "ISBN",
            "Remuneration (PLN)",
            "VAT (%)",
            "Consumption dates",
        ]
    )
    sheet.append(
        [
            "Ksiazka spoza bazy",
            "978-2",
            20.0,
            5.0,
            "2026-02-10 to 2026-02-10",
        ]
    )
    workbook.save(path)


def _write_quarterly_storytel_report(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "A-books"
    sheet.append(
        [
            "Audio Book Title",
            "ISBN",
            "Quantity/no. of units",
            "Remuneration (PLN)",
            "VAT (%)",
            "Consumption dates",
        ]
    )
    sheet.append(
        [
            "Pierwsza ksiazka",
            "978-1",
            17,
            125.50,
            5.0,
            "2025-10-01 to 2025-12-31",
        ]
    )
    workbook.save(path)


def test_calculates_monthly_book_and_platform_summaries(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    _write_legimi_report(year_directory / "Legimi.xlsx")
    _write_storytel_report(year_directory / "Storytel.xlsx")
    database_path = tmp_path / "Databases" / "db.sqlite"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            'CREATE TABLE products (id INTEGER PRIMARY KEY, data TEXT NOT NULL)'
        )
        connection.execute(
            'INSERT INTO products (id, data) VALUES (?, ?)',
            (99, '{"title": "Nie usuwaj"}'),
        )
    _configure_existing_report_mappings(year_directory, database_path)

    result = calculate_platform_reports(
        2026,
        reports_root=reports_root,
        database_path=database_path,
        products=[
            {
                "id": 1,
                "title": "Pierwsza ksiazka",
                "isbn": "9781",
                "publisher": "Klient A",
            }
        ],
        platforms=[
            {"id": 1, "name": "Legimi", "integration": "legimi"},
            {"id": 2, "name": "Storytel", "integration": "storytel"},
        ],
    )

    assert result.database_path == database_path
    assert result.report_files == 2
    assert result.source_rows == 4
    assert result.included_rows == 4
    assert result.book_summary_rows == 3
    assert result.platform_summary_rows == 3
    assert result.unmatched_books == 1
    assert [status.source_file for status in result.file_statuses] == [
        "Legimi.xlsx",
        "Storytel.xlsx",
    ]
    assert all(status.calculated for status in result.file_statuses)
    assert [status.rows for status in result.file_statuses] == [3, 1]

    with sqlite3.connect(database_path) as connection:
        books = connection.execute(
            """
            SELECT period, platform_name, product_id, title, net_amount,
                   gross_amount, source_rows, matched
            FROM monthly_book_summary
            ORDER BY period, platform_name
            """
        ).fetchall()
        transactions = connection.execute(
            """
            SELECT transaction_date, platform_name, product_id, net_amount, matched
            FROM platform_transactions
            ORDER BY transaction_date, platform_name
            """
        ).fetchall()
        obsolete_tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN ('platform_monthly_reports', 'monthly_platform_summary')
            """
        ).fetchall()
        clients = connection.execute(
            """
            SELECT DISTINCT client_name
            FROM monthly_book_summary
            WHERE product_id = 1
            """
        ).fetchall()
        stored_products = connection.execute(
            "SELECT id, data FROM products"
        ).fetchall()

    assert books[0] == ("2026-01", "Legimi", 1, "Pierwsza ksiazka", 15.0, 18.45, 2, 1)
    assert books[1][0:3] == ("2026-02", "Legimi", 1)
    assert books[2][0:3] == ("2026-02", "Storytel", None)
    assert books[2][-1] == 0
    assert clients == [("Klient A",)]
    assert stored_products == [(99, '{"title": "Nie usuwaj"}')]
    assert transactions == [
        ("2026-01-05", "Legimi", 1, 10.0, 1),
        ("2026-01-20", "Legimi", 1, 5.0, 1),
        ("2026-02-01", "Legimi", 1, 7.0, 1),
    ]
    assert obsolete_tables == []


def test_recalculation_replaces_selected_year_instead_of_duplicating(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    _write_legimi_report(year_directory / "Legimi.xlsx")
    database_path = tmp_path / "db.sqlite"
    arguments = {
        "reports_root": reports_root,
        "database_path": database_path,
        "products": [{"id": 1, "title": "Pierwsza ksiazka", "isbn": "9781"}],
        "platforms": [{"id": 1, "name": "Legimi", "integration": "legimi"}],
    }
    _configure_existing_report_mappings(year_directory, database_path)

    calculate_platform_reports(2026, **arguments)
    calculate_platform_reports(2026, **arguments)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM monthly_book_summary WHERE year = 2026"
        ).fetchone()[0]
        runs = connection.execute(
            "SELECT COUNT(*) FROM report_calculations WHERE year = 2026"
        ).fetchone()[0]

    assert count == 2
    assert runs == 1


def test_available_report_years_include_folders_and_stale_database_years(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    (reports_root / "2024").mkdir(parents=True)
    (reports_root / "2026").mkdir()
    (reports_root / "inne").mkdir()
    database_path = tmp_path / "db.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE calculation_sources (
                id INTEGER PRIMARY KEY,
                year INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO calculation_sources (year) VALUES (2025)"
        )

    assert available_report_years(reports_root, database_path) == (
        2024,
        2025,
        2026,
    )


def test_quarterly_report_keeps_exact_range_outside_monthly_tables(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2025"
    year_directory.mkdir(parents=True)
    report_path = year_directory / "Storytel.xlsx"
    _write_quarterly_storytel_report(report_path)
    database_path = tmp_path / "db.sqlite"
    _save_mapping(
        report_path,
        database_path,
        QUARTERLY_REPORT,
        {
            "title": 0,
            "isbn": 1,
            "quantity": 2,
            "net": 3,
            "vat": 4,
            "period": 5,
        },
    )

    result = calculate_platform_reports(
        2025,
        reports_root=reports_root,
        database_path=database_path,
        products=[
            {
                "id": 1,
                "title": "Pierwsza ksiazka",
                "isbn": "9781",
                "publisher": "Klient A",
            }
        ],
        platforms=[{"id": 2, "name": "Storytel", "integration": "storytel"}],
    )

    assert result.quarterly_rows == 1
    assert result.book_summary_rows == 0
    with sqlite3.connect(database_path) as connection:
        quarterly = connection.execute(
            """
            SELECT year, quarter, period, period_start, period_end,
                   platform_name, product_id, quantity, net_amount,
                   gross_amount, source_rows, matched
            FROM quarterly_book_settlements
            """
        ).fetchall()
        monthly_count = connection.execute(
            "SELECT COUNT(*) FROM monthly_book_summary"
        ).fetchone()[0]
        transaction_count = connection.execute(
            "SELECT COUNT(*) FROM platform_transactions"
        ).fetchone()[0]

    assert len(quarterly) == 1
    assert quarterly[0][:9] == (
        2025,
        4,
        "2025-Q4",
        "2025-10-01",
        "2025-12-31",
        "Storytel",
        1,
        17.0,
        125.5,
    )
    assert quarterly[0][9] == pytest.approx(131.775)
    assert quarterly[0][10:] == (1, 1)
    assert monthly_count == 0
    assert transaction_count == 0


def test_selected_platform_recalculation_preserves_other_platforms(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    _write_legimi_report(year_directory / "Legimi.xlsx")
    _write_storytel_report(year_directory / "Storytel.xlsx")
    database_path = tmp_path / "db.sqlite"
    arguments = {
        "reports_root": reports_root,
        "database_path": database_path,
        "products": [{"id": 1, "title": "Pierwsza ksiazka", "isbn": "9781"}],
        "platforms": [
            {"id": 1, "name": "Legimi", "integration": "legimi"},
            {"id": 2, "name": "Storytel", "integration": "storytel"},
        ],
    }
    _configure_existing_report_mappings(year_directory, database_path)

    calculate_platform_reports(2026, **arguments)
    result = calculate_platform_reports(
        2026,
        selected_platform_names=["Legimi"],
        **arguments,
    )

    with sqlite3.connect(database_path) as connection:
        transactions = connection.execute(
            """
            SELECT platform_name, COUNT(*)
            FROM platform_transactions
            WHERE source_type = 'imported_report'
            GROUP BY platform_name
            ORDER BY platform_name
            """
        ).fetchall()
        sources = connection.execute(
            """
            SELECT platform_name, COUNT(*)
            FROM calculation_sources
            WHERE year = 2026
            GROUP BY platform_name
            ORDER BY platform_name
            """
        ).fetchall()

    assert result.report_files == 1
    assert transactions == [("Legimi", 3)]
    assert sources == [("Legimi", 1), ("Storytel", 1)]


def test_selected_platform_recalculation_removes_data_after_report_deleted(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    _write_legimi_report(year_directory / "Legimi.xlsx")
    storytel_path = year_directory / "Storytel.xlsx"
    _write_storytel_report(storytel_path)
    database_path = tmp_path / "db.sqlite"
    arguments = {
        "reports_root": reports_root,
        "database_path": database_path,
        "products": [{"id": 1, "title": "Pierwsza ksiazka", "isbn": "9781"}],
        "platforms": [
            {"id": 1, "name": "Legimi", "integration": "legimi"},
            {"id": 2, "name": "Storytel", "integration": "storytel"},
        ],
    }
    _configure_existing_report_mappings(year_directory, database_path)
    calculate_platform_reports(2026, **arguments)
    storytel_path.unlink()

    result = calculate_platform_reports(
        2026,
        selected_platform_names=["Storytel"],
        **arguments,
    )

    with sqlite3.connect(database_path) as connection:
        monthly = connection.execute(
            """
            SELECT platform_name, COUNT(*)
            FROM monthly_book_summary
            WHERE source_type = 'imported_report'
            GROUP BY platform_name
            ORDER BY platform_name
            """
        ).fetchall()
        transactions = connection.execute(
            """
            SELECT platform_name, COUNT(*)
            FROM platform_transactions
            WHERE source_type = 'imported_report'
            GROUP BY platform_name
            ORDER BY platform_name
            """
        ).fetchall()
        sources = connection.execute(
            """
            SELECT platform_name, COUNT(*)
            FROM calculation_sources
            WHERE year = 2026
            GROUP BY platform_name
            ORDER BY platform_name
            """
        ).fetchall()

    assert result.report_files == 0
    assert result.included_rows == 0
    assert monthly == [("Legimi", 2)]
    assert transactions == [("Legimi", 3)]
    assert sources == [("Legimi", 1)]


def test_selected_platform_ignores_unselected_unsupported_file(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    _write_legimi_report(year_directory / "Legimi.xlsx")
    (year_directory / "Voices.pdf").write_bytes(b"not a supported report")
    database_path = tmp_path / "db.sqlite"
    _configure_existing_report_mappings(year_directory, database_path)

    result = calculate_platform_reports(
        2026,
        reports_root=reports_root,
        database_path=database_path,
        products=[{"id": 1, "title": "Pierwsza ksiazka", "isbn": "9781"}],
        platforms=[{"id": 1, "name": "Legimi", "integration": "legimi"}],
        selected_platform_names=["Legimi"],
    )

    assert result.report_files == 1
    assert result.included_rows == 3


def test_calculates_valid_report_and_skips_selected_unsupported_file(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    _write_legimi_report(year_directory / "Legimi.xlsx")
    (year_directory / "Voices.pdf").write_bytes(b"not a supported report")
    database_path = tmp_path / "db.sqlite"
    _configure_existing_report_mappings(year_directory, database_path)

    result = calculate_platform_reports(
        2026,
        reports_root=reports_root,
        database_path=database_path,
        products=[{"id": 1, "title": "Pierwsza ksiazka", "isbn": "9781"}],
        platforms=[
            {"id": 1, "name": "Legimi", "integration": "legimi"},
            {"id": 2, "name": "Voices", "integration": "voices"},
        ],
        selected_platform_names=["Legimi", "Voices"],
    )

    assert result.report_files == 1
    assert result.included_rows == 3
    assert [(status.source_file, status.calculated) for status in result.file_statuses] == [
        ("Legimi.xlsx", True),
        ("Voices.pdf", False),
    ]
    assert result.file_statuses[1].action == "Zapisz raport jako plik .xlsx."
    with sqlite3.connect(database_path) as connection:
        platforms = connection.execute(
            "SELECT DISTINCT platform_name FROM monthly_book_summary"
        ).fetchall()
    assert platforms == [("Legimi",)]


def test_partial_calculation_preserves_previous_data_of_failed_platform(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    legimi_path = year_directory / "Legimi.xlsx"
    storytel_path = year_directory / "Storytel.xlsx"
    _write_legimi_report(legimi_path)
    _write_storytel_report(storytel_path)
    database_path = tmp_path / "db.sqlite"
    _configure_existing_report_mappings(year_directory, database_path)
    arguments = {
        "reports_root": reports_root,
        "database_path": database_path,
        "products": [{"id": 1, "title": "Pierwsza ksiazka", "isbn": "9781"}],
        "platforms": [
            {"id": 1, "name": "Legimi", "integration": "legimi"},
            {"id": 2, "name": "Storytel", "integration": "storytel"},
        ],
        "selected_platform_names": ["Legimi", "Storytel"],
    }
    calculate_platform_reports(2026, **arguments)

    storytel_path.unlink()
    (year_directory / "Storytel.pdf").write_bytes(b"not a supported report")
    result = calculate_platform_reports(2026, **arguments)

    assert [(status.source_file, status.calculated) for status in result.file_statuses] == [
        ("Legimi.xlsx", True),
        ("Storytel.pdf", False),
    ]
    with sqlite3.connect(database_path) as connection:
        monthly = connection.execute(
            """
            SELECT platform_name, COUNT(*)
            FROM monthly_book_summary
            GROUP BY platform_name
            ORDER BY platform_name
            """
        ).fetchall()
    assert monthly == [("Legimi", 2), ("Storytel", 1)]


def test_rejects_empty_platform_selection(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    _write_legimi_report(year_directory / "Legimi.xlsx")

    with pytest.raises(ReportCalculationError, match="co najmniej jedną platformę"):
        calculate_platform_reports(
            2026,
            reports_root=reports_root,
            database_path=tmp_path / "db.sqlite",
            products=[],
            platforms=[],
            selected_platform_names=[],
        )


def test_rejects_report_without_month_column(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Tytul", "ISBN", "Wynagrodzenie netto"])
    sheet.append(["Pierwsza ksiazka", "978-1", 10.0])
    workbook.save(year_directory / "Legimi.xlsx")

    with pytest.raises(ReportCalculationError, match="Nie rozpoznano raportu") as error:
        calculate_platform_reports(
            2026,
            reports_root=reports_root,
            database_path=tmp_path / "db.sqlite",
            products=[],
            platforms=[],
        )

    assert len(error.value.file_statuses) == 1
    status = error.value.file_statuses[0]
    assert status.source_file == "Legimi.xlsx"
    assert not status.calculated
    assert status.rows == 0
    assert status.action == "Skonfiguruj kolumny raportu."


def test_rejects_report_assigned_to_different_year(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    report_path = year_directory / "Legimi.xlsx"
    _write_legimi_report(report_path)
    workbook = load_workbook(report_path)
    try:
        sheet = workbook.active
        for row_number in (2, 3, 4):
            sheet.cell(row=row_number, column=3).value = "2025-08-01"
        workbook.save(report_path)
    finally:
        workbook.close()
    database_path = tmp_path / "db.sqlite"
    _configure_existing_report_mappings(year_directory, database_path)

    with pytest.raises(ReportCalculationError) as error:
        calculate_platform_reports(
            2026,
            reports_root=reports_root,
            database_path=database_path,
            products=[],
            platforms=[{"id": 1, "name": "Legimi", "integration": "legimi"}],
        )

    assert "przypisano do roku 2026" in str(error.value)
    assert "2025" in str(error.value)
    assert len(error.value.file_statuses) == 1
    status = error.value.file_statuses[0]
    assert not status.calculated
    assert status.rows == 3
    assert status.action == "Przypisz raport do właściwego roku."


def test_permanent_report_deletion_removes_only_selected_report_rows(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2026"
    year_directory.mkdir(parents=True)
    _write_legimi_report(year_directory / "Legimi.xlsx")
    _write_storytel_report(year_directory / "Storytel.xlsx")
    database_path = tmp_path / "db.sqlite"
    _configure_existing_report_mappings(year_directory, database_path)
    calculate_platform_reports(
        2026,
        reports_root=reports_root,
        database_path=database_path,
        products=[{"id": 1, "title": "Pierwsza ksiazka", "isbn": "9781"}],
        platforms=[
            {"id": 1, "name": "Legimi", "integration": "legimi"},
            {"id": 2, "name": "Storytel", "integration": "storytel"},
        ],
    )
    with sqlite3.connect(database_path) as connection:
        # Symulacja wpisów utworzonych przez starszą wersję, która nie
        # zapisywała nazwy pliku przy podsumowaniu miesięcznym.
        connection.execute(
            """
            UPDATE monthly_book_summary
            SET source_file = ''
            WHERE platform_key = 'legimi' AND source_type = 'imported_report'
            """
        )

    result = delete_imported_report_data(
        2026,
        "Legimi.xlsx",
        database_path=database_path,
    )

    assert result.transaction_rows == 3
    assert result.monthly_rows == 2
    assert result.source_rows == 1
    with sqlite3.connect(database_path) as connection:
        imported_transactions = connection.execute(
            "SELECT platform_name FROM platform_transactions "
            "WHERE source_type = 'imported_report'"
        ).fetchall()
        imported_months = connection.execute(
            "SELECT platform_name, source_file FROM monthly_book_summary "
            "WHERE source_type = 'imported_report'"
        ).fetchall()
        sources = connection.execute(
            "SELECT source_file FROM calculation_sources"
        ).fetchall()
        calculations = connection.execute(
            "SELECT COUNT(*) FROM report_calculations WHERE year = 2026"
        ).fetchone()[0]

    assert imported_transactions == []
    assert imported_months == [("Storytel", "Storytel.xlsx")]
    assert sources == [("Storytel.xlsx",)]
    assert calculations == 0


# ==========================================================
# Rozpoznawanie kwartału z nieregularnego zakresu dat
# ==========================================================


class TestQuarterOfRange:
    """Zakres konsumpcji bywa nieregularny i potrafi wystawać poza kwartał
    rozliczenia, więc kwartał bierzemy z tego, gdzie leży większość dni."""

    def test_range_inside_one_quarter(self):
        assert quarter_of_range("2025-10-01", "2025-12-31") == (2025, 4)
        assert quarter_of_range("2025-01-15", "2025-02-20") == (2025, 1)
        assert quarter_of_range("2025-04-01", "2025-06-30") == (2025, 2)
        assert quarter_of_range("2025-07-01", "2025-09-30") == (2025, 3)

    def test_single_day(self):
        assert quarter_of_range("2025-12-20", "2025-12-20") == (2025, 4)

    def test_range_starting_in_the_previous_quarter(self):
        # 3 dni we wrześniu, 94 w IV kwartale - to rozliczenie IV kwartału.
        assert quarter_of_range("2025-09-28", "2025-12-30") == (2025, 4)

    def test_majority_wins_the_other_way(self):
        # 30 dni we wrześniu, 5 w październiku.
        assert quarter_of_range("2025-09-01", "2025-10-05") == (2025, 3)

    def test_range_crossing_the_new_year(self):
        # 12 dni w 2025-Q4, 10 w 2026-Q1.
        assert quarter_of_range("2025-12-20", "2026-01-10") == (2025, 4)
        # Zakres rozliczany już w nowym roku.
        assert quarter_of_range("2024-12-28", "2025-03-20") == (2025, 1)

    def test_tie_goes_to_the_later_quarter(self):
        # Po 5 dni w każdym kwartale - rozliczenie zamyka ten późniejszy.
        assert quarter_of_range("2025-03-27", "2025-04-05") == (2025, 2)

    def test_reversed_dates_are_accepted(self):
        assert quarter_of_range("2025-12-30", "2025-10-06") == (2025, 4)

    def test_one_missing_date_falls_back_to_the_other(self):
        assert quarter_of_range("", "2025-11-15") == (2025, 4)
        assert quarter_of_range("2025-11-15", "") == (2025, 4)

    def test_unusable_dates_give_nothing(self):
        assert quarter_of_range("", "") is None
        assert quarter_of_range(None, None) is None
        assert quarter_of_range("nonsens", "tez nonsens") is None

    def test_garbage_next_to_a_good_date_still_works(self):
        assert quarter_of_range("nonsens", "2025-11-15") == (2025, 4)


# ==========================================================
# Dopinanie pozycji do książek dodanych po przeliczeniu
# ==========================================================


def _quarterly_db(tmp_path, rows):
    import sqlite3
    from platforms.settlements import ensure_settlement_schema

    database_path = tmp_path / "db.sqlite"
    connection = sqlite3.connect(database_path)
    with connection:
        ensure_settlement_schema(connection)
        connection.executemany(
            """
            INSERT INTO quarterly_book_settlements (
                year, quarter, period, period_start, period_end,
                platform_id, platform_key, platform_name,
                product_id, title, isbn, author, net_amount, matched, source_type
            ) VALUES (2025, 4, '2025-Q4', '2025-10-01', '2025-12-31',
                      2, 'storytel', 'Storytel', ?, ?, ?, ?, ?, ?, 'imported_report')
            """,
            rows,
        )
    connection.close()
    return database_path


def _linked(database_path):
    import sqlite3

    connection = sqlite3.connect(database_path)
    try:
        return {
            (title, author): product_id
            for title, author, product_id in connection.execute(
                "SELECT title, author, product_id FROM quarterly_book_settlements"
            )
        }
    finally:
        connection.close()


FACET = {"id": 20, "title": "Facet", "author": "Konrad Laskowski",
         "isbn": "9788368244496", "publisher": "Konrad Laskowski"}


class TestRelinkUnmatchedRows:

    def test_book_added_later_gets_its_rows(self, tmp_path):
        database = _quarterly_db(tmp_path, [
            (None, "Facet", "9788368244502", "Konrad Laskowski", 31.77, 0),
        ])

        assert relink_unmatched_rows(database, [FACET]) == 1
        assert _linked(database) == {("Facet", "Konrad Laskowski"): 20}

    def test_other_authors_books_stay_unmatched(self, tmp_path):
        database = _quarterly_db(tmp_path, [
            (None, "Facet", "9788368244496", "Krzysztof Suchowierski", 5.33, 0),
            (None, "Na nartach przez mrozy Syberii", "9788368244496",
             "Krzysztof Suchowierski", 114.56, 0),
            (None, "Facet", "9788368244502", "Konrad Laskowski", 31.77, 0),
        ])

        relink_unmatched_rows(database, [FACET])

        assert _linked(database) == {
            ("Facet", "Krzysztof Suchowierski"): None,
            ("Na nartach przez mrozy Syberii", "Krzysztof Suchowierski"): None,
            ("Facet", "Konrad Laskowski"): 20,
        }

    def test_client_name_is_filled_from_the_book(self, tmp_path):
        import sqlite3

        database = _quarterly_db(tmp_path, [
            (None, "Facet", "9788368244502", "Konrad Laskowski", 31.77, 0),
        ])
        relink_unmatched_rows(database, [FACET])

        connection = sqlite3.connect(database)
        row = connection.execute(
            "SELECT client_name, matched FROM quarterly_book_settlements"
        ).fetchone()
        connection.close()
        assert row == ("Konrad Laskowski", 1)

    def test_already_matched_rows_are_left_alone(self, tmp_path):
        database = _quarterly_db(tmp_path, [
            (99, "Facet", "9788368244502", "Konrad Laskowski", 31.77, 1),
        ])

        assert relink_unmatched_rows(database, [FACET]) == 0
        assert _linked(database) == {("Facet", "Konrad Laskowski"): 99}

    def test_running_twice_changes_nothing(self, tmp_path):
        database = _quarterly_db(tmp_path, [
            (None, "Facet", "9788368244502", "Konrad Laskowski", 31.77, 0),
        ])

        assert relink_unmatched_rows(database, [FACET]) == 1
        assert relink_unmatched_rows(database, [FACET]) == 0

    def test_missing_database_is_not_an_error(self, tmp_path):
        assert relink_unmatched_rows(tmp_path / "brak.sqlite", [FACET]) == 0

    def test_empty_product_list_does_nothing(self, tmp_path):
        database = _quarterly_db(tmp_path, [
            (None, "Facet", "9788368244502", "Konrad Laskowski", 31.77, 0),
        ])

        assert relink_unmatched_rows(database, []) == 0
