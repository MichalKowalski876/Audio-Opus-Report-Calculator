import pytest
from unittest.mock import MagicMock, patch
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from GUI.Tabs.ClientsTab import ClientsTab
from GUI.Widgets.CrudList.List import List


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_crud_client_list():
    class MockCrudClientList(QtWidgets.QWidget):
        def __init__(self, db_name):
            super().__init__()
            self.db_name = db_name
            self.list = MagicMock()
            self.list.selected = MagicMock()

    return MockCrudClientList


@pytest.fixture
def clients_tab(mock_crud_client_list):
    with patch("GUI.Tabs.ClientsTab.CrudClientList", mock_crud_client_list):
        tab = ClientsTab()
        yield tab


class TestClientsTab:

    def test_clients_tab_initialization(self, clients_tab):
        assert isinstance(clients_tab.layout(), QtWidgets.QVBoxLayout)
        assert clients_tab.layout().count() == 2
        assert clients_tab.list.db_name == "clients"

    def test_signal_connection(self, clients_tab):
        clients_tab.list.list.selected.connect.assert_called_once_with(
            clients_tab.on_client_selected
        )

    def test_on_client_selected(self, clients_tab):
        mock_client = {
            "id": 12,
            "name": "Jan Kowalski",
            "email": "jan@example.com"
        }

        try:
            clients_tab.on_client_selected(mock_client)
        except KeyError:
            pytest.fail("Metoda on_client_selected wyrzuciła błąd KeyError. Oczekiwano istnienia klucza 'id'.")

    def test_client_search_matches_product_titles_fuzzily(self, monkeypatch):
        clients = [{
            "id": 1,
            "name": "Acme",
            "email": "acme@example.com",
            "products": [10],
        }]
        products = [{
            "id": 10,
            "title": "Ildefons Rozrabia",
            "author": "Karolina Bast",
            "publisher": "Audio Opus",
            "isbn": "978-83-68950-01-4",
        }]

        def fake_load_database(name):
            if name == "clients":
                return clients
            if name == "products":
                return products
            return []

        monkeypatch.setattr(
            "GUI.Widgets.CrudList.List.database_controller.load_database",
            fake_load_database,
        )

        client_list = List("clients")
        client_list.search("ildfns", use_fuzzy=True)

        assert client_list.list.topLevelItem(0).isHidden() is False