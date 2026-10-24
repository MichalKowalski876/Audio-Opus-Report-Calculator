"""Przeliczanie raportów platform do miesięcznej bazy SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence

from core import database_controller
from core import paths

from .products import find_product, normalize_isbn, normalize_title
from .reports import PLATFORM_REPORTS_ROOT, safe_platform_filename
from .settlements import (
    IMPORTED_SOURCE,
    MONTHLY_TABLE,
    QUARTERLY_TABLE,
    TRANSACTIONS_TABLE,
    ensure_settlement_schema,
)
from .xlsx_reports import (
    QUARTERLY_REPORT,
    SUPPORTED_EXCEL_SUFFIXES,
    TRANSACTION_REPORT,
    XlsxReportError,
    detect_platform_key,
    load_report_rows,
    match_rows_to_products,
    report_content_years,
    rows_for_monthly_summary,
)


DATABASE_PATH = Path(paths.data_path("Databases", "db.sqlite"))
SUPPORTED_REPORT_SUFFIXES = set(SUPPORTED_EXCEL_SUFFIXES)
KNOWN_REPORT_SUFFIXES = {
    ".xlsx",
    ".xlsm",
    ".xltx",
    ".xltm",
    ".xls",
    ".xlsb",
    ".csv",
    ".ods",
    ".pdf",
    ".zip",
}


class ReportCalculationError(RuntimeError):
    def __init__(self, message: str, file_statuses=()):
        super().__init__(message)
        self.file_statuses = tuple(file_statuses)


@dataclass(frozen=True)
class ReportFileCalculationStatus:
    year: int
    platform_name: str
    source_file: str
    calculated: bool
    rows: int
    message: str = ""
    action: str = ""


@dataclass(frozen=True)
class CalculationResult:
    database_path: Path
    year: int
    report_files: int
    source_rows: int
    included_rows: int
    book_summary_rows: int
    platform_summary_rows: int
    unmatched_books: int
    quarterly_rows: int = 0
    unmatched_entries: tuple[dict, ...] = ()
    file_statuses: tuple[ReportFileCalculationStatus, ...] = ()


@dataclass(frozen=True)
class ImportedReportDeletionResult:
    transaction_rows: int = 0
    monthly_rows: int = 0
    quarterly_rows: int = 0
    source_rows: int = 0


def _validated_year(year: int) -> int:
    try:
        report_year = int(year)
    except (TypeError, ValueError) as error:
        raise ReportCalculationError("Rok raportu musi być liczbą.") from error
    if not 1900 <= report_year <= 9999:
        raise ReportCalculationError(
            "Rok raportu musi mieścić się między 1900 a 9999."
        )
    return report_year


def _load_database_list(name: str, description: str) -> list[dict]:
    try:
        records = database_controller.load_database(name)
    except Exception as error:
        raise ReportCalculationError(
            f"Nie udało się odczytać {description}: {error}"
        ) from error
    if not isinstance(records, list):
        raise ReportCalculationError(f"{description.capitalize()} nie zawiera listy wpisów.")
    return [record for record in records if isinstance(record, dict)]


def _platform_name(platform_key: str, report_path: Path, platforms: list[dict]) -> str:
    expected_key = str(platform_key or "").strip().casefold()
    expected_stem = report_path.stem.strip().casefold()

    for platform in platforms:
        integration = str(platform.get("integration") or "").strip().casefold()
        if integration and integration == expected_key:
            return str(platform.get("name") or report_path.stem).strip()

    for platform in platforms:
        name = str(platform.get("name") or "").strip()
        safe_name = safe_platform_filename(name).casefold()
        if name and (
            name.casefold() in {expected_key, expected_stem}
            or safe_name == expected_stem
        ):
            return name

    return report_path.stem.strip() or expected_key.title() or "Platforma"


def _platform_id(platform_key: str, platform_name: str, platforms: list[dict]):
    expected_key = str(platform_key or "").strip().casefold()
    expected_name = str(platform_name or "").strip().casefold()
    for platform in platforms:
        integration = str(platform.get("integration") or "").strip().casefold()
        name = str(platform.get("name") or "").strip().casefold()
        if integration == expected_key or name in {expected_key, expected_name}:
            try:
                return int(platform.get("id"))
            except (TypeError, ValueError):
                return None
    return None


def _build_product_indexes(products: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_isbn = {}
    by_title = {}
    for product in products:
        if not isinstance(product, dict):
            continue

        isbn = normalize_isbn(product.get("isbn"))
        if isbn and isbn not in by_isbn:
            by_isbn[isbn] = product

        title = normalize_title(_product_title(product))
        if title:
            by_title[title] = product

    return by_isbn, by_title


def _product_for_row(
    row,
    products_by_isbn: dict[str, dict],
    products_by_title: dict[str, dict]
) -> dict | None:
    return find_product(
        row.title,
        row.isbn,
        getattr(row, "author", ""),
        products_by_isbn,
        products_by_title,
    )


def _transaction_summary(
    row,
    platform_key: str,
    platform_name: str,
    platform_id,
    source_file: str,
    products_by_isbn: dict[str, dict],
    products_by_title: dict[str, dict],
) -> dict:
    product = _product_for_row(row, products_by_isbn, products_by_title)
    product_id = product.get("id") if product else None
    return {
        "platform_id": platform_id,
        "platform_key": platform_key,
        "platform_name": platform_name,
        "product_id": product_id,
        "title": _product_title(product) if product else row.title,
        "isbn": str(product.get("isbn") or "").strip() if product else row.isbn,
        "client_name": (
            str(product.get("publisher") or product.get("client") or "").strip()
            if product
            else ""
        ),
        "author": row.author,
        "transaction_date": row.transaction_date or f"{row.month}-01",
        "net_amount": round(row.net, 2),
        "gross_amount": round(row.gross, 2) if row.gross is not None else None,
        "source_type": IMPORTED_SOURCE,
        "source_file": source_file,
        "matched": 1 if product else 0,
    }


def _parsed_date(value):
    """Data z pola raportu; None, gdy pole jest puste albo nieczytelne."""
    try:
        return date.fromisoformat(str(value or "")[:10])
    except (TypeError, ValueError):
        return None


def quarter_of_range(period_start, period_end) -> tuple[int, int] | None:
    """Rok i kwartał, do którego należy nieregularny zakres konsumpcji.

    Platformy podają zakresy, które potrafią wystawać poza kwartał rozliczenia
    (np. 2025-09-28 do 2025-12-30 w raporcie za IV kwartał). Kwartał bierzemy
    więc z tego, gdzie leży większość dni zakresu, a nie z samej daty
    początkowej - inaczej taka pozycja trafiłaby do poprzedniego kwartału.
    Przy remisie wygrywa późniejszy kwartał, bo to on zamyka rozliczenie.
    """
    start = _parsed_date(period_start)
    end = _parsed_date(period_end)
    if start is None and end is None:
        return None
    if start is None:
        start = end
    if end is None:
        end = start
    if end < start:
        start, end = end, start

    days_per_quarter: dict[tuple[int, int], int] = {}
    current = start
    while current <= end:
        quarter = (current.month - 1) // 3 + 1
        # Ostatni dzien kwartalu, w ktorym jestesmy.
        last_month = quarter * 3
        quarter_end = date(
            current.year + (last_month == 12),
            last_month % 12 + 1,
            1,
        ) - timedelta(days=1)

        step_end = min(end, quarter_end)
        key = (current.year, quarter)
        days_per_quarter[key] = (
            days_per_quarter.get(key, 0) + (step_end - current).days + 1
        )
        current = step_end + timedelta(days=1)

    return max(days_per_quarter.items(), key=lambda entry: (entry[1], entry[0]))[0]


def _quarterly_settlement(
    row,
    platform_key: str,
    platform_name: str,
    platform_id,
    source_file: str,
    products_by_isbn: dict[str, dict],
    products_by_title: dict[str, dict],
) -> dict:
    product = _product_for_row(row, products_by_isbn, products_by_title)
    year, quarter = quarter_of_range(row.period_start, row.period_end)
    return {
        "year": year,
        "quarter": quarter,
        "period": f"{year:04d}-Q{quarter}",
        "period_start": row.period_start,
        "period_end": row.period_end,
        "platform_id": platform_id,
        "platform_key": platform_key,
        "platform_name": platform_name,
        "product_id": product.get("id") if product else None,
        "title": _product_title(product) if product else row.title,
        "isbn": str(product.get("isbn") or "").strip() if product else row.isbn,
        "client_name": (
            str(product.get("publisher") or product.get("client") or "").strip()
            if product
            else ""
        ),
        "author": row.author,
        "quantity": row.quantity,
        "net_amount": float(row.net),
        "gross_amount": float(row.gross) if row.gross is not None else None,
        "source_rows": 1,
        "matched": 1 if product else 0,
        "source_type": IMPORTED_SOURCE,
        "source_file": source_file,
    }


def _product_title(product: dict) -> str:
    return str(
        product.get("title")
        or product.get("tytuł")
        or product.get("tytul")
        or ""
    ).strip()


def _report_files(
    year_directory: Path,
    allow_empty: bool = False,
) -> list[Path]:
    if not year_directory.is_dir():
        if allow_empty:
            return []
        raise ReportCalculationError(
            f"Brak katalogu z raportami dla roku {year_directory.name}: "
            f"{year_directory}"
        )

    files = sorted(
        (
            path
            for path in year_directory.iterdir()
            if path.is_file()
            and not path.name.startswith((".", "~$"))
            and path.suffix.lower() in KNOWN_REPORT_SUFFIXES
        ),
        key=lambda path: path.name.casefold(),
    )
    if not files and not allow_empty:
        raise ReportCalculationError(
            f"W katalogu {year_directory} nie ma raportów do przeliczenia."
        )
    return files


def available_report_years(
    reports_root: str | Path = PLATFORM_REPORTS_ROOT,
    database_path: str | Path = DATABASE_PATH,
) -> tuple[int, ...]:
    """Zwraca lata obecne w katalogach raportów lub w zaimportowanych danych.

    Lata zapisane wyłącznie w SQLite są celowo uwzględniane. Pozwala to
    przeliczeniu „Wszystkich lat” usunąć osierocone dane po ręcznym skasowaniu
    ostatniego pliku raportu z danego roku.
    """
    years = {
        int(path.name)
        for path in Path(reports_root).iterdir()
        if path.is_dir()
        and path.name.isdigit()
        and len(path.name) == 4
        and 1900 <= int(path.name) <= 9999
    } if Path(reports_root).is_dir() else set()

    database = Path(database_path)
    if not database.is_file():
        return tuple(sorted(years))

    try:
        with sqlite3.connect(database) as connection:
            table_names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            queries = []
            if "calculation_sources" in table_names:
                queries.append(
                    "SELECT DISTINCT year FROM calculation_sources"
                )
            if MONTHLY_TABLE in table_names:
                queries.append(
                    f"SELECT DISTINCT year FROM {MONTHLY_TABLE} "
                    "WHERE source_type = 'imported_report'"
                )
            if QUARTERLY_TABLE in table_names:
                queries.append(
                    f"SELECT DISTINCT year FROM {QUARTERLY_TABLE} "
                    "WHERE source_type = 'imported_report'"
                )
            if TRANSACTIONS_TABLE in table_names:
                queries.append(
                    f"SELECT DISTINCT substr(transaction_date, 1, 4) "
                    f"FROM {TRANSACTIONS_TABLE} "
                    "WHERE source_type = 'imported_report'"
                )

            for query in queries:
                for row in connection.execute(query):
                    try:
                        year = int(row[0])
                    except (TypeError, ValueError):
                        continue
                    if 1900 <= year <= 9999:
                        years.add(year)
    except sqlite3.Error as error:
        raise ReportCalculationError(
            f"Nie udało się odczytać lat raportów z SQLite: {error}"
        ) from error

    return tuple(sorted(years))


def _selected_report_files(
    files: list[Path],
    selected_platform_names: list[str] | tuple[str, ...] | set[str] | None,
) -> list[Path]:
    if selected_platform_names is None:
        return files

    selected_stems = {
        safe_platform_filename(str(name or "").strip()).casefold()
        for name in selected_platform_names
        if str(name or "").strip()
    }
    if not selected_stems:
        raise ReportCalculationError("Zaznacz co najmniej jedną platformę.")

    selected_files = [
        path for path in files if path.stem.casefold() in selected_stems
    ]
    return selected_files


def _selected_platform_keys(
    selected_platform_names: list[str] | tuple[str, ...] | set[str] | None,
    platforms: list[dict],
) -> set[str] | None:
    """Klucze platform, których dane mają zostać zastąpione.

    Lista pochodzi z wyboru użytkownika, a nie z plików znalezionych w
    katalogu. Dzięki temu usunięcie pliku raportu poza aplikacją usuwa podczas
    kolejnego przeliczenia także osierocone dane tej platformy z SQLite.
    """
    if selected_platform_names is None:
        return None

    selected_names = {
        str(name or "").strip().casefold()
        for name in selected_platform_names
        if str(name or "").strip()
    }
    if not selected_names:
        raise ReportCalculationError("Zaznacz co najmniej jedną platformę.")

    keys = {
        safe_platform_filename(name).casefold()
        for name in selected_platform_names
        if str(name or "").strip()
    }
    for platform in platforms:
        name = str(platform.get("name") or "").strip()
        if name.casefold() not in selected_names:
            continue
        safe_name = safe_platform_filename(name).casefold()
        integration = str(platform.get("integration") or "").strip().casefold()
        if safe_name:
            keys.add(safe_name)
        if integration:
            keys.add(integration)
    keys.discard("")
    return keys


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS report_calculations (
            year INTEGER PRIMARY KEY,
            calculated_at TEXT NOT NULL,
            report_files INTEGER NOT NULL,
            source_rows INTEGER NOT NULL,
            included_rows INTEGER NOT NULL,
            book_summary_rows INTEGER NOT NULL,
            platform_summary_rows INTEGER NOT NULL,
            unmatched_books INTEGER NOT NULL,
            quarterly_rows INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS calculation_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            platform_key TEXT NOT NULL,
            platform_name TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_rows INTEGER NOT NULL,
            included_rows INTEGER NOT NULL,
            skipped_rows INTEGER NOT NULL
        );
        """
    )
    ensure_settlement_schema(connection)

    calculation_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(report_calculations)")
    }
    if "quarterly_rows" not in calculation_columns:
        connection.execute(
            """
            ALTER TABLE report_calculations
            ADD COLUMN quarterly_rows INTEGER NOT NULL DEFAULT 0
            """
        )

    book_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(monthly_book_summary)")
    }
    if "client_name" not in book_columns:
        connection.execute(
            """
            ALTER TABLE monthly_book_summary
            ADD COLUMN client_name TEXT NOT NULL DEFAULT ''
            """
        )


