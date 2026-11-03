import json
import re
from pathlib import Path

from lcmd.knowledge.models import (
    KnowledgeBase,
    KnowledgeCatalog,
    KnowledgeDocument,
    PlatformInfo,
    ToolInfo,
)
from lcmd.knowledge.parser import DocumentParseError, parse_document
from lcmd.knowledge.validator import DocumentValidationError, validate_document


class KnowledgeLoadError(ValueError):
    """知识库整体结构或加载条件不符合要求。"""


_SUPPORTED_KNOWLEDGE_MAJOR = 0

_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-(?:[A-Z]{2}|[0-9]{3}))?$")

_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _is_within_root(path: Path, root: Path) -> bool:
    """检查解析后的路径是否仍处于知识库根目录内。"""
    try:
        path.relative_to(root)
    except ValueError:
        return False

    return True


def _is_reserved_name(name: str) -> bool:
    """检查 Windows 保留设备名。"""
    return name.split(".", maxsplit=1)[0].upper() in _RESERVED_NAMES


def _validate_slug(name: str, description: str) -> None:
    """检查路径名称是否符合 slug 规范。"""
    if not _SLUG_PATTERN.fullmatch(name) or _is_reserved_name(name):
        raise KnowledgeLoadError(f"{description}名称不符合命名规范。")


def _validate_language(name: str) -> None:
    """检查语言目录是否使用规范语言标签。"""
    if not _LANGUAGE_PATTERN.fullmatch(name):
        raise KnowledgeLoadError("语言目录名称不符合规范。")


def _check_duplicate_names(paths: list[Path], description: str) -> None:
    """拒绝大小写规范化后发生冲突的同级目录。"""
    names = [path.name.casefold() for path in paths]

    if len(names) != len(set(names)):
        raise KnowledgeLoadError(f"{description}存在名称冲突。")


def _list_directories(
    path: Path,
    description: str,
    root: Path,
) -> list[Path]:
    """列出普通目录，拒绝符号链接和越出知识库根目录的路径。"""
    try:
        resolved_path = path.resolve(strict=True)

        if not _is_within_root(resolved_path, root) or not resolved_path.is_dir():
            raise KnowledgeLoadError(f"{description}不可用。")

        entries = list(path.iterdir())
    except KnowledgeLoadError:
        raise
    except OSError as exc:
        raise KnowledgeLoadError(f"无法读取{description}。") from exc

    directories = []

    for entry in entries:
        if entry.is_symlink():
            raise KnowledgeLoadError(f"{description}中不允许符号链接。")

        try:
            resolved_entry = entry.resolve(strict=True)
        except OSError as exc:
            raise KnowledgeLoadError(f"{description}中存在不可用路径。") from exc

        if not _is_within_root(resolved_entry, root):
            raise KnowledgeLoadError(f"{description}中存在越界路径。")

        if entry.is_dir():
            directories.append(entry)

    _check_duplicate_names(directories, description)

    return sorted(directories, key=lambda item: item.name.casefold())


def _read_manifest(root: Path) -> str:
    """读取并验证知识库 Manifest。"""
    manifest_path = root / "manifest.json"

    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise KnowledgeLoadError("知识库 manifest.json 缺失或不可用。")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise KnowledgeLoadError("知识库 manifest.json 无法解析。") from exc

    if not isinstance(manifest, dict) or set(manifest) != {"version"}:
        raise KnowledgeLoadError("知识库 Manifest 格式无效。")

    version = manifest["version"]

    if not isinstance(version, str):
        raise KnowledgeLoadError("知识库版本号无效。")

    match = _VERSION_PATTERN.fullmatch(version)

    if match is None:
        raise KnowledgeLoadError("知识库版本号格式无效。")

    major = int(match.group(1))

    if major != _SUPPORTED_KNOWLEDGE_MAJOR:
        raise KnowledgeLoadError("知识库主版本与当前程序不兼容。")

    return version


def discover_catalog(root: Path) -> KnowledgeCatalog:
    """发现知识库中的平台、语言和第三方工具。"""
    root = Path(root)

    if root.is_symlink() or not root.is_dir():
        raise KnowledgeLoadError("知识库根目录不可用。")

    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise KnowledgeLoadError("知识库根目录不可用。") from exc

    version = _read_manifest(root)

    commands_path = root / "commands"
    platforms_path = commands_path / "platforms"
    tools_path = commands_path / "tools"

    if (
        commands_path.is_symlink()
        or not commands_path.is_dir()
        or platforms_path.is_symlink()
        or not platforms_path.is_dir()
    ):
        raise KnowledgeLoadError("知识库 commands/platforms 目录缺失或不可用。")

    if tools_path.is_symlink():
        raise KnowledgeLoadError("知识库 tools 目录不允许符号链接。")

    if tools_path.exists() and not tools_path.is_dir():
        raise KnowledgeLoadError("知识库 tools 路径必须是目录。")

    platforms = []

    for platform_path in _list_directories(
        platforms_path,
        "平台目录",
        root,
    ):
        _validate_slug(platform_path.name, "平台")

        languages = _list_directories(
            platform_path,
            "平台语言目录",
            root,
        )

        for language_path in languages:
            _validate_language(language_path.name)

        platforms.append(
            PlatformInfo(
                name=platform_path.name,
                languages=tuple(item.name for item in languages),
            )
        )

    if not platforms:
        raise KnowledgeLoadError("知识库没有可用的平台目录。")

    tools = []

    if tools_path.is_dir():
        for tool_path in _list_directories(
            tools_path,
            "工具目录",
            root,
        ):
            _validate_slug(tool_path.name, "工具")

            languages = _list_directories(
                tool_path,
                "工具语言目录",
                root,
            )

            for language_path in languages:
                _validate_language(language_path.name)

            tools.append(
                ToolInfo(
                    name=tool_path.name,
                    languages=tuple(item.name for item in languages),
                )
            )

    return KnowledgeCatalog(
        root=root,
        version=version,
        platforms=tuple(platforms),
        tools=tuple(tools),
    )


