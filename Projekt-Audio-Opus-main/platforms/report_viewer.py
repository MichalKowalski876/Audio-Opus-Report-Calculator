"""Odczyt zbiorczych raportów książek z głównej bazy SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core import database_controller

from .products import normalize_isbn, normalize_title
from .report_calculator import DATABASE_PATH
from .settlements import IMPORTED_SOURCE, QUARTERLY_TABLE


class ReportViewerError(RuntimeError):
    pass


@dataclass(frozen=True)
class BookReportSummary:
    year: int
    product_id: int | None
    title: str
    isbn: str
    client_name: str
    total_net: float
    total_gross: float | None
    platforms_count: int
    months_count: int
    source_rows: int


@dataclass(frozen=True)
class MonthlyBookReportSummary:
    year: int
    period: str
    product_id: int | None
    title: str
    isbn: str
    client_name: str
    total_net: float
    total_gross: float | None
    platforms_count: int
    source_rows: int


@dataclass(frozen=True)
class QuarterlyBookReportSummary:
    settlement_id: int
    year: int
    quarter: int
    period: str
    period_start: str
    period_end: str
    platform_name: str
    product_id: int | None
    title: str
    isbn: str
    client_name: str
    quantity: float | None
    total_net: float
    total_gross: float | None
    source_rows: int


@dataclass(frozen=True)
class MonthlyReportTransaction:
    transaction_id: int
    platform_name: str
    transaction_date: str
    title: str
    isbn: str
    client_name: str
    net_amount: float
    gross_amount: float | None
    source_type: str
    source_file: str


@dataclass(frozen=True)
class BookReportEntry:
    platform_name: str
    period: str
    net_amount: float
    gross_amount: float | None
    source_rows: int


@dataclass(frozen=True)
class BookReportDetails:
    report: BookReportSummary
    entries: tuple[BookReportEntry, ...]


def _connect(database_path: str | Path) -> sqlite3.Connection | None:
    path = Path(database_path)
    if not path.is_file():
        return None
    try:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as error:
        raise ReportViewerError(
            f"Nie udało się otworzyć bazy raportów: {error}"
        ) from error


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _book_columns(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(monthly_book_summary)")
    }


def _load_products(products: list[dict] | None) -> list[dict]:
    if products is not None:
        return [product for product in products if isinstance(product, dict)]
    try:
        loaded = database_controller.load_database("products")
    except Exception as error:
        raise ReportViewerError(
            f"Nie udało się odczytać klientów książek: {error}"
        ) from error
    if not isinstance(loaded, list):
        raise ReportViewerError("Baza książek nie zawiera listy wpisów.")
    return [product for product in loaded if isinstance(product, dict)]


def _products_by_id(products: list[dict]) -> dict[int, dict]:
    result = {}
    for product in products:
        try:
            product_id = int(product.get("id"))
        except (TypeError, ValueError):
            continue
        result[product_id] = product
    return result


def _client_name(row: sqlite3.Row, product: dict | None, has_client: bool) -> str:
    stored_client = str(row["client_name"] or "").strip() if has_client else ""
    if stored_client:
        return stored_client
    if not product:
        return ""
    return str(
        product.get("publisher")
        or product.get("client")
        or ""
    ).strip()


def _identity(product_id, title: str, isbn: str):
    if product_id is not None:
        return "product", int(product_id)
    return "unmatched", normalize_title(title), normalize_isbn(isbn)


def _read_book_rows(
    database_path: str | Path,
) -> tuple[list[sqlite3.Row], bool]:
    connection = _connect(database_path)
    if connection is None:
        return [], False
    try:
        if not _table_exists(connection, "monthly_book_summary"):
            return [], False
        columns = _book_columns(connection)
        has_client = "client_name" in columns
        client_expression = "client_name" if has_client else "'' AS client_name"
        conditions = []
        parameters = []
        if "deleted_at" in columns:
            conditions.append("deleted_at IS NULL")
        if "source_type" in columns:
            conditions.append("source_type = ?")
            parameters.append(IMPORTED_SOURCE)
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = connection.execute(
            f"""
            SELECT year, period, platform_name, product_id, title, isbn,
                   {client_expression}, net_amount, gross_amount, source_rows
            FROM monthly_book_summary
            {where_clause}
            ORDER BY year DESC, title, period, platform_name
            """,
            parameters,
        ).fetchall()
        return rows, has_client
    except sqlite3.Error as error:
        raise ReportViewerError(
            f"Nie udało się odczytać bazy raportów: {error}"
        ) from error
    finally:
        connection.close()


def _read_quarterly_rows(
    database_path: str | Path,
) -> tuple[list[sqlite3.Row], bool]:
    connection = _connect(database_path)
    if connection is None:
        return [], False
    try:
        if not _table_exists(connection, QUARTERLY_TABLE):
            return [], False
        columns = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({QUARTERLY_TABLE})")
        }
        has_client = "client_name" in columns
        client_expression = "client_name" if has_client else "'' AS client_name"
        conditions = []
        parameters = []
        if "deleted_at" in columns:
            conditions.append("deleted_at IS NULL")
        if "source_type" in columns:
            conditions.append("source_type = ?")
            parameters.append(IMPORTED_SOURCE)
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = connection.execute(
            f"""
            SELECT id, year, quarter, period, period_start, period_end,
                   platform_name, product_id, title, isbn, {client_expression},
                   quantity, net_amount, gross_amount, source_rows
            FROM {QUARTERLY_TABLE}
            {where_clause}
            ORDER BY year DESC, quarter DESC, title, period_start, platform_name
            """,
            parameters,
        ).fetchall()
        return rows, has_client
    except sqlite3.Error as error:
        raise ReportViewerError(
            f"Nie udało się odczytać rozliczeń kwartalnych: {error}"
        ) from error
    finally:
        connection.close()


def list_book_reports(
    database_path: str | Path = DATABASE_PATH,
    products: list[dict] | None = None,
) -> list[BookReportSummary]:
    """Zwraca jeden raport roczny dla każdej książki ze wszystkich platform."""
    rows, has_client = _read_book_rows(database_path)
    quarterly_rows, quarterly_has_client = _read_quarterly_rows(database_path)
    if not rows and not quarterly_rows:
        return []

    product_index = _products_by_id(_load_products(products))
    grouped = {}

    for row in rows:
        product_id = row["product_id"]
        product = product_index.get(int(product_id)) if product_id is not None else None
        title = str(row["title"] or "").strip()
        isbn = str(row["isbn"] or "").strip()
        key = (int(row["year"]), _identity(product_id, title, isbn))
        summary = grouped.setdefault(
            key,
            {
                "year": int(row["year"]),
                "product_id": int(product_id) if product_id is not None else None,
                "title": title,
                "isbn": isbn,
                "client_name": _client_name(row, product, has_client),
                "total_net": 0.0,
                "total_gross": None,
                "platforms": set(),
                "months": set(),
                "source_rows": 0,
            },
        )
        summary["total_net"] += float(row["net_amount"] or 0.0)
        if row["gross_amount"] is not None:
            summary["total_gross"] = (
                summary["total_gross"] or 0.0
            ) + float(row["gross_amount"])
        summary["platforms"].add(str(row["platform_name"] or ""))
        summary["months"].add(str(row["period"] or ""))
        summary["source_rows"] += int(row["source_rows"] or 0)

    for row in quarterly_rows:
        product_id = row["product_id"]
        product = product_index.get(int(product_id)) if product_id is not None else None
        title = str(row["title"] or "").strip()
        isbn = str(row["isbn"] or "").strip()
        key = (int(row["year"]), _identity(product_id, title, isbn))
        summary = grouped.setdefault(
            key,
            {
                "year": int(row["year"]),
                "product_id": int(product_id) if product_id is not None else None,
                "title": title,
                "isbn": isbn,
                "client_name": _client_name(
                    row,
                    product,
                    quarterly_has_client,
                ),
                "total_net": 0.0,
                "total_gross": None,
                "platforms": set(),
                "months": set(),
                "source_rows": 0,
            },
        )
        summary["total_net"] += float(row["net_amount"] or 0.0)
        if row["gross_amount"] is not None:
            summary["total_gross"] = (
                summary["total_gross"] or 0.0
            ) + float(row["gross_amount"])
        summary["platforms"].add(str(row["platform_name"] or ""))
        summary["months"].add(str(row["period"] or ""))
        summary["source_rows"] += int(row["source_rows"] or 0)

    reports = [
        BookReportSummary(
            year=summary["year"],
            product_id=summary["product_id"],
            title=summary["title"],
            isbn=summary["isbn"],
            client_name=summary["client_name"],
            total_net=round(summary["total_net"], 2),
            total_gross=(
                round(summary["total_gross"], 2)
                if summary["total_gross"] is not None
                else None
            ),
            platforms_count=len(summary["platforms"]),
            months_count=len(summary["months"]),
            source_rows=summary["source_rows"],
        )
        for summary in grouped.values()
    ]
    return sorted(
        reports,
        key=lambda report: (-report.year, report.title.casefold(), report.isbn),
    )


def list_monthly_book_reports(
    database_path: str | Path = DATABASE_PATH,
    products: list[dict] | None = None,
) -> list[MonthlyBookReportSummary]:
    """Zwraca miesięczne podsumowania książek ze wszystkich platform."""
    rows, has_client = _read_book_rows(database_path)
    if not rows:
        return []

    product_index = _products_by_id(_load_products(products))
    grouped = {}

    for row in rows:
        product_id = row["product_id"]
        product = product_index.get(int(product_id)) if product_id is not None else None
        title = str(row["title"] or "").strip()
        isbn = str(row["isbn"] or "").strip()
        period = str(row["period"] or "").strip()
        key = (
            int(row["year"]),
            period,
            _identity(product_id, title, isbn),
        )
        summary = grouped.setdefault(
            key,
            {
                "year": int(row["year"]),
                "period": period,
                "product_id": int(product_id) if product_id is not None else None,
                "title": title,
                "isbn": isbn,
                "client_name": _client_name(row, product, has_client),
                "total_net": 0.0,
                "total_gross": None,
                "platforms": set(),
                "source_rows": 0,
            },
        )
        summary["total_net"] += float(row["net_amount"] or 0.0)
        if row["gross_amount"] is not None:
            summary["total_gross"] = (
                summary["total_gross"] or 0.0
            ) + float(row["gross_amount"])
        summary["platforms"].add(str(row["platform_name"] or ""))
        summary["source_rows"] += int(row["source_rows"] or 0)

    reports = [
        MonthlyBookReportSummary(
            year=summary["year"],
            period=summary["period"],
            product_id=summary["product_id"],
            title=summary["title"],
            isbn=summary["isbn"],
            client_name=summary["client_name"],
            total_net=round(summary["total_net"], 2),
            total_gross=(
                round(summary["total_gross"], 2)
                if summary["total_gross"] is not None
                else None
            ),
            platforms_count=len(summary["platforms"]),
            source_rows=summary["source_rows"],
        )
        for summary in grouped.values()
    ]
    reports.sort(key=lambda report: (report.title.casefold(), report.isbn))
    reports.sort(key=lambda report: (report.year, report.period), reverse=True)
    return reports


def list_quarterly_book_reports(
    database_path: str | Path = DATABASE_PATH,
    products: list[dict] | None = None,
) -> list[QuarterlyBookReportSummary]:
    """Zwraca rozliczenia z dokładnymi, nieregularnymi zakresami dat."""
    rows, has_client = _read_quarterly_rows(database_path)
    if not rows:
        return []

    product_index = _products_by_id(_load_products(products))
    reports = []
    for row in rows:
        product_id = row["product_id"]
        product = product_index.get(int(product_id)) if product_id is not None else None
        reports.append(
            QuarterlyBookReportSummary(
                settlement_id=int(row["id"]),
                year=int(row["year"]),
                quarter=int(row["quarter"]),
                period=str(row["period"] or "").strip(),
                period_start=str(row["period_start"] or "").strip(),
                period_end=str(row["period_end"] or "").strip(),
                platform_name=str(row["platform_name"] or "").strip(),
                product_id=(int(product_id) if product_id is not None else None),
                title=str(row["title"] or "").strip(),
                isbn=str(row["isbn"] or "").strip(),
                client_name=_client_name(row, product, has_client),
                quantity=(
                    float(row["quantity"])
                    if row["quantity"] is not None
                    else None
                ),
                total_net=round(float(row["net_amount"] or 0.0), 2),
                total_gross=(
                    round(float(row["gross_amount"]), 2)
                    if row["gross_amount"] is not None
                    else None
                ),
                source_rows=int(row["source_rows"] or 0),
            )
        )
    return reports


def list_monthly_report_transactions(
    report: MonthlyBookReportSummary,
    database_path: str | Path = DATABASE_PATH,
) -> list[MonthlyReportTransaction]:
    """Zwraca pojedyncze transakcje tworzące miesięczny raport książki."""
    connection = _connect(database_path)
    if connection is None:
        return []
    try:
        if not _table_exists(connection, "platform_transactions"):
            return []
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(platform_transactions)"
            )
        }
        required = {"id", "transaction_date", "net_amount"}
        if not required <= columns:
            raise ReportViewerError(
                "Tabela transakcji ma nieobsługiwany układ danych."
            )

        def expression(column: str, fallback: str) -> str:
            return column if column in columns else f"{fallback} AS {column}"

        conditions = ["substr(transaction_date, 1, 7) = ?"]
        parameters = [str(report.period)]
        if "deleted_at" in columns:
            conditions.append("deleted_at IS NULL")
        if "source_type" in columns:
            conditions.append("source_type = ?")
            parameters.append(IMPORTED_SOURCE)
        rows = connection.execute(
            f"""
            SELECT id,
                   {expression('platform_name', "''")},
                   transaction_date,
                   {expression('product_id', 'NULL')},
                   {expression('title', "''")},
                   {expression('isbn', "''")},
                   {expression('client_name', "''")},
                   net_amount,
                   {expression('gross_amount', 'NULL')},
                   {expression('source_type', "''")},
                   {expression('source_file', "''")}
            FROM platform_transactions
            WHERE {' AND '.join(conditions)}
            ORDER BY transaction_date, platform_name COLLATE NOCASE, id
            """,
            parameters,
        ).fetchall()
    except sqlite3.Error as error:
        raise ReportViewerError(
            f"Nie udało się odczytać transakcji raportu: {error}"
        ) from error
    finally:
        connection.close()

    expected_identity = _identity(report.product_id, report.title, report.isbn)
    transactions = []
    for row in rows:
        if _identity(row["product_id"], row["title"], row["isbn"]) != expected_identity:
            continue
        transactions.append(
            MonthlyReportTransaction(
                transaction_id=int(row["id"]),
                platform_name=str(row["platform_name"] or "").strip(),
                transaction_date=str(row["transaction_date"] or "").strip(),
                title=str(row["title"] or "").strip(),
                isbn=str(row["isbn"] or "").strip(),
                client_name=str(row["client_name"] or "").strip(),
                net_amount=round(float(row["net_amount"] or 0.0), 2),
                gross_amount=(
                    round(float(row["gross_amount"]), 2)
                    if row["gross_amount"] is not None
                    else None
                ),
                source_type=str(row["source_type"] or "").strip(),
                source_file=str(row["source_file"] or "").strip(),
            )
        )
    return transactions


def load_book_report_details(
    report: BookReportSummary,
    database_path: str | Path = DATABASE_PATH,
) -> BookReportDetails:
    """Zwraca miesięczne i kwartalne pozycje książki ze wszystkich platform."""
    rows, _has_client = _read_book_rows(database_path)
    quarterly_rows, _quarterly_has_client = _read_quarterly_rows(database_path)
    expected_identity = _identity(report.product_id, report.title, report.isbn)
    entries = []

    for row in rows:
        if int(row["year"]) != report.year:
            continue
        if _identity(row["product_id"], row["title"], row["isbn"]) != expected_identity:
            continue
        entries.append(
            BookReportEntry(
                platform_name=str(row["platform_name"] or ""),
                period=str(row["period"] or ""),
                net_amount=round(float(row["net_amount"] or 0.0), 2),
                gross_amount=(
                    round(float(row["gross_amount"]), 2)
                    if row["gross_amount"] is not None
                    else None
                ),
                source_rows=int(row["source_rows"] or 0),
            )
        )

    for row in quarterly_rows:
        if int(row["year"]) != report.year:
            continue
        if _identity(row["product_id"], row["title"], row["isbn"]) != expected_identity:
            continue
        entries.append(
            BookReportEntry(
                platform_name=str(row["platform_name"] or ""),
                period=(
                    f"{str(row['period'] or '')} "
                    f"({str(row['period_start'] or '')} – "
                    f"{str(row['period_end'] or '')})"
                ).strip(),
                net_amount=round(float(row["net_amount"] or 0.0), 2),
                gross_amount=(
                    round(float(row["gross_amount"]), 2)
                    if row["gross_amount"] is not None
                    else None
                ),
                source_rows=int(row["source_rows"] or 0),
            )
        )

    if not entries:
        raise ReportViewerError(
            "Nie znaleziono szczegółów wybranego raportu. Przelicz raporty ponownie."
        )

    entries.sort(key=lambda entry: (entry.period, entry.platform_name.casefold()))
    return BookReportDetails(report=report, entries=tuple(entries))
