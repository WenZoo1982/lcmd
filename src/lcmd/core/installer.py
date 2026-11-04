from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from lcmd.core.path_security import (
    PathSecurityError,
    validate_knowledge_destination,
    validate_knowledge_path,
)
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


class InstallerError(ValueError):
    """安装器操作失败。"""


@dataclass(frozen=True)
class DistributionInfo:
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
            raise InstallerError(f"JSON 中存在重复字段：{key}")
        result[key] = value

    return result


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise InstallerError(f"无法读取文件：{path}") from exc

    if not stat.S_ISREG(file_stat.st_mode):
        raise InstallerError(f"不是普通文件：{path}")

    if _is_reparse_point(file_stat):
        raise InstallerError(f"不允许使用符号链接或重解析点：{path}")

    try:
        content = path.read_text(encoding="utf-8-sig")
        data = json.loads(
            content,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except InstallerError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallerError(f"JSON 文件无效：{path}") from exc

    if not isinstance(data, dict):
        raise InstallerError(f"JSON 顶层必须是对象：{path}")

    return data


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    attributes = getattr(file_stat, "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _validate_integrity_manifest(data: dict[str, Any]) -> DistributionInfo:
    if set(data) != _INTEGRITY_FIELDS:
        raise InstallerError("发行完整性清单字段不符合要求。")

    schema_version = data["schema_version"]
    if isinstance(schema_version, bool) or schema_version != 1:
        raise InstallerError("不支持的发行完整性清单版本。")

    main_version = data["main_version"]
    if not isinstance(main_version, str) or not _VERSION_PATTERN.fullmatch(main_version):
        raise InstallerError("主程序版本号格式无效。")

    main_prerelease = data["main_prerelease"]
    if not isinstance(main_prerelease, str) or not _PRERELEASE_PATTERN.fullmatch(main_prerelease):
        raise InstallerError("主程序预发布版本标识无效。")

    knowledge_version = data["knowledge_version"]
    if not isinstance(knowledge_version, str) or not _VERSION_PATTERN.fullmatch(knowledge_version):
        raise InstallerError("知识库版本号格式无效。")

    archive_sha256 = data["knowledge_archive_sha256"]
    if not isinstance(archive_sha256, str) or not _SHA256_PATTERN.fullmatch(archive_sha256):
        raise InstallerError("知识库压缩包 SHA-256 格式无效。")

    file_count = data["file_count"]
    if isinstance(file_count, bool) or not isinstance(file_count, int) or file_count < 0:
        raise InstallerError("发行文件数量无效。")

    files = data["files"]
    if not isinstance(files, list):
        raise InstallerError("发行文件清单必须是数组。")

    if len(files) != file_count:
        raise InstallerError("发行文件数量与清单记录数量不一致。")

    return DistributionInfo(
        main_version=main_version,
        main_prerelease=main_prerelease,
        knowledge_version=knowledge_version,
        knowledge_archive_sha256=archive_sha256,
        file_count=file_count,
    )


def _validate_relative_file_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise InstallerError("发行文件路径必须是非空字符串。")

    if "\\" in value or "\x00" in value:
        raise InstallerError(f"发行文件路径格式无效：{value!r}")

    path = PurePosixPath(value)

    if path.is_absolute() or not path.parts:
        raise InstallerError(f"发行文件路径必须是相对路径：{value!r}")

    if any(part in {"", ".", ".."} for part in path.parts):
        raise InstallerError(f"发行文件路径包含非法目录：{value!r}")

    if path.as_posix() != value:
        raise InstallerError(f"发行文件路径不是规范格式：{value!r}")

    for part in path.parts:
        if part.endswith((" ", ".")):
            raise InstallerError(f"发行文件路径包含 Windows 不安全名称：{value!r}")

        if ":" in part:
            raise InstallerError(f"发行文件路径包含非法字符：{value!r}")

        device_name = part.split(".", 1)[0].upper()
        if device_name in _WINDOWS_RESERVED_NAMES:
            raise InstallerError(f"发行文件路径使用了 Windows 保留名称：{value!r}")

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
                    raise InstallerError(f"无法检查知识库目录：{directory_path}") from exc

                if not stat.S_ISDIR(directory_stat.st_mode) or _is_reparse_point(directory_stat):
                    raise InstallerError(f"知识库中存在符号链接或非普通目录：{directory_path}")

            for file_name in file_names:
                file_path = current_path / file_name

                try:
                    file_stat = file_path.lstat()
                except OSError as exc:
                    raise InstallerError(f"无法检查知识库文件：{file_path}") from exc

                if not stat.S_ISREG(file_stat.st_mode) or _is_reparse_point(file_stat):
                    raise InstallerError(f"知识库中存在符号链接或非普通文件：{file_path}")

                relative_path = file_path.relative_to(root).as_posix()
                _validate_relative_file_path(relative_path)

                folded = relative_path.casefold()
                if folded in folded_paths:
                    raise InstallerError(
                        "知识库中存在大小写不敏感的路径冲突："
                        f"{folded_paths[folded]} 与 {relative_path}"
                    )

                folded_paths[folded] = relative_path
                actual_files[relative_path] = file_path

    except OSError as exc:
        raise InstallerError(f"无法遍历知识库目录：{root}") from exc

    return actual_files


def _calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    try:
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise InstallerError(f"无法读取发行文件：{path}") from exc

    return digest.hexdigest()


def verify_knowledge_distribution(
    knowledge_dir: str | os.PathLike[str],
    integrity_file: str | os.PathLike[str] | None = None,
) -> DistributionInfo:
    """验证随包知识库的结构、文件集合、大小和 SHA-256。

    该函数只读取文件，不创建、删除或修改任何文件。

    integrity_file 未指定时，默认读取知识库目录的上一级目录中的
    knowledge-integrity.json。
    """
    root = Path(knowledge_dir)

    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise InstallerError(f"知识库目录不存在或无法访问：{root}") from exc

    if not stat.S_ISDIR(root_stat.st_mode) or _is_reparse_point(root_stat):
        raise InstallerError(f"知识库路径不是普通目录：{root}")

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
            raise InstallerError("发行文件记录字段不符合要求。")

        relative_path = _validate_relative_file_path(item["path"])

        folded = relative_path.casefold()
        if folded in folded_paths:
            raise InstallerError(
                f"发行清单中存在大小写不敏感的路径冲突：{folded_paths[folded]} 与 {relative_path}"
            )

        folded_paths[folded] = relative_path

        size = item["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise InstallerError(f"发行文件大小无效：{relative_path}")

        sha256 = item["sha256"]
        if not isinstance(sha256, str) or not _SHA256_PATTERN.fullmatch(sha256):
            raise InstallerError(f"发行文件 SHA-256 无效：{relative_path}")

        expected_files[relative_path] = item

    actual_files = _collect_actual_files(root)

    expected_paths = set(expected_files)
    actual_paths = set(actual_files)

    missing_files = sorted(expected_paths - actual_paths)
    extra_files = sorted(actual_paths - expected_paths)

    if missing_files:
        raise InstallerError("知识库缺少发行文件：" + ", ".join(missing_files[:10]))

    if extra_files:
        raise InstallerError("知识库包含清单之外的文件：" + ", ".join(extra_files[:10]))

    for relative_path, expected in expected_files.items():
        file_path = actual_files[relative_path]

        try:
            actual_size = file_path.stat().st_size
        except OSError as exc:
            raise InstallerError(f"无法读取文件大小：{relative_path}") from exc

        if actual_size != expected["size"]:
            raise InstallerError(f"发行文件大小不匹配：{relative_path}")

        actual_sha256 = _calculate_sha256(file_path)
        if actual_sha256 != expected["sha256"]:
            raise InstallerError(f"发行文件 SHA-256 不匹配：{relative_path}")

    try:
        discover_catalog(root)
    except (KnowledgeLoadError, OSError, ValueError) as exc:
        raise InstallerError(f"随包知识库结构验证失败：{exc}") from exc

    knowledge_manifest = _read_json_file(root / "manifest.json")
    if knowledge_manifest.get("version") != distribution.knowledge_version:
        raise InstallerError("知识库版本与发行完整性清单不一致。")

    return distribution


class KnowledgeDestinationState(str, Enum):
    """知识库部署目标目录状态。"""

    MISSING = "missing"
    EMPTY = "empty"
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class KnowledgeDestinationInspection:
    """知识库部署目标目录检查结果。"""

    path: Path
    state: KnowledgeDestinationState
    reason: str | None = None


def inspect_knowledge_destination(
    path: str | os.PathLike[str],
) -> KnowledgeDestinationInspection:
    """只读检查知识库部署目标目录状态。

    不创建、删除、覆盖或修改任何文件。
    """
    try:
        destination = validate_knowledge_destination(path)
    except PathSecurityError as exc:
        raise InstallerError(f"知识库目标路径不安全：{exc}") from exc

    if not destination.exists():
        return KnowledgeDestinationInspection(
            path=destination,
            state=KnowledgeDestinationState.MISSING,
        )

    try:
        has_content = next(destination.iterdir(), None) is not None
    except OSError as exc:
        raise InstallerError(f"无法读取知识库目标目录：{destination}") from exc

    if not has_content:
        return KnowledgeDestinationInspection(
            path=destination,
            state=KnowledgeDestinationState.EMPTY,
        )

    try:
        validate_knowledge_path(destination)
    except (PathSecurityError, OSError, ValueError) as exc:
        return KnowledgeDestinationInspection(
            path=destination,
            state=KnowledgeDestinationState.INVALID,
            reason=str(exc),
        )

    return KnowledgeDestinationInspection(
        path=destination,
        state=KnowledgeDestinationState.VALID,
    )


def deploy_knowledge_distribution(
    source_dir: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    integrity_file: str | os.PathLike[str],
    *,
    replace_existing: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> DistributionInfo:
    """将经过验证的发行知识库部署到指定目录。

    目标目录不存在或为空时直接部署。
    目标目录非空时，必须明确授权替换。

    progress_callback 接收两个参数：
    已复制字节数、源文件总字节数。

    部署完成后再次验证目标目录。
    本函数不修改配置文件。
    """
    source = Path(source_dir)
    manifest = Path(integrity_file)

    # 首先验证发行包，确保源文件完整后才允许处理目标目录。
    verify_knowledge_distribution(
        source,
        manifest,
    )

    # 防止源目录与部署目标相互包含。
    try:
        source_resolved = source.resolve(strict=True)
        destination_resolved = Path(destination).expanduser().resolve(strict=False)

        if (
            source_resolved == destination_resolved
            or source_resolved in destination_resolved.parents
            or destination_resolved in source_resolved.parents
        ):
            raise InstallerError("发行知识库目录与部署目标不能相互包含。")

    except InstallerError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise InstallerError("无法规范化知识库部署路径。") from exc

    # 收集源文件并计算实际复制总量。
    source_files = _collect_actual_files(source_resolved)

    try:
        total_bytes = sum(
            file_path.stat().st_size
            for file_path in source_files.values()
        )
    except OSError as exc:
        raise InstallerError("无法统计发行知识库文件大小。") from exc

    copied_bytes = 0

    def copy_file(source_file: str, destination_file: str) -> str:
        nonlocal copied_bytes

        copied_path = shutil.copy2(source_file, destination_file)

        try:
            copied_bytes += Path(source_file).stat().st_size

            if progress_callback is not None:
                progress_callback(copied_bytes, total_bytes)

        except Exception as exc:
            raise InstallerError("知识库部署进度回调执行失败。") from exc

        return copied_path

    # 首次安装时，默认知识库目录的父目录可能不存在。
    try:
        destination_resolved.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as exc:
        raise InstallerError(
            f"无法创建知识库目标的父目录：{destination_resolved.parent}"
        ) from exc

    # 创建父目录后，再使用现有安全校验函数检查完整目标路径。
    inspection = inspect_knowledge_destination(destination_resolved)
    target = inspection.path

    if (
        inspection.state
        in {
            KnowledgeDestinationState.VALID,
            KnowledgeDestinationState.INVALID,
        }
        and not replace_existing
    ):
        raise InstallerError(
            "知识库目标目录已经包含文件，必须明确确认替换后才能继续。"
        )

    # 只有明确授权替换时，才删除非空目标目录。
    try:
        if inspection.state in {
            KnowledgeDestinationState.VALID,
            KnowledgeDestinationState.INVALID,
        }:
            shutil.rmtree(target)

        elif inspection.state is KnowledgeDestinationState.EMPTY:
            target.rmdir()

    except OSError as exc:
        raise InstallerError(f"无法清理原知识库目标目录：{target}") from exc

    # 复制发行知识库，并报告实际复制进度。
    try:
        shutil.copytree(
            source_resolved,
            target,
            copy_function=copy_file,
        )

        # 使用发行包原始完整性清单验证部署结果。
        deployed_distribution = verify_knowledge_distribution(
            target,
            manifest,
        )

    except (OSError, InstallerError) as exc:
        # 部署失败时清理本次产生的不完整目标。
        # 不恢复已经明确授权替换的旧目标目录。
        if target.exists():
            try:
                shutil.rmtree(target)
            except OSError:
                pass

        if isinstance(exc, InstallerError):
            raise

        raise InstallerError(f"知识库部署失败：{exc}") from exc

    return deployed_distribution