def _book_summaries(
    grouped_rows: dict,
    products: list[dict],
    platform_ids: dict[str, int | None] | None = None,
) -> list[dict]:
    summaries = []
    platform_ids = platform_ids or {}

    for (
        period,
        platform_key,
        platform_name,
        source_file,
    ), rows in sorted(grouped_rows.items()):
        matched, unmatched = match_rows_to_products(rows, products)
        year, month = (int(part) for part in period.split("-", maxsplit=1))

        for entry in matched:
            product = entry.product
            summaries.append(
                {
                    "year": year,
                    "month": month,
                    "period": period,
                    "platform_id": platform_ids.get(platform_key),
                    "platform_key": platform_key,
                    "platform_name": platform_name,
                    "product_id": product.get("id"),
                    "title": _product_title(product) or rows[0].title,
                    "isbn": str(product.get("isbn") or "").strip(),
                    "client_name": str(
                        product.get("publisher")
                        or product.get("client")
                        or ""
                    ).strip(),
                    "author": str(product.get("author") or "").strip(),
                    "net_amount": round(entry.net, 2),
                    "gross_amount": (
                        round(entry.gross, 2) if entry.gross is not None else None
                    ),
                    "source_rows": entry.rows,
                    "matched": 1,
                    "source_type": IMPORTED_SOURCE,
                    "source_file": source_file,
                }
            )

        for entry in unmatched:
            summaries.append(
                {
                    "year": year,
                    "month": month,
                    "period": period,
                    "platform_id": platform_ids.get(platform_key),
                    "platform_key": platform_key,
                    "platform_name": platform_name,
                    "product_id": None,
                    "title": entry.title,
                    "isbn": " | ".join(sorted(entry.isbns)),
                    "client_name": "",
                    "author": entry.author,
                    "net_amount": round(entry.net, 2),
                    "gross_amount": (
                        round(entry.gross, 2) if entry.gross is not None else None
                    ),
                    "source_rows": entry.rows,
                    "matched": 0,
                    "source_type": IMPORTED_SOURCE,
                    "source_file": source_file,
                }
            )

    return sorted(
        summaries,
        key=lambda item: (
            item["year"],
            item["month"],
            item["platform_name"].casefold(),
            item["title"].casefold(),
        ),
    )


