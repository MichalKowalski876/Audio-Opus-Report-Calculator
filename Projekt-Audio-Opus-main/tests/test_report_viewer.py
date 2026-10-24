import sqlite3

from platforms.report_viewer import (
    list_book_reports,
    list_monthly_book_reports,
    list_monthly_report_transactions,
    list_quarterly_book_reports,
    load_book_report_details,
)
from platforms.settlements import ensure_settlement_schema


def _write_report_database(path, include_client=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    client_column = (
        "client_name TEXT NOT NULL DEFAULT ''," if include_client else ""
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            f"""
            CREATE TABLE monthly_book_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                period TEXT NOT NULL,
                platform_key TEXT NOT NULL,
                platform_name TEXT NOT NULL,
                product_id INTEGER,
                title TEXT NOT NULL,
                isbn TEXT NOT NULL DEFAULT '',
                {client_column}
                net_amount REAL NOT NULL,
                gross_amount REAL,
                source_rows INTEGER NOT NULL,
                matched INTEGER NOT NULL
            )
            """
        )
        columns = (
            "year, month, period, platform_key, platform_name, product_id, "
            "title, isbn, client_name, net_amount, gross_amount, source_rows, matched"
            if include_client
            else
            "year, month, period, platform_key, platform_name, product_id, "
            "title, isbn, net_amount, gross_amount, source_rows, matched"
        )
        placeholders = ", ".join("?" for _ in columns.split(", "))
        rows = [
            (2026, 1, "2026-01", "legimi", "Legimi", 1, "Książka A", "978-1", "Klient A", 10.0, 12.3, 2, 1),
            (2026, 2, "2026-02", "storytel", "Storytel", 1, "Książka A", "978-1", "Klient A", 20.0, 24.6, 3, 1),
            (2026, 2, "2026-02", "legimi", "Legimi", 2, "Książka B", "978-2", "Klient B", 5.0, None, 1, 1),
            (2025, 12, "2025-12", "legimi", "Legimi", 1, "Książka A", "978-1", "Klient A", 7.0, 8.61, 1, 1),
        ]
        if not include_client:
            rows = [row[:8] + row[9:] for row in rows]
        connection.executemany(
            f"INSERT INTO monthly_book_summary ({columns}) VALUES ({placeholders})",
            rows,
        )


def test_lists_one_yearly_report_per_book_across_all_platforms(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _write_report_database(database_path)

    reports = list_book_reports(database_path, products=[])

    assert [(report.year, report.title) for report in reports] == [
        (2026, "Książka A"),
        (2026, "Książka B"),
        (2025, "Książka A"),
    ]
    report = reports[0]
    assert report.isbn == "978-1"
    assert report.client_name == "Klient A"
    assert report.total_net == 30.0
    assert report.total_gross == 36.9
    assert report.platforms_count == 2
    assert report.months_count == 2
    assert report.source_rows == 5


def test_loads_monthly_details_from_every_platform(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _write_report_database(database_path)
    report = list_book_reports(database_path, products=[])[0]

    details = load_book_report_details(report, database_path)

    assert [(entry.period, entry.platform_name) for entry in details.entries] == [
        ("2026-01", "Legimi"),
        ("2026-02", "Storytel"),
    ]
    assert [entry.net_amount for entry in details.entries] == [10.0, 20.0]


def test_lists_monthly_reports_grouped_by_book_across_platforms(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _write_report_database(database_path)

    reports = list_monthly_book_reports(database_path, products=[])

    assert [(report.period, report.title) for report in reports] == [
        ("2026-02", "Książka A"),
        ("2026-02", "Książka B"),
        ("2026-01", "Książka A"),
        ("2025-12", "Książka A"),
    ]
    report = reports[0]
    assert report.client_name == "Klient A"
    assert report.total_net == 20.0
    assert report.total_gross == 24.6
    assert report.platforms_count == 1
    assert report.source_rows == 3


def test_loads_transactions_for_selected_book_and_month(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _write_report_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE platform_transactions (
                id INTEGER PRIMARY KEY,
                platform_name TEXT NOT NULL,
                product_id INTEGER,
                title TEXT NOT NULL,
                isbn TEXT NOT NULL,
                client_name TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                net_amount REAL NOT NULL,
                gross_amount REAL,
                source_type TEXT NOT NULL,
                source_file TEXT NOT NULL,
                deleted_at TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO platform_transactions (
                id, platform_name, product_id, title, isbn, client_name,
                transaction_date, net_amount, gross_amount, source_type,
                source_file, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "Storytel", 1, "Książka A", "978-1", "Klient A", "2026-02-03", 5.0, 6.15, "imported_report", "Storytel.xlsx", None),
                (2, "Legimi", 1, "Książka A", "978-1", "Klient A", "2026-02-20", 15.0, 18.45, "imported_report", "Legimi.xlsx", None),
                (3, "Legimi", 2, "Książka B", "978-2", "Klient B", "2026-02-10", 7.0, 8.61, "imported_report", "Legimi.xlsx", None),
                (4, "Legimi", 1, "Książka A", "978-1", "Klient A", "2026-01-10", 3.0, 3.69, "imported_report", "Legimi.xlsx", None),
                (5, "Legimi", 1, "Książka A", "978-1", "Klient A", "2026-02-12", 4.0, 4.92, "imported_report", "Legimi.xlsx", "2026-03-01"),
            ],
        )

    report = next(
        item
        for item in list_monthly_book_reports(database_path, products=[])
        if item.period == "2026-02" and item.product_id == 1
    )
    transactions = list_monthly_report_transactions(report, database_path)

    assert [transaction.transaction_id for transaction in transactions] == [1, 2]
    assert [transaction.platform_name for transaction in transactions] == [
        "Storytel",
        "Legimi",
    ]
    assert sum(transaction.net_amount for transaction in transactions) == 20.0


def test_monthly_report_without_transaction_table_returns_empty_list(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _write_report_database(database_path)
    report = list_monthly_book_reports(database_path, products=[])[0]

    assert list_monthly_report_transactions(report, database_path) == []


def test_reads_client_from_products_for_database_without_client_column(tmp_path):
    database_path = tmp_path / "legacy_schema.sqlite"
    _write_report_database(database_path, include_client=False)

    reports = list_book_reports(
        database_path,
        products=[{"id": 1, "title": "Książka A", "publisher": "Klient A"}],
    )

    report = next(item for item in reports if item.product_id == 1)
    assert report.client_name == "Klient A"


def test_missing_database_returns_empty_report_list(tmp_path):
    assert list_book_reports(tmp_path / "missing.sqlite", products=[]) == []


def test_ignores_monthly_entries_moved_to_trash(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _write_report_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "ALTER TABLE monthly_book_summary ADD COLUMN deleted_at TEXT"
        )
        connection.execute(
            """
            UPDATE monthly_book_summary
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE year = 2026 AND period = '2026-02' AND product_id = 1
            """
        )

    report = next(
        item
        for item in list_book_reports(database_path, products=[])
        if item.year == 2026 and item.product_id == 1
    )

    assert report.total_net == 10.0
    assert report.months_count == 1


def test_lists_quarterly_ranges_and_includes_them_in_yearly_report(tmp_path):
    database_path = tmp_path / "db.sqlite"
    _write_report_database(database_path)
    with sqlite3.connect(database_path) as connection:
        ensure_settlement_schema(connection)
        connection.execute(
            """
            INSERT INTO quarterly_book_settlements (
                year, quarter, period, period_start, period_end,
                platform_key, platform_name, product_id, title, isbn,
                client_name, quantity, net_amount, gross_amount,
                source_rows, matched, source_type, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2026,
                4,
                "2026-Q4",
                "2026-10-01",
                "2026-12-31",
                "storytel",
                "Storytel",
                1,
                "Ksiazka A",
                "978-1",
                "Klient A",
                17.0,
                25.0,
                30.75,
                1,
                1,
                "imported_report",
                "Storytel.xlsx",
            ),
        )

    quarterly = list_quarterly_book_reports(database_path, products=[])
    assert len(quarterly) == 1
    assert quarterly[0].period == "2026-Q4"
    assert quarterly[0].period_start == "2026-10-01"
    assert quarterly[0].period_end == "2026-12-31"
    assert quarterly[0].quantity == 17.0

    annual = next(
        report
        for report in list_book_reports(database_path, products=[])
        if report.year == 2026 and report.product_id == 1
    )
    assert annual.total_net == 55.0
    assert annual.total_gross == 67.65
    assert annual.months_count == 3

    details = load_book_report_details(annual, database_path)
    assert [entry.period for entry in details.entries] == [
        "2026-01",
        "2026-02",
        "2026-Q4 (2026-10-01 – 2026-12-31)",
    ]
