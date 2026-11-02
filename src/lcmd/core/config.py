"""LCMD 用户配置管理."""

import json
import os
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_path

SUPPORTED_PLATFORMS = {"windows", "linux", "macos"}
SUPPORTED_LANGUAGES = {"zh-CN", "en-US"}


class ConfigError(Exception):
    """用户配置读取、校验或保存异常."""


@dataclass(frozen=True)
class AppConfig:
    """LCMD 用户配置."""

    platform: str
    language: str = "zh-CN"
    path: Path | None = None


def get_config_path() -> Path:
    """获取当前系统的默认配置文件路径."""
    return Path(user_config_path("lcmd", appauthor=False)) / "config.toml"


def get_default_config() -> AppConfig:
    """根据当前运行系统生成默认配置."""
    if sys.platform == "win32":
        platform = "windows"
    elif sys.platform.startswith("linux"):
        platform = "linux"
    elif sys.platform == "darwin":
        platform = "macos"
    else:
        raise ConfigError(f"暂不支持当前操作系统：{sys.platform}")

    return AppConfig(platform=platform)


def _validate_config(config: AppConfig) -> None:
    """验证配置对象."""
    if not isinstance(config.platform, str):
        raise ConfigError("配置项 knowledge.platform 必须是字符串。")

    if config.platform not in SUPPORTED_PLATFORMS:
        allowed = "、".join(sorted(SUPPORTED_PLATFORMS))
        raise ConfigError(f"不支持的平台：{config.platform}。允许的值：{allowed}。")

    if not isinstance(config.language, str):
        raise ConfigError("配置项 knowledge.language 必须是字符串。")

    if config.language not in SUPPORTED_LANGUAGES:
        allowed = "、".join(sorted(SUPPORTED_LANGUAGES))
        raise ConfigError(f"不支持的语言：{config.language}。允许的值：{allowed}。")

    if config.path is not None:
        if not isinstance(config.path, Path):
            raise ConfigError("配置项 knowledge.path 必须是 Path 类型。")

        if not config.path.is_absolute():
            raise ConfigError("配置项 knowledge.path 必须是绝对路径。")


def _parse_config(data: dict) -> AppConfig:
    """解析并验证 TOML 配置数据."""
    knowledge = data.get("knowledge")

    if not isinstance(knowledge, dict):
        raise ConfigError("配置文件缺少 [knowledge] 配置段或格式不正确。")

    if "platform" not in knowledge:
        raise ConfigError("配置文件缺少 knowledge.platform 字段。")

    if "language" not in knowledge:
        raise ConfigError("配置文件缺少 knowledge.language 字段。")

    knowledge_path = knowledge.get("path")

    if knowledge_path is not None:
        if not isinstance(knowledge_path, str):
            raise ConfigError("配置项 knowledge.path 必须是字符串。")

        knowledge_path = Path(knowledge_path)

        if not knowledge_path.is_absolute():
            raise ConfigError("配置项 knowledge.path 必须是绝对路径。")

    config = AppConfig(
        platform=knowledge["platform"],
        language=knowledge["language"],
        path=knowledge_path,
    )

    _validate_config(config)
    return config


def save_config(config: AppConfig, path: Path | str | None = None) -> Path:
    """保存配置文件，并通过临时文件替换避免直接破坏原文件."""
    _validate_config(config)

    config_path = Path(path) if path is not None else get_config_path()
    temporary_path: Path | None = None

    content = (
        f"[knowledge]\n"
        f"platform = {json.dumps(config.platform)}\n"
        f"language = {json.dumps(config.language)}\n"
    )

    if config.path is not None:
        content += f"path = {json.dumps(str(config.path))}\n"

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=config_path.parent,
            prefix=f".{config_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, config_path)
        return config_path

    except OSError as exc:
        raise ConfigError(f"无法保存配置文件：{config_path}。原因：{exc}") from exc

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def load_config(path: Path | str | None = None) -> AppConfig:
    """读取配置；文件不存在时应创建默认配置."""
    config_path = Path(path) if path is not None else get_config_path()

    if not config_path.exists():
        config = get_default_config()
        save_config(config, config_path)
        return config

    try:
        with config_path.open("rb") as config_file:
            data = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"配置文件 TOML 格式错误：{config_path}。原因：{exc}") from exc
    except OSError as exc:
        raise ConfigError(f"无法读取配置文件：{config_path}。原因：{exc}") from exc

    return _parse_config(data)
