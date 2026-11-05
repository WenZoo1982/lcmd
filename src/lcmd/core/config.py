import json
import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """配置文件读取、解析或结构错误。"""


@dataclass(frozen=True, slots=True)
class AppConfig:
    knowledge_path: Path | None = None
    platform: str = "windows"
    language: str = "zh-CN"


def _validate_config(config: AppConfig) -> None:
    if not isinstance(config, AppConfig):
        raise ConfigError("配置对象类型无效。")

    if config.knowledge_path is not None:
        if not isinstance(config.knowledge_path, Path):
            raise ConfigError("知识库路径必须是 Path 类型。")

        if not str(config.knowledge_path).strip():
            raise ConfigError("知识库路径不能为空。")

    if not isinstance(config.platform, str) or not config.platform.strip():
        raise ConfigError("平台名称必须是非空字符串。")

    if not isinstance(config.language, str) or not config.language.strip():
        raise ConfigError("语言名称必须是非空字符串。")


def load_config(path: Path) -> AppConfig:
    """读取并验证 TOML 配置文件。"""
    path = Path(path)

    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ConfigError("无法读取配置文件。") from exc

    try:
        data = tomllib.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("配置文件格式无效。") from exc

    if not isinstance(data, dict) or set(data) != {"knowledge"}:
        raise ConfigError("配置文件必须且只能包含 [knowledge] 配置段。")

    knowledge = data["knowledge"]

    if not isinstance(knowledge, dict):
        raise ConfigError("[knowledge] 必须是配置表。")

    if set(knowledge) != {"path", "platform", "language"}:
        raise ConfigError("[knowledge] 必须且只能包含 path、platform 和 language。")

    knowledge_path = knowledge["path"]
    platform = knowledge["platform"]
    language = knowledge["language"]

    if not isinstance(knowledge_path, str) or not knowledge_path.strip():
        raise ConfigError("知识库 path 必须是非空字符串。")

    config = AppConfig(
        knowledge_path=Path(knowledge_path).expanduser(),
        platform=platform,
        language=language,
    )

    _validate_config(config)
    return config


def save_config(config: AppConfig, path: Path) -> None:
    """以原子方式保存 TOML 配置文件。"""
    _validate_config(config)

    if config.knowledge_path is None:
        raise ConfigError("保存配置前必须指定知识库路径。")

    path = Path(path)
    parent = path.parent

    content = (
        "[knowledge]\n"
        f"path = {json.dumps(str(config.knowledge_path), ensure_ascii=False)}\n"
        f"platform = {json.dumps(config.platform, ensure_ascii=False)}\n"
        f"language = {json.dumps(config.language, ensure_ascii=False)}\n"
    )

    temporary_path = None

    try:
        parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, path)

    except OSError as exc:
        raise ConfigError("无法保存配置文件。") from exc

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def initialize_config(
    knowledge_path: str | Path,
    config_file: Path | None = None,
) -> AppConfig:
    """Initialize or update LCMD configuration for a knowledge directory.

    Only the knowledge path is changed. Existing platform and language
    preferences are preserved. Knowledge files are not copied or modified.
    """
    from lcmd.core.path_security import validate_knowledge_path

    validated_path = validate_knowledge_path(knowledge_path)

    if config_file is None:
        from lcmd.core.paths import get_config_file

        config_file = get_config_file()

    if config_file.is_file():
        config = load_config(config_file)
        new_config = AppConfig(
            knowledge_path=validated_path,
            platform=config.platform,
            language=config.language,
        )
    else:
        new_config = AppConfig(knowledge_path=validated_path)

    save_config(new_config, config_file)
    return new_config
