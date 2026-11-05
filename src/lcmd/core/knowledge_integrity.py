from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from lcmd.knowledge.loader import KnowledgeLoadError, discover_catalog

_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_PRERELEASE_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_INTEGRITY_FIELDS = {
    "schema_version",
    "main_version",
    "main_prerelease",
    "knowledge_version",
    "knowledge_archive_sha256",
    "file_count",
    "files",
}

_FILE_FIELDS = {"path", "size", "sha256"}

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


class KnowledgeIntegrityError(ValueError):
    """安装器操作失败。"""


@dataclass(frozen=True)
class KnowledgeDistributionInfo:
    """经过完整性验证的发行包信息。"""

    main_version: str
    main_prerelease: str
    knowledge_version: str
    knowledge_archive_sha256: str
    file_count: int


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for key, value in pairs:
        if key in result:
            raise KnowledgeIntegrityError(f"JSON 中存在重复字段：{key}")
        result[key] = value

    return result


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise KnowledgeIntegrityError(f"无法读取文件：{path}") from exc

    if not stat.S_ISREG(file_stat.st_mode):
        raise KnowledgeIntegrityError(f"不是普通文件：{path}")

    if _is_reparse_point(file_stat):
        raise KnowledgeIntegrityError(f"不允许使用符号链接或重解析点：{path}")

    try:
        content = path.read_text(encoding="utf-8-sig")
        data = json.loads(
            content,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except KnowledgeIntegrityError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise KnowledgeIntegrityError(f"JSON 文件无效：{path}") from exc

    if not isinstance(data, dict):
        raise KnowledgeIntegrityError(f"JSON 顶层必须是对象：{path}")

    return data


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    attributes = getattr(file_stat, "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _validate_integrity_manifest(data: dict[str, Any]) -> KnowledgeDistributionInfo:
    if set(data) != _INTEGRITY_FIELDS:
        raise KnowledgeIntegrityError("发行完整性清单字段不符合要求。")

    schema_version = data["schema_version"]
    if isinstance(schema_version, bool) or schema_version != 1:
        raise KnowledgeIntegrityError("不支持的发行完整性清单版本。")

    main_version = data["main_version"]
    if not isinstance(main_version, str) or not _VERSION_PATTERN.fullmatch(main_version):
        raise KnowledgeIntegrityError("主程序版本号格式无效。")

    main_prerelease = data["main_prerelease"]
    if not isinstance(main_prerelease, str) or not _PRERELEASE_PATTERN.fullmatch(main_prerelease):
        raise KnowledgeIntegrityError("主程序预发布版本标识无效。")

    knowledge_version = data["knowledge_version"]
    if not isinstance(knowledge_version, str) or not _VERSION_PATTERN.fullmatch(knowledge_version):
        raise KnowledgeIntegrityError("知识库版本号格式无效。")

    archive_sha256 = data["knowledge_archive_sha256"]
    if not isinstance(archive_sha256, str) or not _SHA256_PATTERN.fullmatch(archive_sha256):
        raise KnowledgeIntegrityError("知识库压缩包 SHA-256 格式无效。")

    file_count = data["file_count"]
    if isinstance(file_count, bool) or not isinstance(file_count, int) or file_count < 0:
        raise KnowledgeIntegrityError("发行文件数量无效。")

    files = data["files"]
    if not isinstance(files, list):
        raise KnowledgeIntegrityError("发行文件清单必须是数组。")

    if len(files) != file_count:
        raise KnowledgeIntegrityError("发行文件数量与清单记录数量不一致。")

    return KnowledgeDistributionInfo(
        main_version=main_version,
        main_prerelease=main_prerelease,
        knowledge_version=knowledge_version,
        knowledge_archive_sha256=archive_sha256,
        file_count=file_count,
    )


def _validate_relative_file_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise KnowledgeIntegrityError("发行文件路径必须是非空字符串。")

    if "\\" in value or "\x00" in value:
        raise KnowledgeIntegrityError(f"发行文件路径格式无效：{value!r}")

    path = PurePosixPath(value)

    if path.is_absolute() or not path.parts:
        raise KnowledgeIntegrityError(f"发行文件路径必须是相对路径：{value!r}")

    if any(part in {"", ".", ".."} for part in path.parts):
        raise KnowledgeIntegrityError(f"发行文件路径包含非法目录：{value!r}")

    if path.as_posix() != value:
        raise KnowledgeIntegrityError(f"发行文件路径不是规范格式：{value!r}")

    for part in path.parts:
        if part.endswith((" ", ".")):
            raise KnowledgeIntegrityError(f"发行文件路径包含 Windows 不安全名称：{value!r}")

        if ":" in part:
            raise KnowledgeIntegrityError(f"发行文件路径包含非法字符：{value!r}")

        device_name = part.split(".", 1)[0].upper()
        if device_name in _WINDOWS_RESERVED_NAMES:
            raise KnowledgeIntegrityError(f"发行文件路径使用了 Windows 保留名称：{value!r}")

    return value


def _collect_actual_files(root: Path) -> dict[str, Path]:
    actual_files: dict[str, Path] = {}
    folded_paths: dict[str, str] = {}

    try:
        for current_root, directory_names, file_names in os.walk(
            root,
            topdown=True,
            followlinks=False,
        ):
            current_path = Path(current_root)

            for directory_name in directory_names:
                directory_path = current_path / directory_name

                try:
                    directory_stat = directory_path.lstat()
                except OSError as exc:
                    raise KnowledgeIntegrityError(f"无法检查知识库目录：{directory_path}") from exc

                if not stat.S_ISDIR(directory_stat.st_mode) or _is_reparse_point(directory_stat):
                    raise KnowledgeIntegrityError(
                        f"知识库中存在符号链接或非普通目录：{directory_path}"
                    )

            for file_name in file_names:
                file_path = current_path / file_name

                try:
                    file_stat = file_path.lstat()
                except OSError as exc:
                    raise KnowledgeIntegrityError(f"无法检查知识库文件：{file_path}") from exc

                if not stat.S_ISREG(file_stat.st_mode) or _is_reparse_point(file_stat):
                    raise KnowledgeIntegrityError(f"知识库中存在符号链接或非普通文件：{file_path}")

                relative_path = file_path.relative_to(root).as_posix()
                _validate_relative_file_path(relative_path)

                folded = relative_path.casefold()
                if folded in folded_paths:
                    raise KnowledgeIntegrityError(
                        "知识库中存在大小写不敏感的路径冲突："
                        f"{folded_paths[folded]} 与 {relative_path}"
                    )

                folded_paths[folded] = relative_path
                actual_files[relative_path] = file_path

    except OSError as exc:
        raise KnowledgeIntegrityError(f"无法遍历知识库目录：{root}") from exc

    return actual_files


def _calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    try:
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise KnowledgeIntegrityError(f"无法读取发行文件：{path}") from exc

    return digest.hexdigest()


def verify_knowledge_distribution(
    knowledge_dir: str | os.PathLike[str],
    integrity_file: str | os.PathLike[str] | None = None,
) -> KnowledgeDistributionInfo:
    """验证随包知识库的结构、文件集合、大小和 SHA-256。

    该函数只读取文件，不创建、删除或修改任何文件。

    integrity_file 未指定时，默认读取知识库目录的上一级目录中的
    knowledge-integrity.json。
    """
    root = Path(knowledge_dir)

    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise KnowledgeIntegrityError(f"知识库目录不存在或无法访问：{root}") from exc

    if not stat.S_ISDIR(root_stat.st_mode) or _is_reparse_point(root_stat):
        raise KnowledgeIntegrityError(f"知识库路径不是普通目录：{root}")

    root = root.resolve(strict=True)

    if integrity_file is None:
        manifest_path = root.parent / "knowledge-integrity.json"
    else:
        manifest_path = Path(integrity_file)

    integrity_data = _read_json_file(manifest_path)
    distribution = _validate_integrity_manifest(integrity_data)

    files = integrity_data["files"]
    expected_files: dict[str, dict[str, Any]] = {}
    folded_paths: dict[str, str] = {}

    for item in files:
        if not isinstance(item, dict) or set(item) != _FILE_FIELDS:
            raise KnowledgeIntegrityError("发行文件记录字段不符合要求。")

        relative_path = _validate_relative_file_path(item["path"])

        folded = relative_path.casefold()
        if folded in folded_paths:
            raise KnowledgeIntegrityError(
                f"发行清单中存在大小写不敏感的路径冲突：{folded_paths[folded]} 与 {relative_path}"
            )

        folded_paths[folded] = relative_path

        size = item["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise KnowledgeIntegrityError(f"发行文件大小无效：{relative_path}")

        sha256 = item["sha256"]
        if not isinstance(sha256, str) or not _SHA256_PATTERN.fullmatch(sha256):
            raise KnowledgeIntegrityError(f"发行文件 SHA-256 无效：{relative_path}")

        expected_files[relative_path] = item

    actual_files = _collect_actual_files(root)

    expected_paths = set(expected_files)
    actual_paths = set(actual_files)

    missing_files = sorted(expected_paths - actual_paths)
    extra_files = sorted(actual_paths - expected_paths)

    if missing_files:
        raise KnowledgeIntegrityError("知识库缺少发行文件：" + ", ".join(missing_files[:10]))

    if extra_files:
        raise KnowledgeIntegrityError("知识库包含清单之外的文件：" + ", ".join(extra_files[:10]))

    for relative_path, expected in expected_files.items():
        file_path = actual_files[relative_path]

        try:
            actual_size = file_path.stat().st_size
        except OSError as exc:
            raise KnowledgeIntegrityError(f"无法读取文件大小：{relative_path}") from exc

        if actual_size != expected["size"]:
            raise KnowledgeIntegrityError(f"发行文件大小不匹配：{relative_path}")

        actual_sha256 = _calculate_sha256(file_path)
        if actual_sha256 != expected["sha256"]:
            raise KnowledgeIntegrityError(f"发行文件 SHA-256 不匹配：{relative_path}")

    try:
        discover_catalog(root)
    except (KnowledgeLoadError, OSError, ValueError) as exc:
        raise KnowledgeIntegrityError(f"随包知识库结构验证失败：{exc}") from exc

    knowledge_manifest = _read_json_file(root / "manifest.json")
    if knowledge_manifest.get("version") != distribution.knowledge_version:
        raise KnowledgeIntegrityError("知识库版本与发行完整性清单不一致。")

    return distribution