def _platform_summaries(book_summaries: list[dict]) -> list[dict]:
    grouped = {}
    for book in book_summaries:
        key = (
            book["year"],
            book["month"],
            book["period"],
            book["platform_key"],
            book["platform_name"],
        )
        summary = grouped.setdefault(
            key,
            {
                "books_count": 0,
                "matched_books": 0,
                "unmatched_books": 0,
                "net_amount": 0.0,
                "gross_amount": None,
                "source_rows": 0,
            },
        )
        summary["books_count"] += 1
        summary["matched_books" if book["matched"] else "unmatched_books"] += 1
        summary["net_amount"] += book["net_amount"]
        summary["source_rows"] += book["source_rows"]
        if book["gross_amount"] is not None:
            summary["gross_amount"] = (
                summary["gross_amount"] or 0.0
            ) + book["gross_amount"]

    results = []
    for key, amounts in sorted(grouped.items()):
        year, month, period, platform_key, platform_name = key
        results.append(
            {
                "year": year,
                "month": month,
                "period": period,
                "platform_key": platform_key,
                "platform_name": platform_name,
                **amounts,
                "net_amount": round(amounts["net_amount"], 2),
                "gross_amount": (
                    round(amounts["gross_amount"], 2)
                    if amounts["gross_amount"] is not None
                    else None
                ),
            }
        )
    return results


