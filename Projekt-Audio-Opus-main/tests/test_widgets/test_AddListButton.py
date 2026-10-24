from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Buttons.List import AddListButton as add_button_module
from GUI.Widgets.Buttons.List.AddListButton import AddListButton


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_add_client_opens_dialog_in_add_mode_without_writing_to_db():
    refresh = []
    button = AddListButton("clients", lambda: refresh.append(1))

    with patch.object(add_button_module, "EditClientDialog") as mock_dialog, patch.object(
        add_button_module.database_controller, "item_add"
    ) as mock_add:
        button.click()

    mock_dialog.assert_called_once()
    args, kwargs = mock_dialog.call_args
    new_client = args[0]
    assert new_client["name"] == ""
    assert new_client["products"] == []
    assert args[1] == button.refresh_callback
    assert kwargs["is_new"] is True
    mock_dialog.return_value.exec.assert_called_once()

    # Klient jest tworzony dopiero przez zapis w oknie, nie przez sam przycisk.
    mock_add.assert_not_called()


def test_add_other_item_still_adds_directly():
    refresh = []
    button = AddListButton("other", lambda: refresh.append(1))

    with patch.object(add_button_module, "EditClientDialog") as mock_dialog, patch.object(
        add_button_module.database_controller, "item_add"
    ) as mock_add:
        button.click()

    mock_dialog.assert_not_called()
    mock_add.assert_called_once()
    assert refresh == [1]