def _load_markdown_directory(
    directory: Path,
    commands_root: Path,
    root: Path,
    category: str,
    platform: str | None,
    tool: str | None,
    language: str,
) -> list[KnowledgeDocument]:
    """递归加载一个语言目录中的有效 Markdown 文档。"""
    documents = []

    try:
        resolved_directory = directory.resolve(strict=True)

        if not _is_within_root(resolved_directory, root) or not resolved_directory.is_dir():
            return documents

        entries = sorted(
            directory.iterdir(),
            key=lambda item: item.name.casefold(),
        )
    except OSError:
        return documents

    # 文件和目录分别检查冲突。
    # foo.md 与 foo/ 是合法组合，不属于同类型名称冲突。
    directory_groups: dict[str, list[Path]] = {}
    markdown_groups: dict[str, list[Path]] = {}

    for entry in entries:
        if entry.is_symlink():
            continue

        try:
            if entry.is_dir():
                directory_groups.setdefault(entry.name.casefold(), []).append(entry)
            elif entry.is_file() and entry.suffix == ".md":
                markdown_groups.setdefault(entry.name.casefold(), []).append(entry)
        except OSError:
            continue

    conflicting_directories = {
        entry for group in directory_groups.values() if len(group) > 1 for entry in group
    }

    conflicting_markdown = {
        entry for group in markdown_groups.values() if len(group) > 1 for entry in group
    }

    for entry in entries:
        if entry.is_symlink():
            continue

        if entry in conflicting_directories or entry in conflicting_markdown:
            continue

        try:
            resolved = entry.resolve(strict=True)
        except OSError:
            continue

        if not _is_within_root(resolved, root):
            continue

        if entry.is_dir():
            try:
                _validate_slug(entry.name, "子命令目录")
            except KnowledgeLoadError:
                continue

            documents.extend(
                _load_markdown_directory(
                    entry,
                    commands_root,
                    root,
                    category,
                    platform,
                    tool,
                    language,
                )
            )
            continue

        if not entry.is_file() or entry.suffix != ".md":
            continue

        try:
            _validate_slug(entry.stem, "文档")
        except KnowledgeLoadError:
            continue

        try:
            content = entry.read_text(encoding="utf-8")
            parsed = parse_document(content)
            validate_document(parsed)
        except (
            OSError,
            UnicodeError,
            DocumentParseError,
            DocumentValidationError,
        ):
            continue

        document_id = entry.relative_to(commands_root).as_posix()

        documents.append(
            KnowledgeDocument(
                id=document_id,
                category=category,
                platform=platform,
                tool=tool,
                language=language,
                summary=parsed.metadata["summary"],
                body=parsed.body,
            )
        )

    return documents


def load_knowledge(
    catalog: KnowledgeCatalog,
    platform: str,
    language: str,
) -> KnowledgeBase:
    """加载指定平台和语言的有效知识文档。"""
    platform = platform.lower()

    selected_platform = next(
        (item for item in catalog.platforms if item.name == platform),
        None,
    )

    if selected_platform is None:
        raise KnowledgeLoadError("指定的平台不存在。")

    if language not in selected_platform.languages:
        raise KnowledgeLoadError("指定语言在当前平台中不可用。")

    try:
        root = catalog.root.resolve(strict=True)
    except OSError as exc:
        raise KnowledgeLoadError("知识库根目录不可用。") from exc

    commands_root = root / "commands"

    platform_directory = commands_root / "platforms" / platform / language

    platform_documents = _load_markdown_directory(
        platform_directory,
        commands_root,
        root,
        "platforms",
        platform,
        None,
        language,
    )

    if not platform_documents:
        raise KnowledgeLoadError("当前平台和语言没有有效的命令文档。")

    documents = list(platform_documents)

    for selected_tool in catalog.tools:
        if language not in selected_tool.languages:
            continue

        tool_directory = commands_root / "tools" / selected_tool.name / language

        tool_documents = _load_markdown_directory(
            tool_directory,
            commands_root,
            root,
            "tools",
            None,
            selected_tool.name,
            language,
        )

        documents.extend(tool_documents)

    return KnowledgeBase(
        platform=platform,
        language=language,
        documents=tuple(documents),
    )