def _clear_previous_calculations(
    connection: sqlite3.Connection,
    year: int,
    replace_platform_keys: set[str] | None
) -> None:
    start_date = f"{year:04d}-01-01"
    end_date = f"{year + 1:04d}-01-01"

    if replace_platform_keys is None:
        connection.execute("DELETE FROM calculation_sources WHERE year = ?", (year,))
        connection.execute(
            f"DELETE FROM {TRANSACTIONS_TABLE} WHERE source_type = ? AND transaction_date >= ? AND transaction_date < ?",
            (IMPORTED_SOURCE, start_date, end_date),
        )
        connection.execute(
            f"DELETE FROM {MONTHLY_TABLE} WHERE year = ? AND source_type = ?",
            (year, IMPORTED_SOURCE),
        )
        connection.execute(
            f"DELETE FROM {QUARTERLY_TABLE} WHERE year = ? AND source_type = ?",
            (year, IMPORTED_SOURCE),
        )
    else:
        platform_keys = sorted(replace_platform_keys)
        placeholders = ", ".join("?" for _ in platform_keys)

        connection.execute(
            f"DELETE FROM calculation_sources WHERE year = ? AND platform_key IN ({placeholders})",
            (year, *platform_keys),
        )
        connection.execute(
            f"""
            DELETE FROM {TRANSACTIONS_TABLE}
            WHERE source_type = ? AND transaction_date >= ? AND transaction_date < ?
              AND platform_key IN ({placeholders})
            """,
            (IMPORTED_SOURCE, start_date, end_date, *platform_keys),
        )
        connection.execute(
            f"""
            DELETE FROM {MONTHLY_TABLE} 
            WHERE year = ? AND source_type = ? AND platform_key IN ({placeholders})
            """,
            (year, IMPORTED_SOURCE, *platform_keys),
        )
        connection.execute(
            f"""
            DELETE FROM {QUARTERLY_TABLE}
            WHERE year = ? AND source_type = ? AND platform_key IN ({placeholders})
            """,
            (year, IMPORTED_SOURCE, *platform_keys),
        )

    connection.execute("DELETE FROM report_calculations WHERE year = ?", (year,))


