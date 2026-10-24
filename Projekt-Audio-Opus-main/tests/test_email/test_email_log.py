import json
import pytest

import core.email_log as email_log


@pytest.fixture
def mock_log_env(tmp_path, monkeypatch):
    test_log_file = tmp_path / "email_log.json"
    monkeypatch.setattr(email_log, "LOG_FILE", test_log_file)
    return test_log_file


class TestEmailLog:

    def test_get_all_logs_empty(self, mock_log_env):
        logs = email_log.get_all_logs()
        assert logs == []

    def test_log_send_creates_entry(self, mock_log_env):
        recipients = ["test@example.com"]
        pdf_name = "raport_test.pdf"

        email_log.log_send(recipients, pdf_name, "success")

        assert mock_log_env.exists()
        logs = email_log.get_all_logs()

        assert len(logs) == 1
        assert logs[0]["recipients"] == recipients
        assert logs[0]["pdf_name"] == pdf_name
        assert logs[0]["status"] == "success"
        assert logs[0]["error_message"] is None
        assert "date" in logs[0]

    def test_log_send_with_error_message(self, mock_log_env):
        email_log.log_send("odbiorca@example.com", "raport.pdf", "error", "SMTP Timeout")

        logs = email_log.get_all_logs()
        assert len(logs) == 1
        assert logs[0]["status"] == "error"
        assert logs[0]["error_message"] == "SMTP Timeout"
        assert logs[0]["recipients"] == "odbiorca@example.com"

    def test_log_send_appends_to_existing(self, mock_log_env):
        initial_data = [{"date": "2026-01-01 10:00:00", "status": "success"}]
        mock_log_env.write_text(json.dumps(initial_data), encoding="utf-8")

        email_log.log_send(["a@b.com"], "report2.pdf", "success")

        logs = email_log.get_all_logs()
        assert len(logs) == 2
        assert logs[0]["status"] == "success"
        assert logs[1]["pdf_name"] == "report2.pdf"

    def test_get_all_logs_corrupted_json(self, mock_log_env, caplog):
        mock_log_env.write_text("{invalid_json...", encoding="utf-8")

        email_log.log_send(["user@test.com"], "raport.pdf", "success")

        logs = email_log.get_all_logs()
        assert len(logs) == 1
        assert logs[0]["pdf_name"] == "raport.pdf"
        assert "uszkodzony — nadpisuję nową listą" in caplog.text