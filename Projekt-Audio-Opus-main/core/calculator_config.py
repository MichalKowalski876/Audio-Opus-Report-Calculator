"""Konfiguracja kalkulatora (obecnie: stawka VAT).

Trzymana w Databases/calculator_config.json - w tym samym katalogu, co
reszta konfiguracji aplikacji. Wydzielenie z kodu sprawia, ze zmiana
stawki VAT nie wymaga zmiany w zrodlach ani ponownego zbudowania
aplikacji.

Przy braku lub uszkodzeniu pliku / wartosci uzywana jest wartosc
domyslna (DEFAULT_VAT_PERCENT).
"""

import json
import os

from core import database_controller


CONFIG_FILE = os.path.join(database_controller.FOLDER, "calculator_config.json")

# Wartosc uzywana, gdy pliku nie ma albo pozycja jest bledna.
DEFAULT_VAT_PERCENT = 23.0


def _load_raw():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def load_vat_percent():
    """Zwraca stawke VAT (%) z konfiguracji albo wartosc domyslna."""

    try:
        value = float(_load_raw().get("VAT_PERCENT", DEFAULT_VAT_PERCENT))
    except (TypeError, ValueError):
        return DEFAULT_VAT_PERCENT

    return value if value >= 0 else DEFAULT_VAT_PERCENT


def _save(updates):
    """Scala podane wartosci z istniejacym plikiem i zapisuje calosc."""

    os.makedirs(database_controller.FOLDER, exist_ok=True)

    data = _load_raw()
    data.update(updates)

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def save_vat_percent(value):
    """Zapisuje stawke VAT (%) do konfiguracji (bez ruszania reszty)."""

    _save({"VAT_PERCENT": float(value)})
