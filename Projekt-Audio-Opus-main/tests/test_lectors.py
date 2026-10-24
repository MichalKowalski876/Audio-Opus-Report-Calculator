import json

import pytest

from core import database_controller
from core import lectors


@pytest.fixture(autouse=True)
def temp_db_env(tmp_path, monkeypatch):
    monkeypatch.setattr(database_controller, "FOLDER", str(tmp_path))


def _names(entries):
    return [entry["name"] for entry in entries]


def test_load_seeds_defaults_when_database_is_empty():
    result = lectors.load_lectors()

    assert _names(result) == _names(lectors.DEFAULT_LECTORS)
    assert all("id" in entry for entry in result)


def test_add_lector_persists_and_is_returned_with_id():
    saved = lectors.add_lector(
        {"name": "Nowy Lektor", "rate": 500.0, "surcharge": 60.0}
    )

    assert saved["id"] is not None

    reloaded = {entry["id"]: entry for entry in lectors.load_lectors()}
    assert reloaded[saved["id"]] == saved


def test_update_lector_overwrites_fields_in_place():
    saved = lectors.add_lector(
        {"name": "Do zmiany", "rate": 100.0, "surcharge": 0.0}
    )

    lectors.update_lector(
        saved["id"], {"name": "Po zmianie", "rate": 200.0, "surcharge": 10.0}
    )

    reloaded = {entry["id"]: entry for entry in lectors.load_lectors()}
    assert reloaded[saved["id"]] == {
        "id": saved["id"],
        "name": "Po zmianie",
        "rate": 200.0,
        "surcharge": 10.0,
    }


def test_remove_lector_excludes_it_from_load():
    saved = lectors.add_lector(
        {"name": "Do usunięcia", "rate": 100.0, "surcharge": 0.0}
    )

    lectors.remove_lector(saved["id"])

    assert saved["id"] not in {entry["id"] for entry in lectors.load_lectors()}


def test_load_skips_broken_entries():
    database_controller.item_add({"rate": 100}, lectors.DB_NAME)
    database_controller.item_add(
        {"name": "Ujemny", "rate": -5, "surcharge": 0}, lectors.DB_NAME
    )
    database_controller.item_add(
        {"name": "  ", "rate": 10, "surcharge": 0}, lectors.DB_NAME
    )
    database_controller.item_add(
        {"name": "OK", "rate": 300, "surcharge": 50}, lectors.DB_NAME
    )

    assert _names(lectors.load_lectors()) == ["OK"]


def test_load_imports_existing_json_file_into_the_database(tmp_path):
    """Migracja z jsona: plik zostawiony przez starsza wersje aplikacji
    zostaje wczytany do bazy przy pierwszym odczycie."""

    json_path = tmp_path / f"{lectors.DB_NAME}.json"
    json_path.write_text(
        json.dumps([{"name": "Z Pliku", "rate": 111.0, "surcharge": 22.0}]),
        encoding="utf-8",
    )

    result = lectors.load_lectors()

    assert _names(result) == ["Z Pliku"]
    assert result[0]["rate"] == 111.0
    assert result[0]["surcharge"] == 22.0