def _write_database(
    database_path: Path,
    year: int,
    source_summaries: list[dict],
    transaction_rows: list[dict],
    book_summaries: list[dict],
    quarterly_rows: list[dict],
    platform_summaries: list[dict],
    source_rows: int,
    included_rows: int,
    replace_platform_keys: set[str] | None = None,
) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(database_path)
    except sqlite3.Error as error:
        raise ReportCalculationError(f"Nie udało się otworzyć bazy SQLite: {error}") from error

    try:
        with connection:
            _create_schema(connection)
            _clear_previous_calculations(connection, year, replace_platform_keys)

            connection.executemany(
                """
                INSERT INTO calculation_sources (
                    year, platform_key, platform_name, source_file,
                    source_rows, included_rows, skipped_rows
                ) VALUES (
                    :year, :platform_key, :platform_name, :source_file,
                    :source_rows, :included_rows, :skipped_rows
                )
                """,
                source_summaries,
            )
            connection.executemany(
                f"""
                INSERT INTO {TRANSACTIONS_TABLE} (
                    platform_id, platform_key, platform_name, product_id,
                    title, isbn, client_name, author, transaction_date, net_amount,
                    gross_amount, source_type, source_file, matched
                ) VALUES (
                    :platform_id, :platform_key, :platform_name, :product_id,
                    :title, :isbn, :client_name, :author, :transaction_date, :net_amount,
                    :gross_amount, :source_type, :source_file, :matched
                )
                """,
                transaction_rows,
            )
            connection.executemany(
                f"""
                INSERT INTO {MONTHLY_TABLE} (
                    year, month, period, platform_id, platform_key, platform_name,
                    product_id, title, isbn, client_name, author, net_amount, gross_amount,
                    source_rows, matched, source_type, source_file
                ) VALUES (
                    :year, :month, :period, :platform_id, :platform_key, :platform_name,
                    :product_id, :title, :isbn, :client_name, :author, :net_amount, :gross_amount,
                    :source_rows, :matched, :source_type, :source_file
                )
                """,
                book_summaries,
            )
            connection.executemany(
                f"""
                INSERT INTO {QUARTERLY_TABLE} (
                    year, quarter, period, period_start, period_end,
                    platform_id, platform_key, platform_name, product_id,
                    title, isbn, client_name, author, quantity, net_amount,
                    gross_amount, source_rows, matched, source_type, source_file
                ) VALUES (
                    :year, :quarter, :period, :period_start, :period_end,
                    :platform_id, :platform_key, :platform_name, :product_id,
                    :title, :isbn, :client_name, :author, :quantity, :net_amount,
                    :gross_amount, :source_rows, :matched, :source_type, :source_file
                )
                """,
                quarterly_rows,
            )
            connection.execute(
                """
                INSERT INTO report_calculations (
                    year, calculated_at, report_files, source_rows,
                    included_rows, book_summary_rows, platform_summary_rows,
                    unmatched_books, quarterly_rows
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    year,
                    datetime.now().astimezone().isoformat(timespec="seconds"),
                    len(source_summaries),
                    source_rows,
                    included_rows,
                    len(book_summaries),
                    len(platform_summaries),
                    (
                        sum(1 for item in book_summaries if not item["matched"])
                        + sum(1 for item in quarterly_rows if not item["matched"])
                    ),
                    len(quarterly_rows),
                ),
            )
    except sqlite3.Error as error:
        raise ReportCalculationError(f"Nie udało się zapisać bazy SQLite: {error}") from error
    finally:
        connection.close()


def _row_matches_year(row, report_year: int) -> bool:
    """Sprawdza czy wiersz z nieregularną datą przypada na dany rok rozliczeniowy."""
    year_prefix = f"{report_year:04d}-"
    if row.period_start and row.period_start.startswith(year_prefix):
        return True
    if row.period_end and row.period_end.startswith(year_prefix):
        return True
    if row.month and row.month.startswith(year_prefix):
        return True
    if row.transaction_date and row.transaction_date.startswith(year_prefix):
        return True
    return False


def _remember_author(authors: dict[str, str], row) -> None:
    """Zapamiętuje autora z wiersza raportu pod ISBN i tytułem książki."""
    author = str(getattr(row, "author", "") or "").strip()
    if not author:
        return
    for key in (normalize_isbn(row.isbn), normalize_title(row.title)):
        if key:
            authors.setdefault(key, author)


def _unmatched_entries(
    book_summaries: list[dict],
    quarterly_rows: list[dict],
    authors: dict[str, str] | None = None,
) -> tuple[dict, ...]:
    """Zbiera unikalne książki spoza bazy (do okna dopisywania).

    Ta sama książka wraca w wielu miesiącach i na wielu platformach, więc
    łączymy ją po ISBN, a gdy go brak - po tytule, i sumujemy netto.
    """
    authors = authors or {}
    entries: dict[str, dict] = {}
    key_by_title: dict[str, str] = {}

    for item in (*book_summaries, *quarterly_rows):
        if item["matched"]:
            continue

        title = str(item.get("title") or "").strip()
        title_key = normalize_title(title)
        raw_isbns = [
            part.strip()
            for part in str(item.get("isbn") or "").split("|")
            if part.strip()
        ]
        valid_isbn = next(
            (value for value in map(normalize_isbn, raw_isbns) if value),
            "",
        )
        isbn = valid_isbn or (raw_isbns[0] if raw_isbns else "")

        # Własny ISBN wiersza ma priorytet nad dowiązaniem po tytule - inaczej
        # dwie różne książki o tym samym tytule (np. wznowienie) zlałyby się
        # w jeden wpis, bo druga trafiłaby przez key_by_title do wpisu
        # pierwszej. Dowiązanie po tytule służy tylko wierszom bez ISBN.
        if valid_isbn:
            key = valid_isbn
        elif title_key:
            key = key_by_title.get(title_key) or title_key
        else:
            key = None
        if not key:
            continue

        entry = entries.setdefault(
            key,
            {
                "title": title,
                "isbn": isbn,
                "author": "",
                "net": 0.0,
                "platforms": [],
                "source_files": [],
            },
        )
        if title_key:
            key_by_title.setdefault(title_key, key)
        if not entry["title"]:
            entry["title"] = title
        if not entry["isbn"]:
            entry["isbn"] = isbn
        if not entry["author"]:
            entry["author"] = authors.get(valid_isbn) or authors.get(title_key, "")

        entry["net"] += item.get("net_amount") or 0.0
        platform_name = str(item.get("platform_name") or "").strip()
        if platform_name and platform_name not in entry["platforms"]:
            entry["platforms"].append(platform_name)
        source_file = str(item.get("source_file") or "").strip()
        if source_file and source_file not in entry["source_files"]:
            entry["source_files"].append(source_file)

    return tuple(
        {
            "title": entry["title"],
            "isbn": entry["isbn"],
            "author": entry["author"],
            "platform": ", ".join(entry["platforms"]),
            "net": round(entry["net"], 2),
            "source_files": tuple(entry["source_files"]),
        }
        for entry in sorted(
            entries.values(),
            key=lambda entry: entry["title"].casefold(),
        )
    )


def calculate_platform_reports(
    year: int,
    reports_root: str | Path = PLATFORM_REPORTS_ROOT,
    database_path: str | Path = DATABASE_PATH,
    products: list[dict] | None = None,
    platforms: list[dict] | None = None,
    selected_platform_names: list[str] | tuple[str, ...] | set[str] | None = None,
) -> CalculationResult:
    """Przelicza wybrane raporty z danego roku do jednej bazy SQLite.

    Bez listy platform zachowuje dotychczasowe działanie i przelicza cały rok.
    Przy wskazaniu platform podmienia wyłącznie ich zaimportowane rozliczenia.
    """
    report_year = _validated_year(year)
    year_directory = Path(reports_root) / str(report_year)
    files = _selected_report_files(
        _report_files(
            year_directory,
            allow_empty=selected_platform_names is not None,
        ),
        selected_platform_names,
    )

    if products is None:
        products = _load_database_list("products", "bazy książek")
    if platforms is None:
        platforms = _load_database_list("streamings", "bazy platform")
    replace_platform_keys = _selected_platform_keys(
        selected_platform_names,
        platforms,
    )

    products_by_isbn, products_by_title = _build_product_indexes(products)

    grouped_rows = {}
    source_summaries = []
    transaction_rows = []
    quarterly_rows = []
    platform_ids = {}
    authors: dict[str, str] = {}
    errors = []
    file_statuses = []
    failed_platform_keys = set()
    source_rows_count = 0
    included_rows_count = 0

    for report_path in files:
        fallback_platform_name = _platform_name(
            report_path.stem,
            report_path,
            platforms,
        )
        if report_path.suffix.lower() not in SUPPORTED_REPORT_SUFFIXES:
            message = (
                f"Format {report_path.suffix.lower()} nie jest jeszcze obsługiwany."
            )
            errors.append(f"{report_path.name}: {message}")
            file_statuses.append(
                ReportFileCalculationStatus(
                    year=report_year,
                    platform_name=fallback_platform_name,
                    source_file=report_path.name,
                    calculated=False,
                    rows=0,
                    message=message,
                    action="Zapisz raport jako plik .xlsx.",
                )
            )
            failed_platform_keys.update(
                _selected_platform_keys([fallback_platform_name], platforms) or ()
            )
            continue

        try:
            platform_key, rows = load_report_rows(
                report_path,
                mapping_database_path=database_path,
            )
        except XlsxReportError as error:
            errors.append(f"{report_path.name}: {error}")
            file_statuses.append(
                ReportFileCalculationStatus(
                    year=report_year,
                    platform_name=fallback_platform_name,
                    source_file=report_path.name,
                    calculated=False,
                    rows=0,
                    message=str(error),
                    action="Skonfiguruj kolumny raportu.",
                )
            )
            failed_platform_keys.update(
                _selected_platform_keys([fallback_platform_name], platforms) or ()
            )
            continue

        display_name = _platform_name(platform_key, report_path, platforms)
        content_years = report_content_years(rows)
        if report_year not in content_years:
            years_text = ", ".join(str(value) for value in content_years) or "brak"
            message = (
                f"Raport przypisano do roku {report_year}, ale dane dotyczą "
                f"lat: {years_text}."
            )
            errors.append(f"{report_path.name}: {message} Popraw przypisanie raportu.")
            file_statuses.append(
                ReportFileCalculationStatus(
                    year=report_year,
                    platform_name=display_name,
                    source_file=report_path.name,
                    calculated=False,
                    rows=len(rows),
                    message=message,
                    action="Przypisz raport do właściwego roku.",
                )
            )
            failed_platform_keys.add(str(platform_key).strip().casefold())
            failed_platform_keys.update(
                _selected_platform_keys([display_name], platforms) or ()
            )
            continue

        missing_period_rows = [
            row
            for row in rows
            if (
                quarter_of_range(row.period_start, row.period_end) is None
                if row.report_type == QUARTERLY_REPORT
                else not row.month
            )
        ]
        if missing_period_rows:
            message = (
                f"Nie rozpoznano okresu w {len(missing_period_rows)} "
                "pozycjach raportu."
            )
            errors.append(f"{report_path.name}: {message}")
            file_statuses.append(
                ReportFileCalculationStatus(
                    year=report_year,
                    platform_name=display_name,
                    source_file=report_path.name,
                    calculated=False,
                    rows=len(rows),
                    message=message,
                    action="Skonfiguruj kolumnę daty lub okresu.",
                )
            )
            failed_platform_keys.add(str(platform_key).strip().casefold())
            failed_platform_keys.update(
                _selected_platform_keys([display_name], platforms) or ()
            )
            continue

        platform_id = _platform_id(platform_key, display_name, platforms)
        platform_ids[platform_key] = platform_id

        # Pozycję kwartalną przypisujemy do roku jej kwartału, a nie do roku
        # z daty początkowej - zakres potrafi zaczynać się jeszcze w grudniu
        # poprzedniego roku, a rozliczany jest w I kwartale następnego.
        included_rows = [
            row for row in rows if _row_matches_year(row, report_year)
        ]
        for row in included_rows:
            _remember_author(authors, row)
        source_rows_count += len(rows)
        included_rows_count += len(included_rows)
        source_summaries.append(
            {
                "year": report_year,
                "platform_key": platform_key,
                "platform_name": display_name,
                "source_file": report_path.name,
                "source_rows": len(rows),
                "included_rows": len(included_rows),
                "skipped_rows": len(rows) - len(included_rows),
            }
        )
        file_statuses.append(
            ReportFileCalculationStatus(
                year=report_year,
                platform_name=display_name,
                source_file=report_path.name,
                calculated=True,
                rows=len(included_rows),
            )
        )

        for row in rows_for_monthly_summary(included_rows):
            grouped_rows.setdefault(
                (row.month, platform_key, display_name, report_path.name), []
            ).append(row)

        for row in included_rows:
            if row.report_type == QUARTERLY_REPORT:
                quarterly_rows.append(
                    _quarterly_settlement(
                        row,
                        platform_key,
                        display_name,
                        platform_id,
                        report_path.name,
                        products_by_isbn,
                        products_by_title,
                    )
                )
                continue
            if row.report_type != TRANSACTION_REPORT:
                continue
            transaction_rows.append(
                _transaction_summary(
                    row,
                    platform_key,
                    display_name,
                    platform_id,
                    report_path.name,
                    products_by_isbn,
                    products_by_title,
                )
            )

    if errors and not source_summaries:
        details = "\n".join(f"- {error}" for error in errors)
        raise ReportCalculationError(
            "Nie udało się przeliczyć wszystkich raportów:\n" + details,
            file_statuses=tuple(file_statuses),
        )
    if files and not grouped_rows and not quarterly_rows:
        raise ReportCalculationError(
            f"Raporty nie zawierają pozycji z roku {report_year}."
        )

    book_summaries = _book_summaries(grouped_rows, products, platform_ids)
    platform_summaries = _platform_summaries(book_summaries)
    target_database = Path(database_path)
    effective_replace_platform_keys = replace_platform_keys
    if errors:
        successful_platform_keys = {
            str(summary["platform_key"]).strip().casefold()
            for summary in source_summaries
            if str(summary.get("platform_key") or "").strip()
        }
        if replace_platform_keys is None:
            effective_replace_platform_keys = successful_platform_keys
        else:
            effective_replace_platform_keys = (
                (set(replace_platform_keys) - failed_platform_keys)
                | successful_platform_keys
            )

    _write_database(
        target_database,
        report_year,
        source_summaries,
        transaction_rows,
        book_summaries,
        quarterly_rows,
        platform_summaries,
        source_rows_count,
        included_rows_count,
        replace_platform_keys=effective_replace_platform_keys,
    )

    return CalculationResult(
        database_path=target_database,
        year=report_year,
        report_files=len(source_summaries),
        source_rows=source_rows_count,
        included_rows=included_rows_count,
        book_summary_rows=len(book_summaries),
        platform_summary_rows=len(platform_summaries),
        unmatched_books=(
            sum(1 for item in book_summaries if not item["matched"])
            + sum(1 for item in quarterly_rows if not item["matched"])
        ),
        quarterly_rows=len(quarterly_rows),
        unmatched_entries=_unmatched_entries(
            book_summaries,
            quarterly_rows,
            authors,
        ),
        file_statuses=tuple(file_statuses),
    )


@dataclass(frozen=True)
class LinkedBook:
    """Książka dopisana do bazy na podstawie konkretnego raportu."""

    product_id: int
    exclusive: bool


def _ensure_added_books_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS report_added_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, source_file, product_id)
        )
        """
    )


