import json

from core import debug_config


def test_debug_config_uses_persistent_data_path():
    assert debug_config.CONFIG_FILE.name == "debug_config.json"
    assert debug_config.CONFIG_FILE.parent.name == "Databases"


def test_debug_config_round_trip(tmp_path, monkeypatch):
    config_path = tmp_path / "debug_config.json"
    monkeypatch.setattr(debug_config, "CONFIG_FILE", config_path)

    assert debug_config.load() == debug_config.DEFAULT_CONFIG

    debug_config.set_enabled(True)

    assert debug_config.is_enabled() is True
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "enabled": True
    }
