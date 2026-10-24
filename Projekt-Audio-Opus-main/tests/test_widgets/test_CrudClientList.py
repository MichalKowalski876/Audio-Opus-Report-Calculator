import pytest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

from GUI.Widgets.CrudList.CrudClientList import CrudClientList
from GUI.Widgets.Items.BookItem import BookItem


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def clients():
    return [
        {
            "id": 6,
            "name": "Nowy klient",
            "email": "client@test.com",
            "products": [18],
        },
        {
            "id": 7,
            "name": "Drugi klient",
            "email": "second@test.com",
            "products": [],
        },
    ]


@pytest.fixture
def products():
    return [
        {
            "id": 18,
            "title": "Pierwsza książka",
            "author": "Jan Kowalski",
            "publisher": "Audio Opus",
            "cut": 10,
            "isbn": "123456789",
            "settlement type": "instant",
            "threshold": 0,
        },
        {
            "id": 19,
            "title": "Druga książka",
            "author": "",
            "publisher": "",
            "cut": 20,
            "isbn": "",
            "settlement type": "instant",
            "threshold": 5,
        },
    ]


@pytest.fixture
def dialog(clients, products):
    with patch(
        "GUI.Widgets.CrudList.CrudClientList.database_controller.load_database"
    ) as mock_load:
        # Zwracamy świeże kopie przy każdym wywołaniu - tak jak prawdziwe
        # load_database (czyta JSON od nowa). List sortuje listę w miejscu,
        # więc bez kopii fixture 'clients' zostałby przestawiony.
        mock_load.side_effect = lambda name: [
            dict(row) for row in (clients if name == "clients" else products)
        ]

        dlg = CrudClientList("clients")
        yield dlg
        dlg.close()


def _book_items(dialog):
    layout = dialog.products_container_layout
    return [
        layout.itemAt(i).widget()
        for i in range(layout.count())
        if isinstance(layout.itemAt(i).widget(), BookItem)
    ]


def _placeholder_text(dialog):
    layout = dialog.products_container_layout
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if isinstance(widget, QLabel):
            return widget.text()
    return None


def test_initialization(dialog):
    assert dialog.list is not None
    assert dialog.products_container_layout is not None
    assert dialog.name_label.text() == "-"


def test_clients_are_loaded(dialog):
    assert dialog.list.list.topLevelItemCount() == 2


def test_on_selected_item(dialog, clients):
    dialog.on_selected_item(clients[0])

    assert dialog.current_client == clients[0]
    assert dialog.name_label.text() == "Nowy klient"
    assert dialog.email_label.text() == "client@test.com"
    assert dialog.books_count_label.text() == "1"
    assert not dialog.edit_button.isHidden()


def test_on_selected_item_without_email(dialog):
    dialog.on_selected_item(
        {"id": 7, "name": "Drugi klient", "email": "", "products": []}
    )

    assert dialog.email_label.text() == "-"


def test_refresh_products(dialog, clients):
    dialog.refresh_products(clients[0])

    books = _book_items(dialog)
    assert len(books) == 1
    assert books[0].product["title"] == "Pierwsza książka"


def test_refresh_multiple_products(dialog):
    dialog.refresh_products(
        {"id": 6, "name": "Nowy klient", "email": "", "products": [18, 19]}
    )

    books = _book_items(dialog)
    # refresh_products sortuje książki po tytule (małe litery).
    assert [book.product["title"] for book in books] == [
        "Druga książka",
        "Pierwsza książka",
    ]


def test_refresh_products_empty(dialog):
    dialog.refresh_products(
        {"id": 6, "name": "Nowy klient", "email": "", "products": []}
    )

    assert _book_items(dialog) == []
    assert _placeholder_text(dialog) == "Brak przypisanych książek"


def test_refresh_products_missing_product(dialog):
    dialog.refresh_products(
        {"id": 6, "name": "Nowy klient", "email": "", "products": [999]}
    )

    assert _book_items(dialog) == []
    assert _placeholder_text(dialog) == "Brak przypisanych książek"


def test_refresh_products_carries_full_record(dialog, products):
    dialog.refresh_products(
        {"id": 6, "name": "Nowy klient", "email": "", "products": [18]}
    )

    book = _book_items(dialog)[0]
    assert book.product == products[0]
