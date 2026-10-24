"""Odczyt kwot netto/brutto książek z przeliczonych raportów w SQLite.

Okno „Nowe rozliczenie” nie czyta plików Excel. Korzysta z podsumowań
utworzonych wcześniej przez funkcję „Przelicz raporty”:

* miesięcznych (``monthly_book_summary``) - okres ``RRRR-MM``,
* kwartalnych (``quarterly_book_settlements``) - okres ``RRRR-QN``, gdzie
  platforma podaje nieregularny zakres dat zamiast pełnego miesiąca.

Oba rodzaje są rozłączne (platforma raportuje albo miesięcznie, albo
kwartalnie), więc dla okresu rocznego i „wszystkich okresów” sumujemy je
razem - tak samo jak robi to widok raportów.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core import paths

from .settlements import IMPORTED_SOURCE, MONTHLY_TABLE, QUARTERLY_TABLE


# Ta sama baza, do której zapisuje „Przelicz raporty” - w wersji spakowanej
# to katalog danych użytkownika, a nie katalog programu.
DATABASE_PATH = Path(paths.data_path("Databases", "db.sqlite"))

# Pusty okres oznacza "policz wszystko, co jest w bazie".
ALL_PERIODS = ""


class SettlementAmountsError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlatformAmount:
    """Kwoty jednej ksiazki na jednej platformie w wybranym okresie."""

    product_id: int
    platform_id: int | None
    platform_key: str
    platform_name: str
    net: float
    gross: float | None
    periods: tuple[str, ...]
    entries: int


_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$", re.IGNORECASE)


def normalize_period(period) -> str:
    """Sprowadza okres do postaci '', 'RRRR', 'RRRR-MM' albo 'RRRR-QN'."""
    text = str(period or "").strip()
    if not text:
        return ALL_PERIODS
    if len(text) == 4 and text.isdigit():
        return text

    quarter = _QUARTER_RE.match(text)
    if quarter:
        return f"{int(quarter.group(1)):04d}-Q{quarter.group(2)}"

    if (
            len(text) >= 7
            and text[:4].isdigit()
            and text[4] == "-"
            and text[5:7].isdigit()
    ):
        month = int(text[5:7])
        if 1 <= month <= 12:
            return text[:7]

    raise SettlementAmountsError(
        "Okres rozliczenia musi mieć postać RRRR, RRRR-MM (MM to 01-12) "
        "albo RRRR-QN (N to 1-4)."
    )


def is_quarter(period) -> bool:
    """True dla okresu kwartalnego 'RRRR-QN'."""
    return bool(_QUARTER_RE.match(str(period or "").strip()))


def period_year(period) -> int | None:
    """Rok okresu; None dla 'wszystkich okresów'."""
    text = normalize_period(period)
    return int(text[:4]) if text else None


def _connect(database_path: str | Path) -> sqlite3.Connection | None:
    path = Path(database_path)
    if not path.is_file():
        return None
    try:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as error:
        raise SettlementAmountsError(
            f"Nie udało się otworzyć bazy rozliczeń: {error}"
        ) from error


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone() is not None


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def _active_condition(columns: set[str]) -> str:
    # Starsze bazy nie znaja jeszcze miekkiego usuwania.
    return "deleted_at IS NULL" if "deleted_at" in columns else "1 = 1"


def _monthly_period_filter(period: str) -> tuple[str, list]:
    if not period:
        return "1 = 1", []
    if len(period) == 4:
        return "period LIKE ?", [f"{period}-%"]
    return "period = ?", [period]


def _quarterly_period_filter(period: str) -> tuple[str, list]:
    if not period:
        return "1 = 1", []
    if len(period) == 4:
        return "year = ?", [int(period)]
    return "year = ? AND quarter = ?", [int(period[:4]), int(period[6])]


def _reads_monthly(period: str) -> bool:
    """Okres kwartalny nie dotyczy podsumowań miesięcznych."""
    return not is_quarter(period)


def _reads_quarterly(period: str) -> bool:
    """Okres miesięczny nie dotyczy rozliczeń kwartalnych.

    Raport kwartalny podaje jedną kwotę za cały, nieregularny zakres
    konsumpcji i nie mówi, ile z niej przypada na dany miesiąc - nie da się
    z niego uczciwie policzyć miesiąca."""
    return len(period) != 7 or is_quarter(period)


def _source_conditions(columns: set[str]) -> tuple[list[str], list]:
    conditions = [_active_condition(columns)]
    parameters: list = []
    if "source_type" in columns:
        conditions.append("source_type = ?")
        parameters.append(IMPORTED_SOURCE)
    return conditions, parameters


def available_periods(database_path: str | Path = DATABASE_PATH) -> list[str]:
    """Zwraca okresy przeliczonych raportów, od najnowszego.

    Miesiące ('RRRR-MM') i kwartały ('RRRR-QN') trafiają na jedną listę -
    okres bierze się z danych, więc nowy raport sam dokłada swój okres.
    """
    connection = _connect(database_path)
    if connection is None:
        return []

    periods: set[str] = set()
    try:
        if _table_exists(connection, MONTHLY_TABLE):
            columns = _columns(connection, MONTHLY_TABLE)
            conditions, parameters = _source_conditions(columns)
            rows = connection.execute(
                f"""
                SELECT DISTINCT period
                FROM {MONTHLY_TABLE}
                WHERE {' AND '.join(conditions)}
                  AND period IS NOT NULL AND period <> ''
                """,
                parameters,
            )
            periods.update(str(row["period"])[:7] for row in rows)

        if _table_exists(connection, QUARTERLY_TABLE):
            columns = _columns(connection, QUARTERLY_TABLE)
            conditions, parameters = _source_conditions(columns)
            rows = connection.execute(
                f"""
                SELECT DISTINCT year, quarter
                FROM {QUARTERLY_TABLE}
                WHERE {' AND '.join(conditions)}
                  AND year IS NOT NULL AND quarter IS NOT NULL
                """,
                parameters,
            )
            periods.update(
                f"{int(row['year']):04d}-Q{int(row['quarter'])}"
                for row in rows
            )
    except sqlite3.Error as error:
        raise SettlementAmountsError(
            f"Nie udało się odczytać okresów rozliczeń: {error}"
        ) from error
    finally:
        connection.close()

    # Kwartał sortujemy jak jego ostatni miesiąc, żeby w obrębie roku stał
    # obok miesięcy, które obejmuje.
    def order(period: str) -> tuple:
        if is_quarter(period):
            return period[:4], f"{int(period[6]) * 3:02d}", 1
        return period[:4], period[5:7], 0

    return sorted(
        (period for period in periods if len(period) == 7),
        key=order,
        reverse=True,
    )


def _platform_identity(row: sqlite3.Row) -> tuple:
    """Klucz grupowania platformy - id, a dla starszych wpisow nazwa."""
    platform_id = row["platform_id"]
    if platform_id is not None:
        return ("id", int(platform_id))
    name = str(row["platform_key"] or row["platform_name"] or "").strip()
    return ("name", name.casefold())


def _product_ids(product_ids) -> list[int]:
    if isinstance(product_ids, (int, str)):
        product_ids = [product_ids]
    result = []
    for value in product_ids or []:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(result))


def _accumulate(buckets: dict, row: sqlite3.Row, period: str) -> None:
    key = (int(row["product_id"]), _platform_identity(row))
    bucket = buckets.setdefault(
        key,
        {
            "platform_id": row["platform_id"],
            "platform_key": str(row["platform_key"] or "").strip(),
            "platform_name": str(row["platform_name"] or "").strip(),
            "net": 0.0,
            "gross": None,
            "periods": set(),
            "entries": 0,
        },
    )
    bucket["net"] += float(row["net_amount"] or 0.0)
    if row["gross_amount"] is not None:
        bucket["gross"] = (bucket["gross"] or 0.0) + float(row["gross_amount"])
    if period:
        bucket["periods"].add(period)
    bucket["entries"] += 1
    if not bucket["platform_name"]:
        bucket["platform_name"] = str(row["platform_name"] or "").strip()


def load_amounts(
    product_ids,
    period: str = ALL_PERIODS,
    database_path: str | Path = DATABASE_PATH,
) -> dict[int, list[PlatformAmount]]:
    """Sumuje przeliczone raporty książek w rozbiciu na platformy.

    Podstawą są podsumowania utworzone przez funkcję „Przelicz raporty” -
    miesięczne oraz kwartalne (nieregularne zakresy dat). Pojedyncze
    transakcje są danymi szczegółowymi, dlatego nie są tutaj dodawane
    ponownie.
    """
    identifiers = _product_ids(product_ids)
    if not identifiers:
        return {}

    period = normalize_period(period)
    connection = _connect(database_path)
    if connection is None:
        return {}

    placeholders = ", ".join("?" for _ in identifiers)
    buckets: dict = {}
    try:
        if _reads_monthly(period) and _table_exists(connection, MONTHLY_TABLE):
            columns = _columns(connection, MONTHLY_TABLE)
            conditions, source_params = _source_conditions(columns)
            period_filter, period_params = _monthly_period_filter(period)
            rows = connection.execute(
                f"""
                SELECT product_id, platform_id, platform_key, platform_name,
                       period, net_amount, gross_amount
                FROM {MONTHLY_TABLE}
                WHERE product_id IN ({placeholders})
                  AND {' AND '.join(conditions)} AND {period_filter}
                """,
                (*identifiers, *source_params, *period_params),
            ).fetchall()
            for row in rows:
                row_period = str(row["period"] or "")[:7]
                _accumulate(buckets, row, row_period)

        if _reads_quarterly(period) and _table_exists(connection, QUARTERLY_TABLE):
            columns = _columns(connection, QUARTERLY_TABLE)
            conditions, source_params = _source_conditions(columns)
            period_filter, period_params = _quarterly_period_filter(period)
            rows = connection.execute(
                f"""
                SELECT product_id, platform_id, platform_key, platform_name,
                       period, net_amount, gross_amount
                FROM {QUARTERLY_TABLE}
                WHERE product_id IN ({placeholders})
                  AND {' AND '.join(conditions)} AND {period_filter}
                """,
                (*identifiers, *source_params, *period_params),
            ).fetchall()
            for row in rows:
                _accumulate(buckets, row, str(row["period"] or "").strip())
    except sqlite3.Error as error:
        raise SettlementAmountsError(
            f"Nie udało się odczytać kwot z bazy: {error}"
        ) from error
    finally:
        connection.close()

    result: dict[int, list[PlatformAmount]] = {}
    for (product_id, _identity), bucket in buckets.items():
        result.setdefault(product_id, []).append(
            PlatformAmount(
                product_id=product_id,
                platform_id=(
                    int(bucket["platform_id"])
                    if bucket["platform_id"] is not None
                    else None
                ),
                platform_key=bucket["platform_key"],
                platform_name=bucket["platform_name"],
                net=round(bucket["net"], 2),
                gross=(
                    round(bucket["gross"], 2)
                    if bucket["gross"] is not None
                    else None
                ),
                periods=tuple(sorted(bucket["periods"])),
                entries=bucket["entries"],
            )
        )

    for amounts in result.values():
        amounts.sort(key=lambda amount: amount.platform_name.casefold())
    return result


def load_product_amounts(
    product_id,
    period: str = ALL_PERIODS,
    database_path: str | Path = DATABASE_PATH,
) -> list[PlatformAmount]:
    """Kwoty jednej ksiazki w rozbiciu na platformy."""
    return load_amounts([product_id], period, database_path).get(
        int(product_id), []
    )


@dataclass(frozen=True)
class PeriodSpan:
    """Rzeczywisty zakres dat objęty rozliczeniem."""

    start: str
    end: str

    def __str__(self) -> str:
        return self.start if self.start == self.end else f"{self.start} – {self.end}"


def period_span(
    period: str = ALL_PERIODS,
    product_ids=None,
    database_path: str | Path = DATABASE_PATH,
) -> PeriodSpan | None:
    """Zakres dat rozliczeń kwartalnych objętych okresem.

    Platformy raportujące kwartalnie podają nieregularny zakres (np.
    2025-10-02 - 2025-12-28), a nie pełny kwartał. Zwracamy faktyczne
    krańce tego zakresu, żeby raport mógł je wypisać. ``None`` oznacza, że
    w danym okresie nie ma rozliczeń kwartalnych - czyli daty są regularne
    i wystarczy sama nazwa okresu.
    """
    period = normalize_period(period)
    if not _reads_quarterly(period):
        return None

    connection = _connect(database_path)
    if connection is None:
        return None

    try:
        if not _table_exists(connection, QUARTERLY_TABLE):
            return None

        columns = _columns(connection, QUARTERLY_TABLE)
        conditions, parameters = _source_conditions(columns)
        period_filter, period_params = _quarterly_period_filter(period)
        conditions.append(period_filter)
        parameters.extend(period_params)

        identifiers = _product_ids(product_ids) if product_ids is not None else []
        if identifiers:
            placeholders = ", ".join("?" for _ in identifiers)
            conditions.append(f"product_id IN ({placeholders})")
            parameters.extend(identifiers)

        row = connection.execute(
            f"""
            SELECT MIN(period_start) AS start, MAX(period_end) AS end
            FROM {QUARTERLY_TABLE}
            WHERE {' AND '.join(conditions)}
              AND period_start IS NOT NULL AND period_start <> ''
              AND period_end IS NOT NULL AND period_end <> ''
            """,
            parameters,
        ).fetchone()
    except sqlite3.Error as error:
        raise SettlementAmountsError(
            f"Nie udało się odczytać zakresu dat rozliczenia: {error}"
        ) from error
    finally:
        connection.close()

    if not row or not row["start"] or not row["end"]:
        return None
    return PeriodSpan(start=str(row["start"]), end=str(row["end"]))
