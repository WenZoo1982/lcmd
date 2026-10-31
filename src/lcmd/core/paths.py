"""LCMD 知识库路径管理."""

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

from lcmd.core.config import AppConfig

KNOWLEDGE_DIR_ENV = "LCMD_KNOWLEDGE_DIR"


class PathError(Exception):
    """知识库路径异常."""


@dataclass(frozen=True)
class KnowledgeDirs:
    """知识库目录路径."""

    root: Path
    commands: Path
    tasks: Path


def get_default_knowledge_dir() -> Path:
    """获取当前系统的默认知识库根目录."""
    return Path(user_data_path("lcmd", appauthor=False)) / "knowledge"


def get_knowledge_root() -> Path:
    """获取知识库根目录，优先使用环境变量覆盖."""
    value = os.environ.get(KNOWLEDGE_DIR_ENV)

    if value is None:
        return get_default_knowledge_dir()

    if not value.strip():
        raise PathError(f"环境变量 {KNOWLEDGE_DIR_ENV} 不能为空。")

    try:
        return Path(value).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise PathError(f"无法解析知识库路径：{value}。原因：{exc}") from exc


def validate_knowledge_root(path: Path | str | None = None) -> Path:
    """检查知识库根目录是否存在且为目录."""
    root = Path(path).expanduser() if path is not None else get_knowledge_root()

    try:
        root = root.resolve()

        if not root.exists():
            raise PathError(f"知识库目录不存在：{root}")

        if not root.is_dir():
            raise PathError(f"知识库路径不是目录：{root}")

        return root

    except PathError:
        raise
    except (OSError, RuntimeError) as exc:
        raise PathError(f"无法访问知识库目录：{root}。原因：{exc}") from exc


def get_knowledge_dirs(config: AppConfig) -> KnowledgeDirs:
    """根据平台和语言配置推导命令及任务目录."""
    root = get_knowledge_root()

    return KnowledgeDirs(
        root=root,
        commands=root / "commands" / config.platform / config.language,
        tasks=root / "tasks" / config.platform / config.language,
    )
