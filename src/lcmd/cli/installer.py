"""安装器 CLI 操作。"""

from collections.abc import Callable
from pathlib import Path

from lcmd.core.installer import (
    KnowledgeDestinationState,
    deploy_knowledge_distribution,
    inspect_knowledge_destination,
)
from lcmd.core.paths import get_default_knowledge_path


def check_installer_destination() -> KnowledgeDestinationState:
    """检查默认知识库目录，返回安装器使用的状态。"""
    inspection = inspect_knowledge_destination(get_default_knowledge_path())
    return inspection.state


def deploy_installer_knowledge(
    source_dir: str,
    integrity_file: str,
    *,
    replace_existing: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """部署安装包知识库，返回部署完成的默认目录。"""
    destination = get_default_knowledge_path()

    deploy_knowledge_distribution(
        source_dir,
        destination,
        integrity_file,
        replace_existing=replace_existing,
        progress_callback=progress_callback,
    )

    return destination
