import pytest
from unittest.mock import patch, MagicMock
import smtplib
from keyring.errors import NoKeyringError

from core import email_sender


@pytest.fixture
def mock_env(monkeypatch, tmp_path):
    smtp_config_path = tmp_path / "smtp_config.json"
    msg_config_path = tmp_path / "msg_config.json"

    monkeypatch.setattr(email_sender, "SMTP_CONFIG_FILE", smtp_config_path)
    monkeypatch.setattr(email_sender, "MSG_CONFIG_FILE", msg_config_path)

    attachment = tmp_path / "raport.pdf"
    attachment.write_bytes(b"%PDF-dummy-content")

    monkeypatch.delenv("SMTP_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    return {
        "tmp_path": tmp_path,
        "smtp_config": smtp_config_path,
        "msg_config": msg_config_path,
        "attachment": attachment
    }


class TestLoadJsonConfig:

    def test_load_valid_json(self, tmp_path):
        config_file = tmp_path / "valid.json"
        config_file.write_text('{"key": "value"}', encoding="utf-8")

        result = email_sender.load_json_config(config_file, {"default": 1})
        assert result == {"key": "value"}

    def test_load_invalid_json_returns_default(self, tmp_path, caplog):
        config_file = tmp_path / "invalid.json"
        config_file.write_text('{"key": "value", }', encoding="utf-8")

        default_data = {"default": 1}
        result = email_sender.load_json_config(config_file, default_data)

        assert result == default_data
        assert "jest uszkodzony (błąd JSON)" in caplog.text

    def test_load_missing_file_returns_default(self, tmp_path):
        config_file = tmp_path / "missing.json"

        default_data = {"default": "yes"}
        result = email_sender.load_json_config(config_file, default_data)

        assert result == default_data


@patch("core.email_sender.log_send")
class TestSendReportEmail:

    def test_no_receivers(self, mock_log_send, mock_env):
        result = email_sender.send_report_email([], mock_env["attachment"])
        assert result == {}
        mock_log_send.assert_not_called()

    def test_missing_attachment(self, mock_log_send, mock_env, monkeypatch):
        monkeypatch.setenv("SMTP_EMAIL", "test@test.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")

        fake_attachment = mock_env["tmp_path"] / "nieistnieje.pdf"

        result = email_sender.send_report_email(["odbiorca@test.com"], fake_attachment)

        assert result == {
            "odbiorca@test.com": (False, "Plik załącznika nie istnieje")
        }
        mock_log_send.assert_called_once_with(["odbiorca@test.com"], "nieistnieje.pdf", "error",
                                              "Plik załącznika nie istnieje")

    def test_missing_credentials(self, mock_log_send, mock_env):
        result = email_sender.send_report_email(["odbiorca@test.com"], mock_env["attachment"])

        assert result == {
            "odbiorca@test.com": (False, "Brak danych logowania nadawcy")
        }
        mock_log_send.assert_called_once_with(["odbiorca@test.com"], "raport.pdf", "error",
                                              "Brak danych logowania nadawcy")

    def test_missing_keyring_backend_is_treated_as_missing_credentials(
        self, mock_log_send, mock_env
    ):
        with patch(
            "core.email_sender.keyring.get_password",
            side_effect=NoKeyringError(),
        ):
            result = email_sender.send_report_email(
                ["odbiorca@test.com"], mock_env["attachment"]
            )

        assert result == {
            "odbiorca@test.com": (False, "Brak danych logowania nadawcy")
        }
        mock_log_send.assert_called_once_with(
            ["odbiorca@test.com"],
            "raport.pdf",
            "error",
            "Brak danych logowania nadawcy",
        )

    @patch("core.email_sender.smtplib.SMTP_SSL")
    def test_successful_send(self, mock_smtp_ssl, mock_log_send, mock_env, monkeypatch):
        monkeypatch.setenv("SMTP_EMAIL", "nadawca@test.com")
        monkeypatch.setenv("SMTP_PASSWORD", "tajne_haslo")

        mock_server_instance = MagicMock()
        mock_smtp_ssl.return_value = mock_server_instance

        receivers = ["klient1@test.com", "klient2@test.com"]
        result = email_sender.send_report_email(receivers, mock_env["attachment"])

        assert result == {
            "klient1@test.com": (True, None),
            "klient2@test.com": (True, None),
        }
        mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465)
        mock_server_instance.login.assert_called_once_with("nadawca@test.com", "tajne_haslo")

        # Wysyłka i log lecą osobno dla każdego odbiorcy.
        assert mock_server_instance.sendmail.call_count == 2
        sent_to = [call.args[1] for call in mock_server_instance.sendmail.call_args_list]
        assert sorted(sent_to) == [["klient1@test.com"], ["klient2@test.com"]]
        for call in mock_server_instance.sendmail.call_args_list:
            assert call.args[0] == "nadawca@test.com"

        assert mock_log_send.call_count == 2
        mock_log_send.assert_any_call(["klient1@test.com"], "raport.pdf", "success")
        mock_log_send.assert_any_call(["klient2@test.com"], "raport.pdf", "success")

    @patch("core.email_sender.smtplib.SMTP_SSL")
    def test_smtp_authentication_error(self, mock_smtp_ssl, mock_log_send, mock_env, monkeypatch):
        monkeypatch.setenv("SMTP_EMAIL", "nadawca@test.com")
        monkeypatch.setenv("SMTP_PASSWORD", "zle_haslo")

        mock_server_instance = MagicMock()
        mock_server_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        mock_smtp_ssl.return_value = mock_server_instance

        result = email_sender.send_report_email(["odbiorca@test.com"], mock_env["attachment"])

        assert result == {
            "odbiorca@test.com": (False, "Błąd uwierzytelniania SMTP")
        }
        mock_log_send.assert_called_once_with(["odbiorca@test.com"], "raport.pdf", "error",
                                              "Błąd uwierzytelniania SMTP")

    @patch("core.email_sender.smtplib.SMTP_SSL")
    def test_smtp_general_connection_error(self, mock_smtp_ssl, mock_log_send, mock_env, monkeypatch):
        monkeypatch.setenv("SMTP_EMAIL", "nadawca@test.com")
        monkeypatch.setenv("SMTP_PASSWORD", "haslo")

        mock_smtp_ssl.side_effect = Exception("Timeout Error")

        result = email_sender.send_report_email(["odbiorca@test.com"], mock_env["attachment"])

        assert result == {"odbiorca@test.com": (False, "Timeout Error")}
        mock_log_send.assert_called_once_with(["odbiorca@test.com"], "raport.pdf", "error", "Timeout Error")