def record_added_book(
    year: int,
    source_files: Sequence[str],
    product_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Zapamiętuje, że książka została dopisana do bazy na podstawie raportu(ów)."""
    names = sorted(
        {
            Path(str(name or "").strip()).name
            for name in source_files
            if str(name or "").strip()
        }
    )
    if not names:
        return

    target_database = Path(database_path)
    target_database.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(target_database) as connection:
            _ensure_added_books_schema(connection)
            connection.executemany(
                """
                INSERT OR IGNORE INTO report_added_books (year, source_file, product_id)
                VALUES (?, ?, ?)
                """,
                [(int(year), name, int(product_id)) for name in names],
            )
    except sqlite3.Error as error:
        raise ReportCalculationError(
            f"Nie udało się zapisać powiązania dopisanej książki z raportem: {error}"
        ) from error


def books_linked_to_report(
    year: int,
    source_file: str,
    database_path: str | Path = DATABASE_PATH,
) -> tuple[LinkedBook, ...]:
    """Zwraca książki dopisane do bazy na podstawie danego pliku raportu.

    `exclusive=True` oznacza, że książka nie jest powiązana z żadnym innym
    zachowanym raportem, więc jej usunięcie razem z raportem jest bezpieczne.
    """
    report_year = _validated_year(year)
    source_name = Path(str(source_file or "").strip()).name
    if not source_name:
        return ()

    target_database = Path(database_path)
    if not target_database.is_file():
        return ()

    try:
        with sqlite3.connect(target_database) as connection:
            _ensure_added_books_schema(connection)
            product_ids = [
                int(row[0])
                for row in connection.execute(
                    """
                    SELECT DISTINCT product_id FROM report_added_books
                    WHERE year = ? AND LOWER(source_file) = LOWER(?)
                    """,
                    (report_year, source_name),
                )
            ]
            if not product_ids:
                return ()

            # Jedno zapytanie zamiast N+1: pobiera id tych spośród
            # product_ids, które mają jakiekolwiek INNE powiązanie (rok +
            # plik różne od bieżącego raportu) - reszta jest "exclusive".
            placeholders = ", ".join("?" for _ in product_ids)
            non_exclusive_ids = {
                int(row[0])
                for row in connection.execute(
                    f"""
                    SELECT DISTINCT product_id FROM report_added_books
                    WHERE product_id IN ({placeholders})
                      AND NOT (year = ? AND LOWER(source_file) = LOWER(?))
                    """,
                    (*product_ids, report_year, source_name),
                )
            }
            return tuple(
                LinkedBook(
                    product_id=product_id,
                    exclusive=product_id not in non_exclusive_ids,
                )
                for product_id in product_ids
            )
    except sqlite3.Error as error:
        raise ReportCalculationError(
            f"Nie udało się odczytać powiązań dopisanych książek: {error}"
        ) from error


def forget_report_book_links(
    year: int,
    source_file: str,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Usuwa zapamiętane powiązania książek z raportem, który został usunięty."""
    report_year = _validated_year(year)
    source_name = Path(str(source_file or "").strip()).name
    if not source_name:
        return

    target_database = Path(database_path)
    if not target_database.is_file():
        return

    try:
        with sqlite3.connect(target_database) as connection:
            _ensure_added_books_schema(connection)
            connection.execute(
                """
                DELETE FROM report_added_books
                WHERE year = ? AND LOWER(source_file) = LOWER(?)
                """,
                (report_year, source_name),
            )
    except sqlite3.Error as error:
        raise ReportCalculationError(
            f"Nie udało się usunąć powiązań dopisanych książek: {error}"
        ) from error


def _sqlite_table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _sqlite_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table_name}")')
    }


