"""Numeracja rozliczeń w formacie RRRR/MM/NNN.

- RRRR/MM - rok i miesiąc okresu rozliczenia (dla całorocznego okresu MM = 00,
  dla "wszystkich okresów" - rok i miesiąc z daty wystawienia).
- NNN - kolejny numer, licznik zerowany co rok (1 stycznia wraca do 001).

Numer proponuje aplikacja (pierwszy wolny w danym roku), ale użytkownik może go
nadpisać ręcznie w oknie rozliczenia. Wystawione numery zapisujemy w tabeli
``settlements`` w głównej bazie - dzięki temu propozycja pomija już użyte numery,
a numeracja ma swoją historię.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core import paths


DATABASE_PATH = Path(paths.data_path("Databases", "db.sqlite"))

# Akceptujemy też skrócony zapis (2026/9/1) - przy zapisie normalizujemy.
_NUMBER_RE = re.compile(r"^\s*(\d{4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,5})\s*$")
_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$", re.IGNORECASE)


class SettlementNumberError(RuntimeError):
    pass


@dataclass(frozen=True)
class SettlementRecord:
    number: str
    seq_year: int
    seq: int
    period: str
    client_id: int | None
    client_name: str
    total_client: float | None
    pdf_filename: str
    generated_at: str


def _connect(database_path=None) -> sqlite3.Connection:
    path = Path(database_path or DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    _ensure_schema(connection)
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            seq_year INTEGER NOT NULL,
            seq INTEGER NOT NULL,
            period TEXT NOT NULL DEFAULT '',
            client_id INTEGER,
            client_name TEXT NOT NULL DEFAULT '',
            total_client REAL,
            pdf_filename TEXT NOT NULL DEFAULT '',
            generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_settlements_seq_year "
        "ON settlements(seq_year)"
    )
    connection.commit()


def parse_number(text: str) -> tuple[int, int, int]:
    """'2026/09/001' -> (2026, 9, 1). Rzuca SettlementNumberError przy złym zapisie."""
    match = _NUMBER_RE.match(str(text or ""))
    if not match:
        raise SettlementNumberError(
            "Numer rozliczenia musi mieć postać RRRR/MM/NNN."
        )
    year, month, seq = (int(part) for part in match.groups())
    if not 1 <= month <= 12 and month != 0:
        raise SettlementNumberError("Miesiąc w numerze musi być z zakresu 00-12.")
    if seq < 1:
        raise SettlementNumberError("Kolejny numer musi być większy od zera.")
    return year, month, seq


def format_number(year: int, month: int, seq: int) -> str:
    return f"{year:04d}/{month:02d}/{seq:03d}"


def normalize_number(text: str) -> str:
    """Sprowadza zapis do kanonicznego RRRR/MM/NNN."""
    return format_number(*parse_number(text))


def _period_year_month(period: str, now: datetime) -> tuple[int, int]:
    """Rok i miesiąc do numeru na podstawie okresu rozliczenia.

    - 'RRRR-MM' -> (RRRR, MM)
    - 'RRRR-QN' -> (RRRR, ostatni miesiąc kwartału)
    - 'RRRR'    -> (RRRR, 0)   (rozliczenie całoroczne)
    - ''        -> rok i miesiąc z daty wystawienia
    """
    text = str(period or "").strip()

    quarter = _QUARTER_RE.match(text)
    if quarter:
        # Kwartał zamyka się w swoim ostatnim miesiącu, więc to on trafia
        # do numeru - Q4 daje RRRR/12/NNN.
        return int(quarter.group(1)), int(quarter.group(2)) * 3

    if (
            len(text) >= 7
            and text[:4].isdigit()
            and text[4] == "-"
            and text[5:7].isdigit()
    ):
        year = int(text[:4])
        month = int(text[5:7])
        if 1 <= month <= 12:
            return year, month

    if len(text) == 4 and text.isdigit():
        return int(text), 0

    return now.year, now.month


def _next_seq(connection: sqlite3.Connection, seq_year: int) -> int:
    row = connection.execute(
        "SELECT MAX(seq) FROM settlements WHERE seq_year = ?",
        (seq_year,),
    ).fetchone()
    current = row[0] if row and row[0] is not None else 0
    return int(current) + 1


def next_number(
    period: str = "",
    now: datetime | None = None,
    database_path=None,
) -> str:
    """Proponuje pierwszy wolny numer dla danego okresu rozliczenia."""
    now = now or datetime.now()
    year, month = _period_year_month(period, now)
    connection = _connect(database_path)
    try:
        seq = _next_seq(connection, year)
    finally:
        connection.close()
    return format_number(year, month, seq)


def is_taken(number: str, database_path=None) -> bool:
    try:
        canonical = normalize_number(number)
    except SettlementNumberError:
        return False
    connection = _connect(database_path)
    try:
        row = connection.execute(
            "SELECT 1 FROM settlements WHERE number = ?",
            (canonical,),
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def get(number: str, database_path=None) -> SettlementRecord | None:
    try:
        canonical = normalize_number(number)
    except SettlementNumberError:
        return None
    connection = _connect(database_path)
    try:
        row = connection.execute(
            "SELECT * FROM settlements WHERE number = ?",
            (canonical,),
        ).fetchone()
    finally:
        connection.close()
    return _record(row) if row else None


def record_settlement(
    number: str,
    period: str = "",
    client_id: int | None = None,
    client_name: str = "",
    total_client: float | None = None,
    pdf_filename: str = "",
    now: datetime | None = None,
    database_path=None,
) -> SettlementRecord:
    """Zapisuje wystawiony numer. Istniejący numer aktualizuje (nadpisanie)."""
    year, month, seq = parse_number(number)
    canonical = format_number(year, month, seq)
    now = now or datetime.now()
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    period = str(period or "").strip()
    client_name = str(client_name or "").strip()
    pdf_filename = str(pdf_filename or "").strip()

    connection = _connect(database_path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO settlements (
                    number, seq_year, seq, period, client_id, client_name,
                    total_client, pdf_filename, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(number) DO UPDATE SET
                    seq_year = excluded.seq_year,
                    seq = excluded.seq,
                    period = excluded.period,
                    client_id = excluded.client_id,
                    client_name = excluded.client_name,
                    total_client = excluded.total_client,
                    pdf_filename = excluded.pdf_filename,
                    generated_at = excluded.generated_at
                """,
                (
                    canonical,
                    year,
                    seq,
                    period,
                    client_id,
                    client_name,
                    total_client,
                    pdf_filename,
                    generated_at,
                ),
            )
    finally:
        connection.close()

    return SettlementRecord(
        number=canonical,
        seq_year=year,
        seq=seq,
        period=period,
        client_id=client_id,
        client_name=client_name,
        total_client=total_client,
        pdf_filename=pdf_filename,
        generated_at=generated_at,
    )


def list_settlements(database_path=None) -> list[SettlementRecord]:
    connection = _connect(database_path)
    try:
        rows = connection.execute(
            "SELECT * FROM settlements ORDER BY seq_year DESC, seq DESC"
        ).fetchall()
    finally:
        connection.close()
    return [_record(row) for row in rows]


def _record(row: sqlite3.Row) -> SettlementRecord:
    return SettlementRecord(
        number=str(row["number"]),
        seq_year=int(row["seq_year"]),
        seq=int(row["seq"]),
        period=str(row["period"] or ""),
        client_id=row["client_id"],
        client_name=str(row["client_name"] or ""),
        total_client=row["total_client"],
        pdf_filename=str(row["pdf_filename"] or ""),
        generated_at=str(row["generated_at"] or ""),
    )


def number_to_filename_part(number: str) -> str:
    """'2026/09/001' -> '2026-09-001' (ukośnik nie może być w nazwie pliku)."""
    return str(number or "").strip().replace("/", "-")
