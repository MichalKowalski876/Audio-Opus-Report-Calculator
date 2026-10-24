import pytest
from unittest.mock import patch

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from GUI.Widgets.CrudList.List import List


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def clients():
    # Nazwy w kolejności alfabetycznej - lista sortuje wpisy po nazwie,
    # więc dzięki temu indeks w drzewie odpowiada indeksowi w fixture.
    return [
        {
            "id": 1,
            "name": "Klient A",
            "email": "first@test.com",
            "products": [],
        },
        {
            "id": 2,
            "name": "Klient B",
            "email": "second@test.com",
            "products": [18],
        },
    ]


@pytest.fixture
def widget(clients):
    with patch(
        "GUI.Widgets.CrudList.List.database_controller.load_database",
        return_value=clients,
    ):
        dlg = List("clients")
        yield dlg
        dlg.close()


def _count(widget):
    return widget.list.topLevelItemCount()


def _row(widget, index):
    return widget.list.topLevelItem(index)


def _text(widget, index):
    return _row(widget, index).text(0)


def test_initialization(widget):
    assert widget.database_name == "clients"
    assert widget.item_id is None
    assert widget.label.text() == "Clients"
    assert _count(widget) == 2


def test_items_are_loaded(widget):
    assert _text(widget, 0) == "Klient A"
    assert _text(widget, 1) == "Klient B"


def test_item_contains_data_in_user_role(widget, clients):
    data = _row(widget, 0).data(0, QtCore.Qt.ItemDataRole.UserRole)

    assert data == clients[0]


def test_item_clicked(widget, clients):
    selected = []

    widget.selected.connect(selected.append)

    widget.on_item_clicked(_row(widget, 0))

    assert widget.item_id == 1
    assert selected == [clients[0]]


def test_second_item_clicked(widget, clients):
    selected = []

    widget.selected.connect(selected.append)

    widget.on_item_clicked(_row(widget, 1))

    assert widget.item_id == 2
    assert selected == [clients[1]]


def test_refresh_list(widget):
    new_clients = [
        {
            "id": 3,
            "name": "Nowy klient",
            "email": "new@test.com",
            "products": [],
        }
    ]

    with patch(
        "GUI.Widgets.CrudList.List.database_controller.load_database",
        return_value=new_clients,
    ):
        widget.refresh_list()

    assert _count(widget) == 1
    assert _text(widget, 0) == "Nowy klient"


def test_empty_list():
    with patch(
        "GUI.Widgets.CrudList.List.database_controller.load_database",
        return_value=[],
    ):
        widget = List("clients")

    assert widget.list.topLevelItemCount() == 0
    assert widget.data == []

    widget.close()