def relink_unmatched_rows(
    database_path: str | Path = DATABASE_PATH,
    products: list[dict] | None = None,
) -> int:
    """Dopina do książek pozycje raportów, które przy przeliczaniu nie miały
    jeszcze swojej książki w bazie.

    Dopasowanie zapada w chwili „Przelicz raporty” i zostaje zapisane. Książka
    dodana później (np. na podstawie tytułu z raportu) nie widziałaby więc
    swoich kwot aż do ponownego przeliczenia. Tu dopasowujemy takie pozycje
    od nowa - tą samą regułą co przeliczanie (``find_product``).

    Zwraca liczbę dopiętych pozycji. Pozycje już dopasowane zostają
    nietknięte, więc funkcję można bezpiecznie wołać wielokrotnie.
    """
    path = Path(database_path)
    if not path.is_file():
        return 0

    if products is None:
        products = _load_database_list("products", "bazy książek")
    products_by_isbn, products_by_title = _build_product_indexes(products)
    if not products_by_isbn and not products_by_title:
        return 0

    try:
        connection = sqlite3.connect(path)
    except sqlite3.Error as error:
        raise ReportCalculationError(
            f"Nie udało się otworzyć bazy SQLite: {error}"
        ) from error
    connection.row_factory = sqlite3.Row

    linked = 0
    try:
        with connection:
            for table in (QUARTERLY_TABLE, MONTHLY_TABLE, TRANSACTIONS_TABLE):
                if not _sqlite_table_exists(connection, table):
                    continue
                columns = _sqlite_columns(connection, table)
                if not {"id", "product_id", "title", "isbn"} <= columns:
                    continue

                active = " AND deleted_at IS NULL" if "deleted_at" in columns else ""
                author = "author" if "author" in columns else "'' AS author"
                rows = connection.execute(
                    f"SELECT id, title, isbn, {author} FROM {table} "
                    f"WHERE product_id IS NULL{active}"
                ).fetchall()

                for row in rows:
                    # Tryb ostrożny: stare pozycje nie mają autora, a zapis
                    # idzie do bazy bez udziału człowieka.
                    product = find_product(
                        row["title"],
                        row["isbn"],
                        row["author"],
                        products_by_isbn,
                        products_by_title,
                        strict=True,
                    )
                    if product is None or product.get("id") is None:
                        continue

                    assignments = ["product_id = ?"]
                    parameters: list = [product.get("id")]
                    if "matched" in columns:
                        assignments.append("matched = 1")
                    if "client_name" in columns:
                        assignments.append("client_name = ?")
                        parameters.append(
                            str(
                                product.get("publisher")
                                or product.get("client")
                                or ""
                            ).strip()
                        )
                    if "updated_at" in columns:
                        assignments.append("updated_at = CURRENT_TIMESTAMP")

                    connection.execute(
                        f"UPDATE {table} SET {', '.join(assignments)} WHERE id = ?",
                        (*parameters, row["id"]),
                    )
                    linked += 1
    except sqlite3.Error as error:
        raise ReportCalculationError(
            f"Nie udało się dopasować pozycji raportów do książek: {error}"
        ) from error
    finally:
        connection.close()

    return linked


