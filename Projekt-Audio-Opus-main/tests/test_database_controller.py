import os
import json
import sqlite3
import pytest

from core import database_controller


@pytest.fixture
def temp_db_env(tmp_path, monkeypatch):
    """
    Tworzy tymczasowy folder na bazy danych i podmienia
    zmienna FOLDER w module database_controller.
    Zwraca ścieżkę do tymczasowego folderu.
    """
    temp_folder = str(tmp_path / "TestDatabases") + "/"
    os.makedirs(temp_folder, exist_ok=True)

    monkeypatch.setattr(database_controller, "FOLDER", temp_folder)

    return temp_folder


@pytest.fixture
def seed_database(temp_db_env):
    """
    Funkcja pomocnicza do szybkiego zapelniania testowej bazy danych.
    """

    def _seed(db_name, data):
        file_path = os.path.join(temp_db_env, f"{db_name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    return _seed


class TestDatabaseController:

    def test_save_and_load_database(self, temp_db_env):
        db_name = "test_clients"
        data_to_save = [{"id": 1, "name": "Firma A"}, {"id": 2, "name": "Firma B"}]

        database_controller.save_database(db_name, data_to_save)

        file_path = os.path.join(temp_db_env, f"{db_name}.json")
        assert os.path.exists(file_path)

        loaded_data = database_controller.load_database(db_name)
        assert loaded_data == data_to_save
        assert len(loaded_data) == 2

    def test_item_add_to_empty_db(self, seed_database):
        db_name = "empty_db"
        seed_database(db_name, [])

        new_item = {"name": "Nowy Klient", "cut": 15}
        database_controller.item_add(new_item, db_name)

        data = database_controller.load_database(db_name)
        assert len(data) == 1
        assert data[0]["id"] == 1  # Powinien dostac ID = 1
        assert data[0]["name"] == "Nowy Klient"

    def test_item_add_to_existing_db(self, seed_database):
        db_name = "existing_db"
        seed_database(db_name, [
            {"id": 2, "name": "A"},
            {"id": 5, "name": "B"}
        ])

        new_item = {"name": "C"}
        database_controller.item_add(new_item, db_name)

        data = database_controller.load_database(db_name)
        assert len(data) == 3
        assert data[-1]["id"] == 6
        assert data[-1]["name"] == "C"

    def test_item_remove_existing(self, seed_database):
        db_name = "remove_db"
        seed_database(db_name, [
            {"id": 1, "name": "Do zachowania"},
            {"id": 2, "name": "Do usuniecia"}
        ])

        database_controller.item_remove(2, db_name)

        data = database_controller.load_database(db_name)
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["name"] == "Do zachowania"

    def test_item_remove_non_existent(self, seed_database):
        db_name = "remove_missing_db"
        initial_data = [{"id": 1, "name": "Test"}]
        seed_database(db_name, initial_data)

        database_controller.item_remove(99, db_name)

        data = database_controller.load_database(db_name)
        assert data == initial_data

    def test_item_modify_existing(self, seed_database):
        db_name = "modify_db"
        seed_database(db_name, [
            {"id": 1, "name": "Stara Nazwa", "cut": 10},
            {"id": 2, "name": "Inny", "cut": 20}
        ])

        database_controller.item_modify(1, "name", "Nowa Nazwa", db_name)

        data = database_controller.load_database(db_name)
        assert data[0]["name"] == "Nowa Nazwa"
        assert data[0]["cut"] == 10  # Inne pola powinny zostac nienaruszone
        assert data[1]["name"] == "Inny"  # Inne obiekty bez zmian

    def test_item_modify_non_existent(self, seed_database):
        db_name = "modify_missing_db"
        initial_data = [{"id": 1, "name": "Test"}]
        seed_database(db_name, initial_data)

        database_controller.item_modify(99, "name", "Zmiana", db_name)

        data = database_controller.load_database(db_name)
        assert data == initial_data

    def test_item_get_existing(self, seed_database):
        db_name = "get_db"
        seed_database(db_name, [
            {"id": 1, "name": "Jeden"},
            {"id": 2, "name": "Dwa"}
        ])

        item = database_controller.item_get(2, db_name)

        assert item is not None
        assert item["id"] == 2
        assert item["name"] == "Dwa"

    def test_item_get_non_existent(self, seed_database):
        db_name = "get_missing_db"
        seed_database(db_name, [{"id": 1, "name": "Jeden"}])

        item = database_controller.item_get(99, db_name)

        assert item is None

    def test_item_remove_is_recoverable_via_trash(self, seed_database):
        db_name = "trash_db"
        seed_database(db_name, [
            {"id": 1, "name": "Do zachowania"},
            {"id": 2, "name": "Do usuniecia"},
        ])

        database_controller.item_remove(2, db_name)

        # Zniknal z normalnego widoku...
        assert [item["id"] for item in database_controller.load_database(db_name)] == [1]

        # ...ale wciaz istnieje w bazie i w koszu.
        with_deleted = database_controller.load_database(db_name, include_deleted=True)
        assert [item["id"] for item in with_deleted] == [1, 2]

        trash = database_controller.list_trash(db_name)
        assert len(trash) == 1
        assert trash[0]["id"] == 2
        assert trash[0]["name"] == "Do usuniecia"
        assert trash[0]["_deleted_at"]

    def test_item_restore_brings_item_back(self, seed_database):
        db_name = "restore_db"
        seed_database(db_name, [{"id": 1, "name": "Klient"}])

        database_controller.item_remove(1, db_name)
        assert database_controller.load_database(db_name) == []

        database_controller.item_restore(1, db_name)

        data = database_controller.load_database(db_name)
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["name"] == "Klient"
        assert "_deleted" not in data[0]
        assert "_deleted_at" not in data[0]

    def test_item_purge_deletes_permanently(self, seed_database):
        db_name = "purge_db"
        seed_database(db_name, [{"id": 1, "name": "Klient"}])

        database_controller.item_remove(1, db_name)
        database_controller.item_purge(1, db_name)

        assert database_controller.list_trash(db_name) == []
        assert database_controller.load_database(db_name, include_deleted=True) == []

    def test_save_database_does_not_wipe_trashed_items(self, seed_database):
        db_name = "save_upsert_db"
        seed_database(db_name, [
            {"id": 1, "name": "Aktywny"},
            {"id": 2, "name": "W koszu"},
        ])

        database_controller.item_remove(2, db_name)

        # Typowy wzorzec "wczytaj -> zmodyfikuj -> zapisz" na aktywnych danych
        # (tak jak robi to EditClientDialog) nie moze skasowac kosza.
        active = database_controller.load_database(db_name)
        active[0]["name"] = "Aktywny (zmieniony)"
        database_controller.save_database(db_name, active)

        trash = database_controller.list_trash(db_name)
        assert len(trash) == 1
        assert trash[0]["id"] == 2

        data = database_controller.load_database(db_name)
        assert data[0]["name"] == "Aktywny (zmieniony)"

    def test_clients_and_products_use_relational_sqlite_tables(
        self,
        temp_db_env,
    ):
        database_controller.save_database(
            "clients",
            [{"id": 1, "name": "Klient A", "email": "a@example.com", "products": []}],
        )
        database_controller.save_database(
            "products",
            [
                {
                    "id": 1,
                    "title": "Książka",
                    "author": "Autor",
                    "publisher": "Klient A",
                    "isbn": "978-1",
                    "cut": 30,
                    "settlement type": "instant",
                    "threshold": 0,
                    "streaming": ["Legimi", "Storytel"],
                }
            ],
        )

        clients = database_controller.load_database("clients")
        products = database_controller.load_database("products")

        assert clients[0]["products"] == [1]
        assert products[0]["publisher"] == "Klient A"
        assert products[0]["streaming"] == ["Legimi", "Storytel"]
        assert not os.path.exists(os.path.join(temp_db_env, "clients.json"))
        assert not os.path.exists(os.path.join(temp_db_env, "products.json"))

        with sqlite3.connect(database_controller._database_path()) as connection:
            client_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(clients)")
            }
            product_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(products)")
            }
            foreign_keys = connection.execute(
                "PRAGMA foreign_key_list(products)"
            ).fetchall()

        assert "data" not in client_columns
        assert {"name", "email", "deleted_at"} <= client_columns
        assert "data" not in product_columns
        assert {"title", "isbn", "client_id", "deleted_at"} <= product_columns
        assert any(row[2] == "clients" and row[3] == "client_id" for row in foreign_keys)

    def test_saving_client_assignments_updates_product_relation(
        self,
        temp_db_env,
    ):
        database_controller.save_database(
            "clients",
            [
                {"id": 1, "name": "Klient A", "email": "", "products": []},
                {"id": 2, "name": "Klient B", "email": "", "products": []},
            ],
        )
        database_controller.save_database(
            "products",
            [{"id": 1, "title": "Książka", "publisher": "Klient A"}],
        )

        clients = database_controller.load_database("clients")
        clients[0]["products"] = []
        clients[1]["products"] = [1]
        database_controller.save_database("clients", clients)

        product = database_controller.item_get(1, "products")
        assert product["publisher"] == "Klient B"

    def test_migrates_legacy_json_payload_tables_without_json_files(
        self,
        temp_db_env,
    ):
        database_path = database_controller._database_path()
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "CREATE TABLE clients (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE products (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO clients (id, data) VALUES (?, ?)",
                (
                    1,
                    json.dumps(
                        {"name": "Klient A", "email": "", "products": [4]},
                        ensure_ascii=False,
                    ),
                ),
            )
            connection.execute(
                "INSERT INTO products (id, data) VALUES (?, ?)",
                (
                    4,
                    json.dumps(
                        {
                            "title": "Książka",
                            "publisher": "Klient A",
                            "streaming": ["Legimi"],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        assert database_controller.load_database("clients")[0]["products"] == [4]
        product = database_controller.load_database("products")[0]
        assert product["publisher"] == "Klient A"
        assert product["streaming"] == ["Legimi"]

        with sqlite3.connect(database_path) as connection:
            assert "data" not in {
                row[1] for row in connection.execute("PRAGMA table_info(clients)")
            }
            assert "data" not in {
                row[1] for row in connection.execute("PRAGMA table_info(products)")
            }
