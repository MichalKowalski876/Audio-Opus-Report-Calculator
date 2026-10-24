import sqlite3

from platforms.settlements import ensure_settlement_schema


def test_schema_contains_shared_transaction_monthly_and_quarterly_tables(tmp_path):
    database_path = tmp_path / "db.sqlite"
    with sqlite3.connect(database_path) as connection:
        ensure_settlement_schema(connection)
        settlement_tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                  AND name IN (
                      'platform_transactions', 'monthly_book_summary',
                      'quarterly_book_settlements',
                      'platform_monthly_reports', 'monthly_platform_summary'
                  )
                """
            )
        }
        transaction_default = connection.execute(
            "PRAGMA table_info(platform_transactions)"
        ).fetchall()

    defaults = {row[1]: row[4] for row in transaction_default}
    assert settlement_tables == {
        "platform_transactions",
        "monthly_book_summary",
        "quarterly_book_settlements",
    }
    assert defaults["source_type"] == "'imported_report'"
