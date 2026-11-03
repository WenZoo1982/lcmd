import tomllib
from pathlib import Path

import pytest

from lcmd.core.config import AppConfig, ConfigError, load_config, save_config


def test_app_config_defaults():
    config = AppConfig()

    assert config.knowledge_path is None
    assert config.platform == "windows"
    assert config.language == "zh-CN"


def test_save_and_load_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config = AppConfig(
        knowledge_path=Path(r"D:\Project_DEV\lcmd-kb"),
        platform="windows",
        language="zh-CN",
    )

    save_config(config, config_path)
    loaded = load_config(config_path)

    assert loaded == config


def test_save_config_creates_parent_directory(tmp_path):
    config_path = tmp_path / "config" / "nested" / "config.toml"
    config = AppConfig(
        knowledge_path=Path(r"D:\Project_DEV\lcmd-kb"),
    )

    save_config(config, config_path)

    assert config_path.is_file()
    assert load_config(config_path) == config


def test_save_config_writes_valid_toml(tmp_path):
    config_path = tmp_path / "config.toml"
    config = AppConfig(
        knowledge_path=Path(r"D:\Project_DEV\lcmd-kb"),
    )

    save_config(config, config_path)

    with config_path.open("rb") as file:
        data = tomllib.load(file)

    assert data == {
        "knowledge": {
            "path": r"D:\Project_DEV\lcmd-kb",
            "platform": "windows",
            "language": "zh-CN",
        }
    }


def test_load_config_rejects_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "missing.toml")


def test_load_config_rejects_invalid_utf8(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_bytes(b"\xff\xfe")

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_invalid_toml(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[knowledge\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_missing_knowledge_section(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_unknown_top_level_section(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[knowledge]\n"
        'path = "D:/kb"\n'
        'platform = "windows"\n'
        'language = "zh-CN"\n'
        "\n"
        "[other]\n"
        "enabled = true\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_missing_knowledge_field(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[knowledge]\npath = "D:/kb"\nplatform = "windows"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_unknown_knowledge_field(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[knowledge]\npath = "D:/kb"\nplatform = "windows"\nlanguage = "zh-CN"\nextra = true\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


@pytest.mark.parametrize(
    "field_value",
    [
        "",
        "   ",
    ],
)
def test_load_config_rejects_invalid_path_values(tmp_path, field_value):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[knowledge]\npath = {field_value!r}\nplatform = "windows"\nlanguage = "zh-CN"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("platform", '""'),
        ("platform", "123"),
        ("language", '""'),
        ("language", "true"),
    ],
)
def test_load_config_rejects_invalid_selection_values(
    tmp_path,
    field,
    value,
):
    values = {
        "path": '"D:/kb"',
        "platform": '"windows"',
        "language": '"zh-CN"',
    }
    values[field] = value

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[knowledge]\n"
        f"path = {values['path']}\n"
        f"platform = {values['platform']}\n"
        f"language = {values['language']}\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_save_config_rejects_missing_knowledge_path(tmp_path):
    with pytest.raises(ConfigError):
        save_config(AppConfig(), tmp_path / "config.toml")


def test_save_config_rejects_invalid_platform():
    config = AppConfig(
        knowledge_path=Path("D:/kb"),
        platform=" ",
    )

    with pytest.raises(ConfigError):
        save_config(config, Path("config.toml"))


def test_save_config_rejects_invalid_language():
    config = AppConfig(
        knowledge_path=Path("D:/kb"),
        language="",
    )

    with pytest.raises(ConfigError):
        save_config(config, Path("config.toml"))


def test_failed_save_preserves_existing_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    original = '[knowledge]\npath = "D:/old-kb"\nplatform = "windows"\nlanguage = "zh-CN"\n'
    config_path.write_text(original, encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("lcmd.core.config.os.replace", fail_replace)

    config = AppConfig(
        knowledge_path=Path("D:/new-kb"),
        platform="linux",
        language="en-US",
    )

    with pytest.raises(ConfigError):
        save_config(config, config_path)

    assert config_path.read_text(encoding="utf-8") == original
