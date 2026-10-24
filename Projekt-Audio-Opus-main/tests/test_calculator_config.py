import json

import pytest

from core import calculator_config


@pytest.fixture(autouse=True)
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "calculator_config.json"
    monkeypatch.setattr(calculator_config, "CONFIG_FILE", str(path))
    return path


def test_default_when_missing(config_file):
    assert calculator_config.load_vat_percent() == calculator_config.DEFAULT_VAT_PERCENT


def test_save_then_load_roundtrip(config_file):
    calculator_config.save_vat_percent(8)

    assert json.loads(config_file.read_text(encoding="utf-8")) == {"VAT_PERCENT": 8.0}
    assert calculator_config.load_vat_percent() == 8.0


def test_reads_existing_value(config_file):
    config_file.write_text('{"VAT_PERCENT": 5}', encoding="utf-8")

    assert calculator_config.load_vat_percent() == 5.0


@pytest.mark.parametrize(
    "content",
    [
        "{ not json",
        "[]",
        '{"VAT_PERCENT": "abc"}',
        '{"VAT_PERCENT": -3}',
        "{}",
    ],
)
def test_falls_back_on_bad_content(config_file, content):
    config_file.write_text(content, encoding="utf-8")

    assert calculator_config.load_vat_percent() == calculator_config.DEFAULT_VAT_PERCENT


def test_save_keeps_unrelated_keys(config_file):
    config_file.write_text('{"OTHER": 1}', encoding="utf-8")

    calculator_config.save_vat_percent(8)

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data == {"OTHER": 1, "VAT_PERCENT": 8.0}
