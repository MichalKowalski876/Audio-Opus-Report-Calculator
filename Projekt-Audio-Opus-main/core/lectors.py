"""Przechowywanie listy lektorow (stawki za arkusz) dla kalkulatora.

Dane trzymane sa w tabeli "lectors" w Databases/db.sqlite (przez
database_controller) - tak samo jak reszta nierelacyjnych "baz" (np.
streamings): kazdy lektor to wiersz {id, data}, kolekcja jest tez
zwierciadlona do Databases/lectors.json przy kazdym zapisie (ten sam
mechanizm automatycznie zaimportowal istniejacy plik JSON do bazy przy
pierwszym uruchomieniu tej wersji).

Kazdy lektor to slownik:

    {"id": 1, "name": "Wojtek Masiak", "rate": 400.0, "surcharge": 50.0}

    rate      - stawka lektora za arkusz wydawniczy (netto),
    surcharge - narzut Audio Opus za arkusz wydawniczy (netto).

Gdy baza jest pusta (pierwsze uruchomienie), zasiewana jest lista
domyslna (DEFAULT_LECTORS) zbudowana na podstawie aktualnego cennika.
"""

from core import database_controller


DB_NAME = "lectors"


DEFAULT_LECTORS = [
    {"name": "Karolina", "rate": 300.0, "surcharge": 0.0},
    {"name": "Iza Dobrowolska", "rate": 250.0, "surcharge": 50.0},
    {"name": "Maciej Marcinkowski", "rate": 350.0, "surcharge": 50.0},
    {"name": "Darek Januszewski", "rate": 350.0, "surcharge": 50.0},
    {"name": "Wojtek Masiak", "rate": 400.0, "surcharge": 50.0},
    {"name": "Monika Wrońska", "rate": 450.0, "surcharge": 50.0},
    {"name": "Karol Kunysz", "rate": 350.0, "surcharge": 50.0},
    {"name": "Weronika Musiał", "rate": 250.0, "surcharge": 50.0},
]


def _clean_entry(entry):
    """Zamienia wpis z bazy na uporzadkowany slownik albo None, gdy jest bledny."""

    try:
        name = str(entry["name"]).strip()
    except (KeyError, TypeError):
        return None

    if not name:
        return None

    try:
        rate = float(entry.get("rate", 0) or 0)
        surcharge = float(entry.get("surcharge", 0) or 0)
    except (TypeError, ValueError):
        return None

    if rate < 0 or surcharge < 0:
        return None

    cleaned = {"name": name, "rate": rate, "surcharge": surcharge}

    if "id" in entry:
        cleaned["id"] = entry["id"]

    return cleaned


def default_lectors():
    """Zwraca swieza kopie listy domyslnej."""

    return [dict(lector) for lector in DEFAULT_LECTORS]


def _load_clean():
    items = database_controller.load_database(DB_NAME)

    return [
        cleaned
        for cleaned in (_clean_entry(item) for item in items)
        if cleaned is not None
    ]


def load_lectors():
    """Wczytuje liste lektorow z bazy; przy pustej bazie zasiewa domyslna."""

    cleaned = _load_clean()

    if cleaned:
        return cleaned

    for entry in default_lectors():
        database_controller.item_add(entry, DB_NAME)

    return _load_clean()


def add_lector(entry):
    """Dodaje lektora do bazy. Zwraca zapisany slownik (z polem "id")."""

    cleaned = _clean_entry(entry)
    lector_id = database_controller.item_add(cleaned, DB_NAME)
    cleaned["id"] = lector_id

    return cleaned


def update_lector(lector_id, entry):
    """Nadpisuje dane lektora o danym id."""

    cleaned = _clean_entry(entry)
    cleaned["id"] = lector_id

    database_controller.save_database(DB_NAME, [cleaned])


def remove_lector(lector_id):
    """Usuwa lektora o danym id (soft-delete, tak jak reszta bazy)."""

    database_controller.item_remove(lector_id, DB_NAME)
