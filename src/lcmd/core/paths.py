"""LCMD 知识库路径管理."""

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

from lcmd.core.config import AppConfig


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


def get_knowledge_root(config: AppConfig) -> Path:
    """根据配置获取知识库根目录."""
    if config.path is not None:
        return config.path

    return get_default_knowledge_dir()


def validate_knowledge_root(path: Path | str) -> Path:
    """检查知识库根目录是否存在且为目录."""
    root = Path(path).expanduser()

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
    root = get_knowledge_root(config)

    return KnowledgeDirs(
        root=root,
        commands=root / "commands" / config.platform / config.language,
        tasks=root / "tasks" / config.platform / config.language,
    )
