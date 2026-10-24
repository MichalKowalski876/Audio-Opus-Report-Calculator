import pytest
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Dialogs.SendConfirmationDialog import (
    SendConfirmationDialog,
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    yield app


@pytest.fixture
def dialog():
    dlg = SendConfirmationDialog(
        recipients=[
            "jan@test.com",
            "anna@test.com",
        ],
        attachment_name="raport.pdf",
        subject="Raport rozliczeniowy",
        body="Dzień dobry,\n\nW załączniku raport.",
    )

    yield dlg
    dlg.close()


def test_initialization(dialog):
    assert dialog.windowTitle() == "Potwierdzenie wysyłki"
    assert dialog.size().width() == 450
    assert dialog.size().height() == 460


def test_recipients(dialog):
    lists = dialog.findChildren(QtWidgets.QListWidget)

    assert len(lists) == 1

    recipients_list = lists[0]

    assert recipients_list.count() == 2
    assert recipients_list.item(0).text() == "jan@test.com"
    assert recipients_list.item(1).text() == "anna@test.com"


def test_attachment_and_subject(dialog):
    labels = [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]

    assert "<b>Załącznik:</b> raport.pdf" in labels
    assert "<b>Temat:</b>" in labels
    # Temat jest teraz edytowalny przed wysyłką.
    assert dialog.subject_input.text() == "Raport rozliczeniowy"


def test_body(dialog):
    text_edits = dialog.findChildren(QtWidgets.QTextEdit)

    assert len(text_edits) == 1
    assert dialog.body_preview.toPlainText() == (
        "Dzień dobry,\n\nW załączniku raport."
    )
    # Treść jest edytowalna przed wysyłką (ReportTab czyta ją z powrotem).
    assert not dialog.body_preview.isReadOnly()


def test_buttons(dialog):
    buttons = dialog.findChildren(QtWidgets.QDialogButtonBox)

    assert len(buttons) == 1

    button_box = buttons[0]

    send_button = button_box.button(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
    )
    cancel_button = button_box.button(
        QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )

    assert send_button.text() == "Wyślij"
    assert cancel_button.text() == "Anuluj"


def test_accept(dialog):
    with pytest.MonkeyPatch.context() as mp:
        accepted = []

        mp.setattr(
            dialog,
            "accept",
            lambda: accepted.append(True),
        )

        buttons = dialog.findChildren(
            QtWidgets.QDialogButtonBox
        )[0]

        buttons.accepted.emit()

        assert accepted == [True]


def test_reject(dialog):
    with pytest.MonkeyPatch.context() as mp:
        rejected = []

        mp.setattr(
            dialog,
            "reject",
            lambda: rejected.append(True),
        )

        buttons = dialog.findChildren(
            QtWidgets.QDialogButtonBox
        )[0]

        buttons.rejected.emit()

        assert rejected == [True]
