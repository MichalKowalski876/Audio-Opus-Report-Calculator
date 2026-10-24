import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Dialogs.UnmatchedTitlesDialog import UnmatchedTitlesDialog


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def entries():
    return [
        {
            "title": "Lustro Iluzji",
            "isbn": "9788397514638",
            "net": 46.66,
            "platform": "Legimi",
            "file": "Legimi.xlsx",
        },
        {
            "title": "Nowy Tytuł",
            "isbn": "",
            "net": 5.0,
            "platform": "Storytel",
            "file": "Storytel.xlsx",
        },
    ]


def test_lists_every_title_checked_by_default(entries):
    dialog = UnmatchedTitlesDialog(entries)

    assert dialog.list_widget.count() == 2
    assert len(dialog.selected_entries()) == 2


def test_shows_isbn_platform_and_amount(entries):
    dialog = UnmatchedTitlesDialog(entries)

    label = dialog.list_widget.item(0).text()

    assert "Lustro Iluzji" in label
    assert "ISBN 9788397514638" in label
    assert "Legimi" in label
    assert "46.66" in label


def test_unchecked_titles_are_not_returned(entries):
    dialog = UnmatchedTitlesDialog(entries)

    dialog.list_widget.item(0).setCheckState(QtCore.Qt.CheckState.Unchecked)
    selected = dialog.selected_entries()

    assert len(selected) == 1
    assert selected[0]["title"] == "Nowy Tytuł"


def test_clear_all_button_unchecks_everything(entries):
    dialog = UnmatchedTitlesDialog(entries)

    dialog.clear_all_button.click()

    assert dialog.selected_entries() == []

    dialog.select_all_button.click()

    assert len(dialog.selected_entries()) == 2


def test_handles_entry_without_details():
    dialog = UnmatchedTitlesDialog([{"title": "", "net": "brak"}])

    assert dialog.list_widget.item(0).text().startswith("(bez nazwy)")
