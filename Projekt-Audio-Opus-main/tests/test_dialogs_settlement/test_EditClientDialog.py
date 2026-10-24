from unittest.mock import patch

import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Dialogs.EditClientDialog import EditClientDialog


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def client():
    return {
        "name": "Nowy klient",
        "email": "",
        "products": [],
        "id": 6,
    }


@pytest.fixture
def books():
    return [
        {"id": 18, "title": "Komu są potrzebne różowe trampki", "author": ""},
        {"id": 19, "title": "Druga książka", "author": "Jan Kowalski"},
    ]


@pytest.fixture
def db(client, books):
    """Zwraca świeże kopie tabel 'clients' / 'products' przy każdym load."""
    other_clients = []

    state = {"clients": [client] + other_clients, "products": books}

    def fake_load(name):
        return [dict(row) for row in state.get(name, [])]

    return state, fake_load


@pytest.fixture
def dialog(client, db):
    _, fake_load = db
    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ):
        dlg = EditClientDialog(client, lambda: None)
        yield dlg
        dlg.close()


def _item_by_book_id(dialog, book_id):
    for index in range(dialog.books_list.count()):
        item = dialog.books_list.item(index)
        if item.data(QtCore.Qt.ItemDataRole.UserRole) == book_id:
            return item
    return None


# ==========================================================

def test_initialization(dialog):
    assert dialog.windowTitle() == "Edytuj klienta"
    assert dialog.name_edit.text() == "Nowy klient"
    assert dialog.email_edit.text() == ""


def test_all_books_listed_with_checkboxes(dialog):
    # Lista pokazuje wszystkie książki (przypisane i nie), z checkboxami.
    assert dialog.books_list.count() == 2
    for index in range(dialog.books_list.count()):
        item = dialog.books_list.item(index)
        assert item.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable


def test_assigned_book_is_checked(dialog, client):
    client["products"] = [18]
    dialog.load_assigned_books()

    item = _item_by_book_id(dialog, 18)
    assert item.text() == "Komu są potrzebne różowe trampki"
    assert item.checkState() == QtCore.Qt.CheckState.Checked

    assert (
        _item_by_book_id(dialog, 19).checkState()
        == QtCore.Qt.CheckState.Unchecked
    )


def test_book_with_author_in_label(dialog, client):
    client["products"] = [19]
    dialog.load_assigned_books()

    assert _item_by_book_id(dialog, 19).text() == "Druga książka — Jan Kowalski"


def test_nothing_checked_when_no_assignment(dialog):
    assert dialog.books_list.count() == 2
    for index in range(dialog.books_list.count()):
        assert (
            dialog.books_list.item(index).checkState()
            == QtCore.Qt.CheckState.Unchecked
        )


def test_placeholder_when_no_products(client):
    def fake_load(name):
        return [dict(client)] if name == "clients" else []

    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ):
        dlg = EditClientDialog(client, lambda: None)

    assert dlg.books_list.count() == 1
    assert dlg.books_list.item(0).text() == "Brak dostępnych książek."
    dlg.close()


def test_save_writes_clients_and_products(dialog, client, db):
    state, fake_load = db

    dialog.name_edit.setText("Jan Kowalski")
    dialog.email_edit.setText("jan@test.com")

    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ), patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.save_database"
    ) as mock_save, patch.object(
        dialog, "refresh_callback"
    ) as mock_refresh, patch.object(dialog, "accept") as mock_accept:

        dialog.save()

    assert client["name"] == "Jan Kowalski"
    assert client["email"] == "jan@test.com"
    assert client["products"] == []

    saved_tables = [call.args[0] for call in mock_save.call_args_list]
    assert saved_tables == ["clients", "products"]

    mock_refresh.assert_called_once()
    mock_accept.assert_called_once()


def test_save_keeps_checked_book(dialog, client, db):
    _, fake_load = db
    client["products"] = [18]
    dialog.load_assigned_books()

    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ), patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.save_database"
    ):
        dialog.save()

    assert client["products"] == [18]


def test_save_drops_unchecked_book(dialog, client, db):
    _, fake_load = db
    client["products"] = [18]
    dialog.load_assigned_books()

    _item_by_book_id(dialog, 18).setCheckState(QtCore.Qt.CheckState.Unchecked)

    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ), patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.save_database"
    ):
        dialog.save()

    assert client["products"] == []


