"""Wspolny schemat rozliczen platform streamingowych w SQLite."""

from __future__ import annotations

import json
import sqlite3


TRANSACTIONS_TABLE = "platform_transactions"
MONTHLY_TABLE = "monthly_book_summary"
QUARTERLY_TABLE = "quarterly_book_settlements"
IMPORTED_SOURCE = "imported_report"


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone() is not None


def _columns(connection: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    return {
        str(row[1]): row
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def _create_transactions_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TRANSACTIONS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_id INTEGER,
            platform_key TEXT NOT NULL DEFAULT '',
            platform_name TEXT NOT NULL DEFAULT '',
            product_id INTEGER,
            title TEXT NOT NULL DEFAULT '',
            isbn TEXT NOT NULL DEFAULT '',
            client_name TEXT NOT NULL DEFAULT '',
            transaction_date TEXT NOT NULL,
            net_amount REAL NOT NULL DEFAULT 0,
            gross_amount REAL,
            source_type TEXT NOT NULL DEFAULT '{IMPORTED_SOURCE}',
            source_file TEXT NOT NULL DEFAULT '',
            matched INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT,
            FOREIGN KEY (platform_id) REFERENCES streamings(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )


def _rebuild_legacy_transactions(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, TRANSACTIONS_TABLE):
        _create_transactions_table(connection)
        return

    columns = _columns(connection, TRANSACTIONS_TABLE)
    expected = {
        "id",
        "platform_id",
        "platform_key",
        "platform_name",
        "product_id",
        "title",
        "isbn",
        "client_name",
        "transaction_date",
        "net_amount",
        "gross_amount",
        "source_type",
        "source_file",
        "matched",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    product_is_required = bool(columns.get("product_id") and columns["product_id"][3])
    if expected <= set(columns) and not product_is_required:
        return

    legacy_table = "_legacy_platform_transactions"
    connection.execute(f'DROP TABLE IF EXISTS "{legacy_table}"')
    connection.execute(
        f'ALTER TABLE "{TRANSACTIONS_TABLE}" RENAME TO "{legacy_table}"'
    )
    _create_transactions_table(connection)

    legacy_columns = _columns(connection, legacy_table)

    def expression(name: str, fallback: str) -> str:
        return f'"{name}"' if name in legacy_columns else fallback

    connection.execute(
        f"""
        INSERT INTO {TRANSACTIONS_TABLE} (
            id, platform_id, platform_key, platform_name, product_id,
            title, isbn, client_name, transaction_date, net_amount,
            gross_amount, source_type, source_file, matched,
            created_at, updated_at, deleted_at
        )
        SELECT
            {expression('id', 'NULL')},
            {expression('platform_id', 'NULL')},
            {expression('platform_key', "''")},
            {expression('platform_name', "''")},
            {expression('product_id', 'NULL')},
            {expression('title', "''")},
            {expression('isbn', "''")},
            {expression('client_name', "''")},
            {expression('transaction_date', "date('now')")},
            {expression('net_amount', '0')},
            {expression('gross_amount', 'NULL')},
            {expression('source_type', repr(IMPORTED_SOURCE))},
            {expression('source_file', "''")},
            {expression('matched', '1')},
            {expression('created_at', 'CURRENT_TIMESTAMP')},
            {expression('updated_at', expression('created_at', 'CURRENT_TIMESTAMP'))},
            {expression('deleted_at', 'NULL')}
        FROM "{legacy_table}"
        """
    )
    connection.execute(f'DROP TABLE "{legacy_table}"')


def _create_monthly_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MONTHLY_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            period TEXT NOT NULL,
            platform_id INTEGER,
            platform_key TEXT NOT NULL DEFAULT '',
            platform_name TEXT NOT NULL DEFAULT '',
            product_id INTEGER,
            title TEXT NOT NULL DEFAULT '',
            isbn TEXT NOT NULL DEFAULT '',
            client_name TEXT NOT NULL DEFAULT '',
            net_amount REAL NOT NULL DEFAULT 0,
            gross_amount REAL,
            source_rows INTEGER NOT NULL DEFAULT 0,
            matched INTEGER NOT NULL DEFAULT 1,
            source_type TEXT NOT NULL DEFAULT '{IMPORTED_SOURCE}',
            source_file TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT,
            FOREIGN KEY (platform_id) REFERENCES streamings(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )


def _create_quarterly_table(connection: sqlite3.Connection) -> None:
    """Tworzy listę rozliczeń obejmujących nieregularne zakresy kwartału."""
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {QUARTERLY_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            period TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            platform_id INTEGER,
            platform_key TEXT NOT NULL DEFAULT '',
            platform_name TEXT NOT NULL DEFAULT '',
            product_id INTEGER,
            title TEXT NOT NULL DEFAULT '',
            isbn TEXT NOT NULL DEFAULT '',
            client_name TEXT NOT NULL DEFAULT '',
            quantity REAL,
            net_amount REAL NOT NULL DEFAULT 0,
            gross_amount REAL,
            source_rows INTEGER NOT NULL DEFAULT 1,
            matched INTEGER NOT NULL DEFAULT 1,
            source_type TEXT NOT NULL DEFAULT '{IMPORTED_SOURCE}',
            source_file TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT,
            FOREIGN KEY (platform_id) REFERENCES streamings(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )


def _add_monthly_columns(connection: sqlite3.Connection) -> None:
    additions = {
        "platform_id": "INTEGER",
        "client_name": "TEXT NOT NULL DEFAULT ''",
        "source_type": f"TEXT NOT NULL DEFAULT '{IMPORTED_SOURCE}'",
        "source_file": "TEXT NOT NULL DEFAULT ''",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        "deleted_at": "TEXT",
    }
    columns = _columns(connection, MONTHLY_TABLE)
    for name, declaration in additions.items():
        if name not in columns:
            connection.execute(
                f'ALTER TABLE "{MONTHLY_TABLE}" ADD COLUMN "{name}" {declaration}'
            )
    connection.execute(
        f"""
        UPDATE {MONTHLY_TABLE}
        SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
            updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE created_at IS NULL OR updated_at IS NULL
        """
    )


def _json_record(connection: sqlite3.Connection, table: str, identifier) -> dict:
    if identifier is None or not _table_exists(connection, table):
        return {}
    columns = _columns(connection, table)
    if "data" not in columns:
        return {}
    row = connection.execute(
        f'SELECT data FROM "{table}" WHERE id = ?',
        (identifier,),
    ).fetchone()
    if not row:
        return {}
    try:
        value = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def platform_details(
    connection: sqlite3.Connection,
    platform_id,
) -> tuple[str, str]:
    record = _json_record(connection, "streamings", platform_id)
    name = str(record.get("name") or "").strip()
    key = str(record.get("integration") or name).strip().casefold()
    if not name and platform_id is not None:
        name = f"Platforma {platform_id}"
    return key, name


def product_details(
    connection: sqlite3.Connection,
    product_id,
) -> tuple[str, str, str]:
    if product_id is None or not _table_exists(connection, "products"):
        return "", "", ""
    columns = _columns(connection, "products")
    if {"title", "isbn"} <= set(columns):
        client_expression = (
            "COALESCE(clients.name, '')"
            if "client_id" in columns and _table_exists(connection, "clients")
            else "''"
        )
        join = (
            "LEFT JOIN clients ON clients.id = products.client_id"
            if "client_id" in columns and _table_exists(connection, "clients")
            else ""
        )
        row = connection.execute(
            f"""
            SELECT products.title, products.isbn, {client_expression}
            FROM products
            {join}
            WHERE products.id = ?
            """,
            (product_id,),
        ).fetchone()
        if row:
            return tuple(str(value or "").strip() for value in row)

    record = _json_record(connection, "products", product_id)
    return (
        str(record.get("title") or "").strip(),
        str(record.get("isbn") or "").strip(),
        str(record.get("publisher") or record.get("client") or "").strip(),
    )


def _backfill_transaction_details(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        f"""
        SELECT id, platform_id, product_id, platform_key, platform_name,
               title, isbn, client_name
        FROM {TRANSACTIONS_TABLE}
        """
    ).fetchall()
    for row in rows:
        platform_key, platform_name = platform_details(connection, row[1])
        title, isbn, client_name = product_details(connection, row[2])
        connection.execute(
            f"""
            UPDATE {TRANSACTIONS_TABLE}
            SET platform_key = CASE WHEN platform_key = '' THEN ? ELSE platform_key END,
                platform_name = CASE WHEN platform_name = '' THEN ? ELSE platform_name END,
                title = CASE WHEN title = '' THEN ? ELSE title END,
                isbn = CASE WHEN isbn = '' THEN ? ELSE isbn END,
                client_name = CASE WHEN client_name = '' THEN ? ELSE client_name END
            WHERE id = ?
            """,
            (platform_key, platform_name, title, isbn, client_name, row[0]),
        )


def _add_author_columns(connection: sqlite3.Connection) -> None:
    """Autor z raportu - pozwala odróżnić dwie różne książki, którym platforma
    dała ten sam ISBN albo ten sam tytuł. Starsze bazy go nie mają."""
    for table in (TRANSACTIONS_TABLE, MONTHLY_TABLE, QUARTERLY_TABLE):
        if _table_exists(connection, table) and "author" not in _columns(connection, table):
            connection.execute(
                f"ALTER TABLE \"{table}\" ADD COLUMN author TEXT NOT NULL DEFAULT ''"
            )


def ensure_settlement_schema(connection: sqlite3.Connection) -> None:
    """Zapewnia wspólne tabele danych z przeliczonych raportów."""
    _rebuild_legacy_transactions(connection)
    _create_monthly_table(connection)
    _create_quarterly_table(connection)
    _add_monthly_columns(connection)
    _add_author_columns(connection)
    _backfill_transaction_details(connection)
    # To bylo wyliczone powielenie danych z tabeli miesiecznej. Podsumowanie
    # platformy nalezy liczyc zapytaniem GROUP BY, bez trzeciej tabeli.
    connection.execute("DROP TABLE IF EXISTS monthly_platform_summary")
    connection.executescript(
        f"""
        CREATE INDEX IF NOT EXISTS idx_platform_transactions_month
            ON {TRANSACTIONS_TABLE} (
                platform_id, product_id, transaction_date, deleted_at
            );
        CREATE INDEX IF NOT EXISTS idx_platform_transactions_source
            ON {TRANSACTIONS_TABLE} (source_type, transaction_date);
        CREATE INDEX IF NOT EXISTS idx_monthly_books_year_month
            ON {MONTHLY_TABLE} (year, month);
        CREATE INDEX IF NOT EXISTS idx_monthly_books_platform
            ON {MONTHLY_TABLE} (platform_key, year, month);
        CREATE INDEX IF NOT EXISTS idx_monthly_books_product
            ON {MONTHLY_TABLE} (product_id, year, month);
        CREATE INDEX IF NOT EXISTS idx_monthly_books_source
            ON {MONTHLY_TABLE} (source_type, year, month);
        CREATE INDEX IF NOT EXISTS idx_quarterly_books_year_quarter
            ON {QUARTERLY_TABLE} (year, quarter);
        CREATE INDEX IF NOT EXISTS idx_quarterly_books_platform
            ON {QUARTERLY_TABLE} (platform_key, year, quarter);
        CREATE INDEX IF NOT EXISTS idx_quarterly_books_product
            ON {QUARTERLY_TABLE} (product_id, year, quarter);
        CREATE INDEX IF NOT EXISTS idx_quarterly_books_source
            ON {QUARTERLY_TABLE} (source_type, year, source_file);
        """
    )
