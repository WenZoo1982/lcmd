"""LCMD 配置模块测试."""

import json
import tomllib
from pathlib import Path

import pytest

from lcmd.core import config
from lcmd.core.config import AppConfig, ConfigError


def test_get_config_path_uses_platformdirs(monkeypatch, tmp_path):
    """配置路径应由 platformdirs 提供."""
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)

    assert config.get_config_path() == tmp_path / "config.toml"


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("win32", "windows"),
        ("linux", "linux"),
        ("linux2", "linux"),
        ("darwin", "macos"),
    ],
)
def test_get_default_config(system, expected, monkeypatch):
    """应根据运行平台生成默认配置."""
    monkeypatch.setattr(config.sys, "platform", system)

    assert config.get_default_config() == AppConfig(platform=expected)


def test_get_default_config_rejects_unsupported_platform(monkeypatch):
    """不支持的平台应明确报错."""
    monkeypatch.setattr(config.sys, "platform", "unknown")

    with pytest.raises(ConfigError, match="暂不支持"):
        config.get_default_config()


def test_load_config_creates_default_file(tmp_path, monkeypatch):
    """配置文件不存在时应创建默认配置."""
    monkeypatch.setattr(config.sys, "platform", "win32")
    path = tmp_path / "nested" / "config.toml"

    result = config.load_config(path)

    assert result == AppConfig(platform="windows")
    assert path.is_file()

    with path.open("rb") as config_file:
        data = tomllib.load(config_file)

    assert data == {
        "knowledge": {
            "platform": "windows",
            "language": "zh-CN",
        }
    }


@pytest.mark.parametrize("language", ["zh-CN", "en-US"])
def test_load_config_reads_existing_file(tmp_path, language):
    """应正确读取支持的语言配置."""
    path = tmp_path / "config.toml"
    path.write_text(
        f'[knowledge]\nplatform = "linux"\nlanguage = "{language}"\n',
        encoding="utf-8",
    )

    assert config.load_config(path) == AppConfig(
        platform="linux",
        language=language,
    )


def test_load_config_reads_absolute_knowledge_path(tmp_path):
    """应正确读取绝对知识库路径."""
    knowledge_path = tmp_path / "my knowledge"
    path = tmp_path / "config.toml"
    path.write_text(
        "[knowledge]\n"
        'platform = "linux"\n'
        'language = "zh-CN"\n'
        f"path = {json.dumps(str(knowledge_path))}\n",
        encoding="utf-8",
    )

    assert config.load_config(path) == AppConfig(
        platform="linux",
        language="zh-CN",
        path=knowledge_path,
    )


def test_load_config_rejects_relative_knowledge_path(tmp_path):
    """知识库路径必须是绝对路径."""
    path = tmp_path / "config.toml"
    path.write_text(
        '[knowledge]\nplatform = "linux"\nlanguage = "zh-CN"\npath = "relative/knowledge"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        config.load_config(path)


def test_load_config_rejects_non_string_knowledge_path(tmp_path):
    """知识库路径必须是字符串."""
    path = tmp_path / "config.toml"
    path.write_text(
        '[knowledge]\nplatform = "linux"\nlanguage = "zh-CN"\npath = 123\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        config.load_config(path)


def test_save_config_and_load_again(tmp_path):
    """保存后的配置应能重新读取."""
    path = tmp_path / "nested" / "config.toml"
    expected = AppConfig(platform="macos", language="zh-CN")

    saved_path = config.save_config(expected, path)

    assert saved_path == path
    assert config.load_config(path) == expected


def test_save_config_preserves_absolute_knowledge_path(tmp_path):
    """保存后重新读取，知识库路径应保持一致."""
    config_path = tmp_path / "config.toml"
    knowledge_path = tmp_path / "自定义知识库目录"

    expected = AppConfig(
        platform="windows",
        language="zh-CN",
        path=knowledge_path,
    )

    config.save_config(expected, config_path)

    assert config.load_config(config_path) == expected


def test_save_config_rejects_relative_knowledge_path(tmp_path):
    """保存配置时应拒绝相对知识库路径."""
    config_path = tmp_path / "config.toml"
    invalid_config = AppConfig(
        platform="windows",
        path=Path("relative/knowledge"),
    )

    with pytest.raises(ConfigError):
        config.save_config(invalid_config, config_path)

    assert not config_path.exists()


def test_load_config_rejects_invalid_toml(tmp_path):
    """TOML 语法错误时应报错且保留原文件."""
    path = tmp_path / "config.toml"
    original = "[knowledge\nplatform = windows\n"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ConfigError, match="TOML 格式错误"):
        config.load_config(path)

    assert path.read_text(encoding="utf-8") == original


def test_load_config_rejects_missing_section(tmp_path):
    """缺少 knowledge 配置段时应报错."""
    path = tmp_path / "config.toml"
    path.write_text('[other]\nvalue = "test"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="缺少"):
        config.load_config(path)


def test_load_config_rejects_missing_field(tmp_path):
    """缺少必需字段时应报错."""
    path = tmp_path / "config.toml"
    path.write_text('[knowledge]\nplatform = "windows"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="language"):
        config.load_config(path)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('[knowledge]\nplatform = 123\nlanguage = "zh-CN"\n', "platform 必须是字符串"),
        ('[knowledge]\nplatform = "windows"\nlanguage = 123\n', "language 必须是字符串"),
        ('[knowledge]\nplatform = "other"\nlanguage = "zh-CN"\n', "不支持的平台"),
        ('[knowledge]\nplatform = "windows"\nlanguage = "en"\n', "不支持的语言"),
    ],
)
def test_load_config_rejects_invalid_values(tmp_path, content, message):
    """字段类型或字段值无效时应报错."""
    path = tmp_path / "config.toml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        config.load_config(path)


def test_save_config_rejects_invalid_value(tmp_path):
    """保存无效配置时应拒绝写入."""
    path = tmp_path / "config.toml"

    with pytest.raises(ConfigError, match="不支持的平台"):
        config.save_config(AppConfig(platform="other"), path)

    assert not path.exists()


def test_load_config_rejects_missing_platform(tmp_path):
    """缺少 platform 字段时应报错."""
    path = tmp_path / "config.toml"
    path.write_text(
        '[knowledge]\nlanguage = "zh-CN"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="platform"):
        config.load_config(path)


def test_save_config_preserves_existing_file_on_invalid_value(tmp_path):
    """保存非法配置时不得破坏已有配置文件."""
    path = tmp_path / "config.toml"
    original = '[knowledge]\nplatform = "windows"\nlanguage = "zh-CN"\n'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ConfigError, match="不支持的平台"):
        config.save_config(AppConfig(platform="invalid"), path)

    assert path.read_text(encoding="utf-8") == original
