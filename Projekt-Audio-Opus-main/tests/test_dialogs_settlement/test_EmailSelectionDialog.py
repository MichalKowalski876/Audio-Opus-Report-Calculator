import json
from unittest.mock import mock_open, patch

import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Dialogs.EmailSelectionDialog import EmailSelectionDialog


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
            "id": 1,
            "name": "Jan Kowalski",
            "email": "jan@test.com",
        },
        {
            "id": 2,
            "name": "Anna Nowak",
            "email": "anna@test.com",
        },
        {
            "id": 3,
            "name": "Duplikat",
            "email": "jan@test.com",
        },
        {
            "id": 4,
            "name": "Bez maila",
            "email": "",
        },
    ]


@pytest.fixture
def custom_emails():
    return [
        "custom@test.com",
        "jan@test.com",
    ]


@pytest.fixture
def dialog(clients, custom_emails):
    with patch(
        "GUI.Widgets.Dialogs.EmailSelectionDialog.database_controller.load_database",
        return_value=clients,
    ), patch(
        "GUI.Widgets.Dialogs.EmailSelectionDialog.os.path.exists",
        return_value=True,
    ), patch(
        "builtins.open",
        mock_open(read_data=json.dumps(custom_emails)),
    ):
        dlg = EmailSelectionDialog()

        yield dlg

        dlg.close()


def test_initialization(dialog):
    assert dialog.windowTitle() == "Wybór odbiorców raportu"
    assert dialog.minimumWidth() >= 450
    assert dialog.minimumHeight() >= 450
    assert dialog.list_widget.count() == 3
    assert dialog.selected_emails == []


def test_load_emails(dialog):
    assert dialog.list_widget.count() == 3

    assert (
        dialog.list_widget.item(0).text()
        == "jan@test.com  (Jan Kowalski)"
    )

    assert (
        dialog.list_widget.item(1).text()
        == "anna@test.com  (Anna Nowak)"
    )

    assert (
        dialog.list_widget.item(2).text()
        == "custom@test.com"
    )


def test_items_contain_email_in_user_role(dialog):
    assert (
        dialog.list_widget.item(0).data(
            QtCore.Qt.ItemDataRole.UserRole
        )
        == "jan@test.com"
    )

    assert (
        dialog.list_widget.item(2).data(
            QtCore.Qt.ItemDataRole.UserRole
        )
        == "custom@test.com"
    )


def test_add_item(dialog):
    dialog._add_item(
        "test@test.com  (Test)",
        "test@test.com",
    )

    item = dialog.list_widget.item(
        dialog.list_widget.count() - 1
    )

    assert item.text() == "test@test.com  (Test)"
    assert item.data(
        QtCore.Qt.ItemDataRole.UserRole
    ) == "test@test.com"


def test_on_accept_selected_email(dialog):
    dialog.list_widget.item(0).setCheckState(
        QtCore.Qt.CheckState.Checked
    )

    with patch.object(
        dialog,
        "accept",
    ) as mock_accept:
        dialog.on_accept()

    assert dialog.selected_emails == ["jan@test.com"]
    mock_accept.assert_called_once()


def test_on_accept_manual_emails(dialog):
    dialog.manual_input.setPlainText(
        "one@test.com, two@test.com\nthree@test.com"
    )

    with patch.object(
        dialog,
        "accept",
    ) as mock_accept:
        dialog.on_accept()

    assert dialog.selected_emails == [
        "one@test.com",
        "two@test.com",
        "three@test.com",
    ]

    mock_accept.assert_called_once()


def test_on_accept_removes_duplicate_manual_email(dialog):
    dialog.list_widget.item(0).setCheckState(
        QtCore.Qt.CheckState.Checked
    )

    dialog.manual_input.setPlainText(
        "jan@test.com, new@test.com"
    )

    with patch.object(
        dialog,
        "accept",
    ) as mock_accept:
        dialog.on_accept()

    assert dialog.selected_emails == [
        "jan@test.com",
        "new@test.com",
    ]

    mock_accept.assert_called_once()


def test_on_accept_without_emails(dialog):
    with patch(
        "GUI.Widgets.Dialogs.EmailSelectionDialog.QtWidgets.QMessageBox.warning"
    ) as mock_warning, patch.object(
        dialog,
        "accept",
    ) as mock_accept:
        dialog.on_accept()

    assert dialog.selected_emails == []

    mock_warning.assert_called_once()
    mock_accept.assert_not_called()


def test_load_emails_without_custom_file(clients):
    with patch(
        "GUI.Widgets.Dialogs.EmailSelectionDialog.database_controller.load_database",
        return_value=clients,
    ), patch(
        "GUI.Widgets.Dialogs.EmailSelectionDialog.os.path.exists",
        return_value=False,
    ):
        dialog = EmailSelectionDialog()

    try:
        assert dialog.list_widget.count() == 2

        assert (
            dialog.list_widget.item(0).text()
            == "jan@test.com  (Jan Kowalski)"
        )

        assert (
            dialog.list_widget.item(1).text()
            == "anna@test.com  (Anna Nowak)"
        )
    finally:
        dialog.close()