def delete_imported_report_data(
    year: int,
    source_file: str,
    database_path: str | Path = DATABASE_PATH,
) -> ImportedReportDeletionResult:
    """Usuwa wyłącznie dane zaimportowane z jednego pliku raportu."""
    report_year = _validated_year(year)
    source_name = Path(str(source_file or "").strip()).name
    if not source_name:
        raise ReportCalculationError("Nie można ustalić nazwy pliku raportu.")

    target_database = Path(database_path)
    if not target_database.is_file():
        return ImportedReportDeletionResult()

    try:
        connection = sqlite3.connect(target_database)
    except sqlite3.Error as error:
        raise ReportCalculationError(
            f"Nie udało się otworzyć bazy SQLite: {error}"
        ) from error

    transaction_rows = 0
    monthly_rows = 0
    quarterly_rows = 0
    source_rows = 0
    try:
        with connection:
            platform_keys = set()
            if _sqlite_table_exists(connection, "calculation_sources"):
                platform_keys.update(
                    str(row[0] or "").strip().casefold()
                    for row in connection.execute(
                        """
                        SELECT platform_key
                        FROM calculation_sources
                        WHERE year = ? AND LOWER(source_file) = LOWER(?)
                        """,
                        (report_year, source_name),
                    )
                    if str(row[0] or "").strip()
                )

            detected_key = detect_platform_key(source_name)
            platform_keys.add(
                str(detected_key or Path(source_name).stem).strip().casefold()
            )
            platform_keys.discard("")

            if _sqlite_table_exists(connection, TRANSACTIONS_TABLE):
                columns = _sqlite_columns(connection, TRANSACTIONS_TABLE)
                if {"source_type", "source_file", "transaction_date"} <= columns:
                    cursor = connection.execute(
                        f"""
                        DELETE FROM {TRANSACTIONS_TABLE}
                        WHERE source_type = ?
                          AND LOWER(source_file) = LOWER(?)
                          AND transaction_date >= ?
                          AND transaction_date < ?
                        """,
                        (
                            IMPORTED_SOURCE,
                            source_name,
                            f"{report_year:04d}-01-01",
                            f"{report_year + 1:04d}-01-01",
                        ),
                    )
                    transaction_rows = max(0, cursor.rowcount)

            if _sqlite_table_exists(connection, MONTHLY_TABLE):
                columns = _sqlite_columns(connection, MONTHLY_TABLE)
                if {"year", "source_type"} <= columns:
                    conditions = []
                    parameters: list[object] = [IMPORTED_SOURCE, report_year]
                    if "source_file" in columns:
                        conditions.append("LOWER(source_file) = LOWER(?)")
                        parameters.append(source_name)
                    if "platform_key" in columns and platform_keys:
                        placeholders = ", ".join("?" for _ in platform_keys)
                        legacy_source = (
                            "COALESCE(source_file, '') = '' AND "
                            if "source_file" in columns
                            else ""
                        )
                        conditions.append(
                            f"({legacy_source}LOWER(platform_key) "
                            f"IN ({placeholders}))"
                        )
                        parameters.extend(sorted(platform_keys))
                    if conditions:
                        cursor = connection.execute(
                            f"""
                            DELETE FROM {MONTHLY_TABLE}
                            WHERE source_type = ? AND year = ?
                              AND ({' OR '.join(conditions)})
                            """,
                            parameters,
                        )
                        monthly_rows = max(0, cursor.rowcount)

            if _sqlite_table_exists(connection, QUARTERLY_TABLE):
                columns = _sqlite_columns(connection, QUARTERLY_TABLE)
                if {"year", "source_type", "source_file"} <= columns:
                    cursor = connection.execute(
                        f"""
                        DELETE FROM {QUARTERLY_TABLE}
                        WHERE source_type = ? AND year = ?
                          AND LOWER(source_file) = LOWER(?)
                        """,
                        (IMPORTED_SOURCE, report_year, source_name),
                    )
                    quarterly_rows = max(0, cursor.rowcount)

            if _sqlite_table_exists(connection, "calculation_sources"):
                cursor = connection.execute(
                    """
                    DELETE FROM calculation_sources
                    WHERE year = ? AND LOWER(source_file) = LOWER(?)
                    """,
                    (report_year, source_name),
                )
                source_rows = max(0, cursor.rowcount)

            if _sqlite_table_exists(connection, "report_calculations"):
                connection.execute(
                    "DELETE FROM report_calculations WHERE year = ?",
                    (report_year,),
                )
    except sqlite3.Error as error:
        raise ReportCalculationError(
            f"Nie udało się usunąć danych raportu z SQLite: {error}"
        ) from error
    finally:
        connection.close()

    return ImportedReportDeletionResult(
        transaction_rows=transaction_rows,
        monthly_rows=monthly_rows,
        quarterly_rows=quarterly_rows,
        source_rows=source_rows,
    )
