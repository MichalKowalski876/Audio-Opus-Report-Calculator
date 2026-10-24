import json
from unittest.mock import mock_open, patch

import pytest
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Dialogs.EmailHistoryDialog import (
    EmailHistoryDialog,
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    yield app


@pytest.fixture
def history():
    return [
        {
            "timestamp": "2026-08-10 10:00",
            "receiver": "a@test.com",
            "file": "C:/files/book1.pdf",
            "success": True,
        },
        {
            "timestamp": "2026-08-10 11:00",
            "receiver": "b@test.com",
            "file": "C:/files/book2.pdf",
            "success": False,
            "error": "Błąd wysyłki",
        },
    ]


@pytest.fixture
def dialog(history):
    with patch(
            "GUI.Widgets.Dialogs.EmailHistoryDialog.os.path.exists",
            return_value=True,
    ), patch(
        "builtins.open",
        mock_open(read_data=json.dumps(history)),
    ):
        dlg = EmailHistoryDialog()
        yield dlg
        dlg.close()


def test_initialization(dialog):
    assert dialog.windowTitle() == "Historia wysyłki e-maili"
    assert dialog.size().width() == 700
    assert dialog.size().height() == 450
    assert dialog.table.columnCount() == 4
    assert dialog.table.horizontalHeaderItem(0).text() == "Data"
    assert dialog.table.horizontalHeaderItem(1).text() == "Odbiorca"
    assert dialog.table.horizontalHeaderItem(2).text() == "Plik"
    assert dialog.table.horizontalHeaderItem(3).text() == "Status"


def test_load_history(dialog, history):
    assert dialog.all_history == history
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 1).text() == "b@test.com"
    assert dialog.table.item(1, 1).text() == "a@test.com"


def test_load_history_file_not_exists():
    with patch(
            "GUI.Widgets.Dialogs.EmailHistoryDialog.os.path.exists",
            return_value=False,
    ):
        dialog = EmailHistoryDialog()

    try:
        assert dialog.all_history == []
        assert dialog.table.rowCount() == 0
        assert dialog.result_count_label.text() == "Liczba wpisów: 0"
    finally:
        dialog.close()


def test_search_filter(dialog):
    dialog.search_input.setText("book1")

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 1).text() == "a@test.com"


def test_receiver_filter(dialog):
    dialog.search_input.setText("b@test.com")

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 1).text() == "b@test.com"


def test_success_filter(dialog):
    dialog.status_filter.setCurrentText("Sukces")

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 1).text() == "a@test.com"
    assert dialog.table.item(0, 3).text() == "Sukces"


def test_error_filter(dialog):
    dialog.status_filter.setCurrentText("Błąd")

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 1).text() == "b@test.com"
    assert dialog.table.item(0, 3).text() == "Błąd"


def test_clear_filters(dialog):
    dialog.search_input.setText("book1")
    dialog.status_filter.setCurrentText("Sukces")

    dialog.clear_filters()

    assert dialog.search_input.text() == ""
    assert dialog.status_filter.currentIndex() == 0
    assert dialog.table.rowCount() == 2


def test_result_count(dialog):
    assert dialog.result_count_label.text() == "Liczba wpisów: 2"

    dialog.status_filter.setCurrentText("Sukces")

    assert (
            dialog.result_count_label.text()
            == "Wyświetlono 1 z 2 wpisów"
    )


def test_clear_history_confirmed(dialog):
    with patch(
            "GUI.Widgets.Dialogs.EmailHistoryDialog.confirm_yes_no",
            return_value=True,
    ), patch(
        "builtins.open",
        mock_open(),
    ) as mock_file, patch(
        "GUI.Widgets.Dialogs.EmailHistoryDialog.json.dump"
    ) as mock_dump, patch.object(
        dialog,
        "load_history",
    ) as mock_load:
        dialog.clear_history()

    mock_file.assert_called_once()
    mock_dump.assert_called_once_with(
        [],
        mock_file.return_value.__enter__.return_value,
        indent=4,
        ensure_ascii=False,
    )
    mock_load.assert_called_once()


def test_clear_history_cancelled(dialog):
    with patch(
            "GUI.Widgets.Dialogs.EmailHistoryDialog.confirm_yes_no",
            return_value=False,
    ), patch(
        "builtins.open",
        mock_open(),
    ) as mock_file, patch(
        "GUI.Widgets.Dialogs.EmailHistoryDialog.json.dump"
    ) as mock_dump:
        dialog.clear_history()

    mock_file.assert_not_called()
    mock_dump.assert_not_called()
