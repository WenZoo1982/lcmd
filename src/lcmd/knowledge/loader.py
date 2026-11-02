"""LCMD 知识库加载器."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lcmd import __version__
from lcmd.core.config import AppConfig
from lcmd.core.paths import PathError, get_knowledge_dirs, validate_knowledge_root
from lcmd.knowledge.parser import DocumentParseError, parse_document
from lcmd.knowledge.validator import (
    DocumentValidationError,
    validate_document,
)


class KnowledgeLoadError(Exception):
    """知识库整体加载异常."""


@dataclass(frozen=True)
class LoadedDocument:
    """已加载的知识文档."""

    name: str
    path: Path
    metadata: dict[str, Any]
    body: str


@dataclass(frozen=True)
class LoadDiagnostic:
    """单篇知识文档加载诊断."""

    path: Path
    message: str


@dataclass
class KnowledgeLoadResult:
    """知识库加载结果."""

    commands: list[LoadedDocument]
    diagnostics: list[LoadDiagnostic]


_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)"
    r"\.(0|[1-9]\d*)"
    r"\.(0|[1-9]\d*)"
    r"(?:-("
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*"
    r"))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _parse_version(version: str, source: str) -> tuple[int, int, int]:
    """验证 SemVer 格式并返回 Major、Minor、Patch."""
    match = _SEMVER_PATTERN.fullmatch(version)

    if match is None:
        raise KnowledgeLoadError(f"{source}版本格式无效：{version!r}。必须符合 SemVer 2.0.0。")

    return tuple(int(match.group(index)) for index in range(1, 4))


def _load_manifest(root: Path) -> str:
    """读取并验证知识库清单，返回知识库版本."""
    manifest_path = root / "manifest.json"

    try:
        content = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise KnowledgeLoadError(f"知识库清单 manifest.json 不存在：{manifest_path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise KnowledgeLoadError(
            f"无法读取知识库清单 manifest.json：{manifest_path}。原因：{exc}"
        ) from exc

    try:
        manifest = json.loads(content)
    except json.JSONDecodeError as exc:
        raise KnowledgeLoadError(f"知识库清单 manifest.json JSON 格式错误：{exc}") from exc

    if not isinstance(manifest, dict):
        raise KnowledgeLoadError("知识库清单 manifest.json 格式错误：顶层内容必须是 JSON 对象。")

    if set(manifest) != {"version"}:
        raise KnowledgeLoadError("知识库清单 manifest.json 字段错误：只允许 version 字段。")

    version = manifest["version"]

    if not isinstance(version, str):
        raise KnowledgeLoadError("知识库清单 manifest.json 格式错误：version 必须是字符串。")

    _parse_version(version, "知识库")

    return version


def load_knowledge_version(config: AppConfig) -> str:
    """只读取本地知识库 manifest 版本，不加载 Markdown 文档."""
    try:
        dirs = get_knowledge_dirs(config)
        root = validate_knowledge_root(dirs.root)
    except PathError as exc:
        raise KnowledgeLoadError(f"知识库根目录无效：{exc}") from exc

    return _load_manifest(root)


def _check_version_compatibility(knowledge_version: str) -> None:
    """只比较知识库与主程序的 Major 版本."""
    knowledge_major, _, _ = _parse_version(knowledge_version, "知识库")
    app_major, _, _ = _parse_version(__version__, "主程序")

    if knowledge_major < app_major:
        raise KnowledgeLoadError(
            f"知识库版本过旧：知识库 Major 版本为 {knowledge_major}，"
            f"主程序 Major 版本为 {app_major}。请更新知识库。"
        )

    if knowledge_major > app_major:
        raise KnowledgeLoadError(
            f"主程序版本过旧：知识库 Major 版本为 {knowledge_major}，"
            f"主程序 Major 版本为 {app_major}。请升级主程序。"
        )


def _load_documents(
    directory: Path,
    document_type: str,
) -> tuple[list[LoadedDocument], list[LoadDiagnostic]]:
    """加载指定目录中的 Markdown 文档，隔离单篇文档错误."""
    documents: list[LoadedDocument] = []
    diagnostics: list[LoadDiagnostic] = []

    if not directory.exists():
        return documents, diagnostics

    if not directory.is_dir():
        diagnostics.append(
            LoadDiagnostic(
                path=directory,
                message="知识文档目录路径不是目录，已跳过。",
            )
        )
        return documents, diagnostics

    try:
        paths = sorted(
            directory.glob("*.md"),
            key=lambda path: path.name.casefold(),
        )
    except OSError as exc:
        raise KnowledgeLoadError(f"无法扫描知识文档目录：{directory}。原因：{exc}") from exc

    for path in paths:
        try:
            content = path.read_text(encoding="utf-8")
            parsed = parse_document(content)
            metadata = validate_document(parsed, document_type)

            documents.append(
                LoadedDocument(
                    name=path.stem,
                    path=path,
                    metadata=metadata,
                    body=parsed.body,
                )
            )
        except (
            OSError,
            UnicodeDecodeError,
            DocumentParseError,
            DocumentValidationError,
        ) as exc:
            diagnostics.append(
                LoadDiagnostic(
                    path=path,
                    message=str(exc),
                )
            )

    return documents, diagnostics


def load_knowledge(config: AppConfig) -> KnowledgeLoadResult:
    """加载当前平台命令文档，缺少的文档逐项回退到 common."""
    try:
        dirs = get_knowledge_dirs(config)
        root = validate_knowledge_root(dirs.root)
    except PathError as exc:
        raise KnowledgeLoadError(f"知识库根目录无效：{exc}") from exc

    knowledge_version = _load_manifest(root)
    _check_version_compatibility(knowledge_version)

    common_commands = root / "commands" / "common" / config.language

    platform_commands, command_diagnostics = _load_documents(
        dirs.commands,
        "command",
    )
    common_command_docs, common_command_diagnostics = _load_documents(
        common_commands,
        "command",
    )

    # 平台文档优先；common 只补充平台缺少的同名文档。
    command_names = {doc.name.casefold() for doc in platform_commands}
    commands = platform_commands + [
        doc for doc in common_command_docs if doc.name.casefold() not in command_names
    ]

    return KnowledgeLoadResult(
        commands=commands,
        diagnostics=command_diagnostics + common_command_diagnostics,
    )
