"""Zapamiętane mapowania kolumn raportów Excel.

Mapowanie jest przypisane jednocześnie do platformy oraz sygnatury układu
nagłówków. Dzięki temu ustawienia jednej platformy nie wpływają na inną, a
zmiana kolejności albo liczby kolumn jest traktowana jako nowy układ.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from core import paths


DEFAULT_DATABASE_PATH = Path(paths.data_path("Databases", "db.sqlite"))

ALLOWED_FIELDS = {
    "title",
    "isbn",
    "author",
    "transaction_date",
    "period",
    "sale_type",
    "net",
    "gross",
    "vat",
    "quantity",
}
ALLOWED_REPORT_TYPES = {"transaction", "monthly", "quarterly"}


class ColumnMappingError(RuntimeError):
    pass


@dataclass(frozen=True)
class SavedColumnMapping:
    platform_key: str
    layout_signature: str
    report_type: str
    columns: dict[str, int]
    headers: tuple[str, ...]


def normalize_column_name(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value).strip())
    text = "".join(
        character for character in text if not unicodedata.combining(character)
    )
    text = text.casefold()
    text = re.sub(r"[_\-/\\]+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_platform_key(value: Any) -> str:
    key = " ".join(str(value or "").strip().casefold().split())
    if not key:
        raise ColumnMappingError("Nie podano platformy dla mapowania kolumn.")
    return key


def normalized_headers(headers: Sequence[Any]) -> tuple[str, ...]:
    values = [normalize_column_name(value) for value in headers]
    while values and not values[-1]:
        values.pop()
    return tuple(values)


def layout_signature(headers: Sequence[Any]) -> str:
    payload = json.dumps(
        normalized_headers(headers),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_mapping(report_type: str, columns: Mapping[str, int]) -> dict[str, int]:
    report_type = str(report_type or "").strip().casefold()
    if report_type not in ALLOWED_REPORT_TYPES:
        raise ColumnMappingError("Niepoprawny typ raportu.")

    cleaned: dict[str, int] = {}
    for field_name, column_index in columns.items():
        if field_name not in ALLOWED_FIELDS:
            raise ColumnMappingError(f"Nieznane pole mapowania: {field_name}.")
        if isinstance(column_index, bool) or not isinstance(column_index, int):
            raise ColumnMappingError(f"Niepoprawny numer kolumny dla pola {field_name}.")
        if column_index < 0:
            raise ColumnMappingError(f"Numer kolumny dla pola {field_name} jest ujemny.")
        cleaned[field_name] = column_index

    required = {"title", "isbn", "net"}
    required.add("transaction_date" if report_type == "transaction" else "period")
    missing = sorted(required - cleaned.keys())
    if missing:
        raise ColumnMappingError(
            "Brak wymaganych pól mapowania: " + ", ".join(missing) + "."
        )
    if len(set(cleaned.values())) != len(cleaned):
        raise ColumnMappingError("Jedna kolumna nie może być przypisana do kilku pól.")
    return cleaned


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS report_column_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_key TEXT NOT NULL,
            layout_signature TEXT NOT NULL,
            report_type TEXT NOT NULL,
            mapping_json TEXT NOT NULL,
            headers_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(platform_key, layout_signature)
        )
        """
    )


def save_column_mapping(
    platform_key: str,
    headers: Sequence[Any],
    report_type: str,
    columns: Mapping[str, int],
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> SavedColumnMapping:
    key = normalize_platform_key(platform_key)
    report_type = str(report_type or "").strip().casefold()
    cleaned_columns = _validate_mapping(report_type, columns)
    header_values = tuple(
        "" if value is None else str(value).strip() for value in headers
    )
    while header_values and not header_values[-1]:
        header_values = header_values[:-1]
    signature = layout_signature(header_values)

    path = Path(database_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            _create_schema(connection)
            connection.execute(
                """
                INSERT INTO report_column_mappings (
                    platform_key, layout_signature, report_type,
                    mapping_json, headers_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(platform_key, layout_signature) DO UPDATE SET
                    report_type = excluded.report_type,
                    mapping_json = excluded.mapping_json,
                    headers_json = excluded.headers_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    key,
                    signature,
                    report_type,
                    json.dumps(cleaned_columns, ensure_ascii=False, sort_keys=True),
                    json.dumps(header_values, ensure_ascii=False),
                ),
            )
    except sqlite3.Error as error:
        raise ColumnMappingError(
            f"Nie udało się zapisać mapowania kolumn: {error}"
        ) from error

    return SavedColumnMapping(
        platform_key=key,
        layout_signature=signature,
        report_type=report_type,
        columns=cleaned_columns,
        headers=header_values,
    )


def load_platform_column_mappings(
    platform_key: str,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> dict[str, SavedColumnMapping]:
    key = normalize_platform_key(platform_key)
    path = Path(database_path)
    if not path.is_file():
        return {}

    try:
        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            table_exists = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'report_column_mappings'
                """
            ).fetchone()
            if not table_exists:
                return {}
            rows = connection.execute(
                """
                SELECT platform_key, layout_signature, report_type,
                       mapping_json, headers_json
                FROM report_column_mappings
                WHERE platform_key = ?
                """,
                (key,),
            ).fetchall()
    except sqlite3.Error as error:
        raise ColumnMappingError(
            f"Nie udało się odczytać mapowań kolumn: {error}"
        ) from error

    mappings: dict[str, SavedColumnMapping] = {}
    for row in rows:
        try:
            columns = {
                str(field_name): int(column_index)
                for field_name, column_index in json.loads(row["mapping_json"]).items()
            }
            headers = tuple(str(value) for value in json.loads(row["headers_json"]))
            columns = _validate_mapping(row["report_type"], columns)
        except (ColumnMappingError, TypeError, ValueError, json.JSONDecodeError):
            continue
        mapping = SavedColumnMapping(
            platform_key=row["platform_key"],
            layout_signature=row["layout_signature"],
            report_type=row["report_type"],
            columns=columns,
            headers=headers,
        )
        mappings[mapping.layout_signature] = mapping
    return mappings
