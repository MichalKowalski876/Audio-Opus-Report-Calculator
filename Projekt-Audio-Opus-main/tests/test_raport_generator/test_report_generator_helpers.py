import json
from unittest.mock import patch

from core.report_generator import (
    DEFAULT_STYLE,
    _field,
    _logo_html,
    _money,
    load_report_style,
    resolve_logo_path,
)


class TestHelpers:

    def test_field_extracts_existing_key(self):
        record = {"tytul": "Song A", "prog": 100}
        assert _field(record, "title", "tytul", "name") == "Song A"
        assert _field(record, "prog") == 100

    def test_field_uses_default_when_missing(self):
        record = {"id": 1}
        assert _field(record, "title", "tytul", default="Unknown") == "Unknown"

    def test_field_ignores_empty_or_none_values(self):
        record = {"title": "", "tytul": None, "name": "Valid Name"}
        assert _field(record, "title", "tytul", "name", default="Unknown") == "Valid Name"

    def test_field_handles_invalid_record_type(self):
        assert _field(None, "title", default="Fallback") == "Fallback"
        assert _field(["list", "not", "dict"], "title", default="Fallback") == "Fallback"

    def test_money_formatting(self):
        result = _money(1234.56)
        assert result == "1\u00a0234,56\u00a0z\u0142"

        result_zero = _money(0)
        assert result_zero == "0,00\u00a0z\u0142"

        result_large = _money(1000000.99)
        assert result_large == "1\u00a0000\u00a0000,99\u00a0z\u0142"

    @patch("core.report_generator.os.path.exists")
    def test_logo_html_file_exists(self, mock_exists):
        mock_exists.return_value = True
        html = _logo_html()
        assert "<img src='" in html
        assert "logo.png" in html

    @patch("core.report_generator.os.path.exists")
    def test_logo_html_file_missing(self, mock_exists):
        mock_exists.return_value = False
        html = _logo_html()
        assert "<b>AUDIO&nbsp;OPUS</b>" in html
        assert "<img src=" not in html


class TestReportStyle:

    def test_defaults_when_config_is_missing(self, tmp_path):
        style = load_report_style(tmp_path / "brak.json")

        assert style == DEFAULT_STYLE

    def test_configured_values_replace_defaults(self, tmp_path):
        config_path = tmp_path / "report_config.json"
        config_path.write_text(
            json.dumps({"red": "#123456", "heading_font": "Verdana"}),
            encoding="utf-8",
        )

        style = load_report_style(config_path)

        assert style["red"] == "#123456"
        assert style["heading_font"] == "Verdana"
        # Klucze spoza pliku zostaja domyslne.
        assert style["ink"] == DEFAULT_STYLE["ink"]

    def test_broken_config_falls_back_to_defaults(self, tmp_path):
        config_path = tmp_path / "report_config.json"
        config_path.write_text("{ to nie jest json", encoding="utf-8")

        assert load_report_style(config_path) == DEFAULT_STYLE

    def test_logo_path_from_configuration_wins(self, tmp_path):
        logo_file = tmp_path / "moje_logo.png"
        logo_file.write_bytes(b"")

        style = dict(DEFAULT_STYLE)
        style["logo_path"] = str(logo_file)

        assert resolve_logo_path(style) == str(logo_file)

    def test_missing_logo_returns_none(self, tmp_path):
        style = dict(DEFAULT_STYLE)
        style["logo_path"] = str(tmp_path / "nie_ma.png")

        with patch("core.report_generator.os.path.exists", return_value=False):
            assert resolve_logo_path(style) is None
