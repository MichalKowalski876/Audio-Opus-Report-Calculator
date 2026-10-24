import pytest
from unittest.mock import patch, mock_open

from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from core import report_generator
from GUI.Tabs.ReportTab import ReportTab


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    yield app


@pytest.fixture
def report_tab():
    tab = ReportTab()
    yield tab
    tab.close()


def test_initialization(report_tab):
    assert report_tab.folder_output == report_generator.FOLDER
    assert report_tab.pdf_button.text() == "Nowe rozliczenie (PDF)"
    assert report_tab.progress_label.isHidden()
    assert report_tab.progress_bar.isHidden()
    assert report_tab.layout().count() > 0


def test_is_valid_email_format(report_tab):
    assert report_tab.is_valid_email_format("test@example.com") is True
    assert report_tab.is_valid_email_format(
        "user.name+tag@domain.co.uk"
    ) is True
    assert report_tab.is_valid_email_format("invalid-email") is False
    assert report_tab.is_valid_email_format("test@.com") is False
    assert report_tab.is_valid_email_format("@domain.com") is False


@patch("os.path.exists", return_value=False)
def test_load_email_content_defaults(mock_exists, report_tab):
    subject, body = report_tab.load_email_content()

    assert subject == "Zbiorczy raport rozliczeniowy Audio Opus"
    assert "W załączniku znajduje się aktualny raport rozliczeniowy" in body


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"EMAIL_SUBJECT": "Test", "EMAIL_BODY": "Body", "EMAIL_FOOTER": "Footer"}'
)
@patch("os.path.exists", return_value=True)
def test_load_email_content_from_file(
    mock_exists,
    mock_file,
    report_tab
):
    subject, body = report_tab.load_email_content()

    assert subject == "Test"
    assert "Body" in body
    assert "Footer" in body
    assert "--" in body


@patch("GUI.Tabs.ReportTab.MessageSettingsDialog")
def test_open_settings(mock_dialog_class, report_tab):
    mock_dialog = mock_dialog_class.return_value

    report_tab.open_settings()

    mock_dialog.exec.assert_called_once()


@patch("GUI.Tabs.ReportTab.CustomEmailsDialog")
def test_open_custom_emails_manager(mock_dialog_class, report_tab):
    mock_dialog = mock_dialog_class.return_value

    report_tab.open_custom_emails_manager()

    mock_dialog.exec.assert_called_once()


@patch("GUI.Tabs.ReportTab.EmailHistoryDialog")
def test_open_email_history(mock_dialog_class, report_tab):
    mock_dialog = mock_dialog_class.return_value

    report_tab.open_email_history()

    mock_dialog.exec.assert_called_once()


@patch("GUI.Tabs.ReportTab.SettlementDialog")
def test_open_settlement(mock_dialog_class, report_tab):
    mock_dialog = mock_dialog_class.return_value

    report_tab.open_settlement()

    mock_dialog_class.assert_called_once_with(
        report_tab,
        folder_output=report_generator.FOLDER
    )
    mock_dialog.exec.assert_called_once()


@patch("os.remove")
@patch("os.path.exists", return_value=True)
def test_cleanup_report_file_removes_temp_file(
    mock_exists,
    mock_remove,
    report_tab
):
    report_tab._cleanup_report_file(
        "dummy_path.pdf",
        False
    )

    mock_remove.assert_called_once_with("dummy_path.pdf")


@patch("os.remove")
@patch("os.path.exists", return_value=True)
def test_cleanup_report_file_keeps_existing_file(
    mock_exists,
    mock_remove,
    report_tab
):
    report_tab._cleanup_report_file(
        "dummy_path.pdf",
        True
    )

    mock_remove.assert_not_called()


@patch("PySide6.QtWidgets.QMessageBox.warning")
@patch("os.path.exists", return_value=False)
def test_on_send_clicked_blocks_no_smtp(
    mock_exists,
    mock_warning,
    report_tab
):
    report_tab.on_send_clicked()

    mock_warning.assert_called_once()
    assert report_tab._send_worker is None


@patch("json.dump")
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="[]"
)
@patch("os.path.exists", return_value=True)
def test_log_email_history_writes_to_json(
    mock_exists,
    mock_file,
    mock_dump,
    report_tab
):
    report_tab.log_email_history(
        "test@test.com",
        "file.pdf",
        True
    )

    mock_dump.assert_called_once()

    args, kwargs = mock_dump.call_args
    history_list = args[0]

    assert len(history_list) == 1
    assert history_list[0]["receiver"] == "test@test.com"
    assert history_list[0]["success"] is True


@patch("GUI.Tabs.ReportTab.EmailSendWorker")
@patch("GUI.Tabs.ReportTab.SendConfirmationDialog")
@patch("GUI.Tabs.ReportTab.EmailSelectionDialog")
@patch("GUI.Tabs.ReportTab.SettlementDialog")
@patch("os.path.exists", return_value=True)
def test_on_send_clicked_success_path(
    mock_exists,
    mock_settle_class,
    mock_selection_class,
    mock_confirm_class,
    mock_worker_class,
    report_tab
):
    # Settlement dialog
    mock_settle_instance = mock_settle_class.return_value
    mock_settle_instance.exec.return_value = (
        QtWidgets.QDialog.DialogCode.Accepted
    )
    mock_settle_instance.generated_file_path = "valid/path.pdf"
    mock_settle_instance.is_existing_file = False

    # Email selection dialog
    mock_selection_instance = mock_selection_class.return_value
    mock_selection_instance.exec.return_value = (
        QtWidgets.QDialog.DialogCode.Accepted
    )
    mock_selection_instance.selected_emails = [
        "test@example.com"
    ]

    # Confirmation dialog
    mock_confirm_instance = mock_confirm_class.return_value
    mock_confirm_instance.exec.return_value = (
        QtWidgets.QDialog.DialogCode.Accepted
    )

    # Worker
    mock_worker_instance = mock_worker_class.return_value

    report_tab.on_send_clicked()

    assert report_tab.send_button.isEnabled() is False
    assert report_tab.progress_label.isHidden() is False

    mock_worker_instance.start.assert_called_once()


@patch("PySide6.QtWidgets.QMessageBox.information")
def test_on_send_finished_success(
    mock_info,
    report_tab
):
    report_tab._pending_recipients = [
        "test@test.com"
    ]
    report_tab._pending_report_path = "test.pdf"
    report_tab._pending_is_existing_file = True

    with patch.object(
        report_tab,
        "log_email_history"
    ) as mock_log, patch.object(
        report_tab,
        "_cleanup_report_file"
    ) as mock_cleanup:

        report_tab.on_send_finished(
            True,
            "Wysłano"
        )

        assert report_tab.progress_label.isHidden() is True
        assert report_tab.send_button.isEnabled() is True

        mock_log.assert_called_once_with(
            "test@test.com",
            "test.pdf",
            True,
            error=None
        )

        mock_cleanup.assert_called_once_with(
            "test.pdf",
            True
        )

        mock_info.assert_called_once()

        assert report_tab._pending_report_path is None
        assert report_tab._pending_is_existing_file is False
        assert report_tab._pending_recipients == []
