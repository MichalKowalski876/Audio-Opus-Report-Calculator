import json
from unittest.mock import mock_open, patch

import pytest
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Dialogs.CustomEmailsDialog import (
    CustomEmailsDialog,
    CUSTOM_EMAILS_FILE,
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    yield app


@pytest.fixture
def dialog():
    """
    Tworzy dialog bez wczytywania prawdziwego pliku
    CUSTOM_EMAILS_FILE.
    """
    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.os.path.exists",
        return_value=False,
    ):
        dlg = CustomEmailsDialog()

    yield dlg
    dlg.close()


def test_initialization(dialog):
    assert dialog.windowTitle() == "Zarządzaj własnymi mailami"
    assert dialog.size().width() == 400
    assert dialog.size().height() == 300
    assert isinstance(dialog.list_widget, QtWidgets.QListWidget)


def test_load_emails_file_not_exists(dialog):
    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.os.path.exists",
        return_value=False,
    ) as mock_exists:
        dialog.load_emails()

    assert dialog.list_widget.count() == 0
    mock_exists.assert_called_once_with(CUSTOM_EMAILS_FILE)


def test_load_emails(dialog):
    email_data = [
        "a@test.com",
        "b@test.com",
    ]

    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.os.path.exists",
        return_value=True,
    ) as mock_exists:
        with patch(
            "builtins.open",
            new_callable=mock_open,
            read_data=json.dumps(email_data),
        ) as mock_file:
            dialog.load_emails()

    assert dialog.list_widget.count() == 2
    assert dialog.list_widget.item(0).text() == "a@test.com"
    assert dialog.list_widget.item(1).text() == "b@test.com"

    mock_exists.assert_called_once_with(CUSTOM_EMAILS_FILE)
    mock_file.assert_called_once()


def test_save_emails(dialog):
    dialog.list_widget.addItems(
        [
            "a@test.com",
            "b@test.com",
        ]
    )

    with patch(
        "builtins.open",
        new_callable=mock_open,
    ) as mock_file:
        with patch(
            "GUI.Widgets.Dialogs.CustomEmailsDialog.json.dump"
        ) as mock_dump:
            dialog.save_emails()

    mock_file.assert_called_once()
    mock_dump.assert_called_once()

    assert mock_dump.call_args.args[0] == [
        "a@test.com",
        "b@test.com",
    ]


def test_add_email(dialog):
    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.QtWidgets.QInputDialog.getText",
        return_value=("test@test.com", True),
    ) as mock_input:
        with patch.object(
            CustomEmailsDialog,
            "save_emails",
        ) as mock_save:
            dialog.add_email()

    assert dialog.list_widget.count() == 1
    assert dialog.list_widget.item(0).text() == "test@test.com"

    mock_input.assert_called_once()
    mock_save.assert_called_once()


def test_add_duplicate(dialog):
    dialog.list_widget.addItem("test@test.com")

    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.QtWidgets.QInputDialog.getText",
        return_value=("test@test.com", True),
    ) as mock_input:
        with patch(
            "GUI.Widgets.Dialogs.CustomEmailsDialog.QtWidgets.QMessageBox.information"
        ) as mock_info:
            with patch.object(
                CustomEmailsDialog,
                "save_emails",
            ) as mock_save:
                dialog.add_email()

    assert dialog.list_widget.count() == 1

    mock_input.assert_called_once()
    mock_info.assert_called_once()
    mock_save.assert_not_called()


def test_edit_email(dialog):
    dialog.list_widget.addItem("old@test.com")
    dialog.list_widget.setCurrentRow(0)

    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.QtWidgets.QInputDialog.getText",
        return_value=("new@test.com", True),
    ) as mock_input:
        with patch.object(
            CustomEmailsDialog,
            "save_emails",
        ) as mock_save:
            dialog.edit_email()

    assert dialog.list_widget.count() == 1
    assert dialog.list_widget.item(0).text() == "new@test.com"

    mock_input.assert_called_once()
    mock_save.assert_called_once()


def test_edit_without_selection(dialog):
    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.QtWidgets.QMessageBox.warning"
    ) as mock_warning:
        dialog.edit_email()

    mock_warning.assert_called_once()


def test_delete_email(dialog):
    dialog.list_widget.addItems(
        [
            "a@test.com",
            "b@test.com",
        ]
    )
    dialog.list_widget.setCurrentRow(0)

    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.confirm_yes_no",
        return_value=True,
    ) as mock_question:
        with patch.object(
            CustomEmailsDialog,
            "save_emails",
        ) as mock_save:
            dialog.delete_email()

    assert dialog.list_widget.count() == 1
    assert dialog.list_widget.item(0).text() == "b@test.com"

    mock_question.assert_called_once()
    mock_save.assert_called_once()


def test_delete_cancelled(dialog):
    dialog.list_widget.addItem("a@test.com")
    dialog.list_widget.setCurrentRow(0)

    with patch(
        "GUI.Widgets.Dialogs.CustomEmailsDialog.confirm_yes_no",
        return_value=False,
    ) as mock_question:
        with patch.object(
            CustomEmailsDialog,
            "save_emails",
        ) as mock_save:
            dialog.delete_email()

    assert dialog.list_widget.count() == 1
    assert dialog.list_widget.item(0).text() == "a@test.com"

    mock_question.assert_called_once()
    mock_save.assert_not_called()
