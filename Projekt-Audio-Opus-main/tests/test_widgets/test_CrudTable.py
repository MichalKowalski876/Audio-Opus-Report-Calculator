import pytest
from unittest.mock import patch, Mock

from PySide6 import QtWidgets

from GUI.Widgets.CrudTable.CrudTable import CrudTable


@pytest.fixture(scope="session")
def app():
    application = QtWidgets.QApplication.instance()

    if application is None:
        application = QtWidgets.QApplication([])

    return application


@pytest.fixture
def dialog(app):
    with patch(
        "GUI.Widgets.CrudTable.Table.database_controller.load_database",
        return_value=[],
    ):
        dlg = CrudTable(
            ["ID", "Tytuł", "Autor"],
            "products",
        )

        dlg.table.search = Mock()

        yield dlg

        dlg.close()
        dlg.deleteLater()


def test_initialization(dialog):
    assert dialog.table is not None
    assert dialog.add_button.text() == "+"
    assert dialog.remove_button.text() == "-"
    assert dialog.add_button.property("role") == "AddButton"
    assert dialog.remove_button.property("role") == "RemoveButton"


def test_search(dialog):
    dialog.search("książka")

    dialog.table.search.assert_called_once_with("książka")
