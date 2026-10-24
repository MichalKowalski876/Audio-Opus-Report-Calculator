import smtplib
import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtGui import QGuiApplication

from GUI.Widgets.Workers.EmailSendWorker import EmailSendWorker
from GUI.Widgets.Workers.SMTPTestWorker import SMTPTestWorker


@pytest.fixture(scope="session")
def q_app():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


class TestEmailSendWorker:

    @patch("GUI.Widgets.Workers.EmailSendWorker.email_sender.send_report_email")
    def test_email_send_worker_success(self, mock_send_email, q_app):
        mock_send_email.return_value = {"test@example.com": (True, None)}

        worker = EmailSendWorker(["test@example.com"], "report.pdf")

        results = []
        worker.finished_ok.connect(lambda success, msg: results.append((success, msg)))

        worker.run()

        assert len(results) == 1
        assert results[0][0] is True
        assert "pomyślnie wysłany" in results[0][1]
        mock_send_email.assert_called_once_with(
            ["test@example.com"], "report.pdf",
            custom_subject=None, custom_body=None,
        )

    @patch("GUI.Widgets.Workers.EmailSendWorker.email_sender.send_report_email")
    def test_email_send_worker_failure(self, mock_send_email, q_app):
        mock_send_email.return_value = {
            "test@example.com": (False, "Błąd uwierzytelniania SMTP")
        }

        worker = EmailSendWorker(["test@example.com"], "report.pdf")
        results = []
        worker.finished_ok.connect(lambda success, msg: results.append((success, msg)))

        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert "Nie udało się wysłać" in results[0][1]

    @patch("GUI.Widgets.Workers.EmailSendWorker.email_sender.send_report_email")
    def test_email_send_worker_exception(self, mock_send_email, q_app):
        mock_send_email.side_effect = Exception("Critical disk error")

        worker = EmailSendWorker(["test@example.com"], "report.pdf")
        results = []
        worker.finished_ok.connect(lambda success, msg: results.append((success, msg)))

        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert "Wystąpił błąd podczas wysyłania: Critical disk error" in results[0][1]


class TestSMTPTestWorker:

    @patch("GUI.Widgets.Workers.SMTPTestWorker.smtplib.SMTP_SSL")
    def test_smtp_test_worker_success(self, mock_smtp_ssl, q_app):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        worker = SMTPTestWorker("smtp.test.com", 465, "user@test.com", "password123")
        results = []
        worker.finished_ok.connect(lambda success, msg: results.append((success, msg)))

        worker.run()

        assert len(results) == 1
        assert results[0][0] is True
        assert "zakończone sukcesem" in results[0][1]
        mock_server.login.assert_called_once_with("user@test.com", "password123")

    @patch("GUI.Widgets.Workers.SMTPTestWorker.smtplib.SMTP_SSL")
    def test_smtp_test_worker_auth_error(self, mock_smtp_ssl, q_app):
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad credentials")
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        worker = SMTPTestWorker("smtp.test.com", 465, "user@test.com", "wrong_pass")
        results = []
        worker.finished_ok.connect(lambda success, msg: results.append((success, msg)))

        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert "Błąd uwierzytelniania" in results[0][1]

    @patch("GUI.Widgets.Workers.SMTPTestWorker.smtplib.SMTP_SSL")
    def test_smtp_test_worker_connect_error(self, mock_smtp_ssl, q_app):
        mock_smtp_ssl.side_effect = smtplib.SMTPConnectError(111, b"Connection refused")

        worker = SMTPTestWorker("invalid.server", 465, "user@test.com", "pass")
        results = []
        worker.finished_ok.connect(lambda success, msg: results.append((success, msg)))

        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert "Nie udało się połączyć z serwerem SMTP" in results[0][1]

    @patch("GUI.Widgets.Workers.SMTPTestWorker.smtplib.SMTP_SSL")
    def test_smtp_test_worker_timeout(self, mock_smtp_ssl, q_app):
        mock_smtp_ssl.side_effect = TimeoutError("Connection timed out")

        worker = SMTPTestWorker("smtp.test.com", 465, "user@test.com", "pass")
        results = []
        worker.finished_ok.connect(lambda success, msg: results.append((success, msg)))

        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert "Błąd połączenia: Connection timed out" in results[0][1]