def test_save_updates_only_matching_client(dialog, client):
    other = {"id": 5, "name": "Inny klient", "email": "other@test.com", "products": []}
    clients = [other, client]

    def fake_load(name):
        if name == "clients":
            return clients
        return []

    dialog.name_edit.setText("Zmieniony klient")
    dialog.email_edit.setText("changed@test.com")

    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ), patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.save_database"
    ) as mock_save:
        dialog.save()

    saved_clients = mock_save.call_args_list[0].args[1]
    by_id = {c["id"]: c for c in saved_clients}
    assert by_id[5]["name"] == "Inny klient"
    assert by_id[6]["name"] == "Zmieniony klient"
    assert by_id[6]["email"] == "changed@test.com"


# Tryb dodawania nowego klienta (is_new=True)

@pytest.fixture
def new_client():
    return {"name": "", "email": "", "products": [], "created_at": "2026-09-21T10:00:00"}


@pytest.fixture
def new_dialog(new_client, db):
    _, fake_load = db
    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ):
        dlg = EditClientDialog(new_client, lambda: None, is_new=True)
        yield dlg
        dlg.close()


def test_add_mode_title(new_dialog):
    assert new_dialog.windowTitle() == "Dodawanie klienta"
    assert new_dialog.name_edit.text() == ""


def test_edit_mode_title_unchanged(dialog):
    assert dialog.windowTitle() == "Edytuj klienta"


def test_add_mode_lists_books_without_id(new_dialog):
    assert new_dialog.books_list.count() == 2


def test_add_mode_empty_name_creates_nothing(new_dialog):
    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.QtWidgets.QMessageBox.warning"
    ) as mock_warning, patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.item_add"
    ) as mock_add, patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.save_database"
    ) as mock_save:
        new_dialog.save()

    mock_warning.assert_called_once()
    mock_add.assert_not_called()
    mock_save.assert_not_called()


def test_add_mode_reject_creates_nothing(new_dialog):
    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.item_add"
    ) as mock_add, patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.save_database"
    ) as mock_save:
        new_dialog.reject()

    mock_add.assert_not_called()
    mock_save.assert_not_called()


def test_add_mode_save_adds_client_and_assigns_books(new_dialog, new_client):
    clients = []

    def fake_load(name):
        if name == "clients":
            return [dict(row) for row in clients]
        return [
            {"id": 18, "title": "Komu są potrzebne różowe trampki", "author": ""},
        ]

    def fake_item_add(item, db_name):
        assert db_name == "clients"
        assert "id" not in item
        clients.append({**item, "id": 7})
        return 7

    new_dialog.name_edit.setText("Wydawnictwo Test")
    new_dialog.email_edit.setText("test@test.com")
    _item_by_book_id(new_dialog, 18).setCheckState(QtCore.Qt.CheckState.Checked)

    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ), patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.item_add",
        side_effect=fake_item_add,
    ) as mock_add, patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.save_database"
    ) as mock_save, patch.object(
        new_dialog, "refresh_callback"
    ) as mock_refresh, patch.object(new_dialog, "accept") as mock_accept:
        new_dialog.save()

    mock_add.assert_called_once()
    assert new_client["id"] == 7
    assert new_client["name"] == "Wydawnictwo Test"
    assert new_client["products"] == [18]

    saved_clients = mock_save.call_args_list[0].args[1]
    assert [c["id"] for c in saved_clients] == [7]
    assert saved_clients[0]["products"] == [18]

    saved_products = mock_save.call_args_list[1].args[1]
    assert saved_products[0]["publisher"] == "Wydawnictwo Test"

    mock_refresh.assert_called_once()
    mock_accept.assert_called_once()


def test_add_mode_retry_after_failure_does_not_add_twice(new_dialog):
    clients = []

    def fake_load(name):
        return [dict(row) for row in clients] if name == "clients" else []

    def fake_item_add(item, db_name):
        clients.append({**item, "id": 7})
        return 7

    new_dialog.name_edit.setText("Wydawnictwo Test")

    with patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.load_database",
        side_effect=fake_load,
    ), patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.item_add",
        side_effect=fake_item_add,
    ) as mock_add, patch(
        "GUI.Widgets.Dialogs.EditClientDialog.database_controller.save_database",
        side_effect=[RuntimeError("boom"), None, None],
    ):
        with pytest.raises(RuntimeError):
            new_dialog.save()
        new_dialog.save()

    mock_add.assert_called_once()
