from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from lcmd.core.config import load_config
from lcmd.core.knowledge_files import (
    KnowledgeFilesError,
    get_directory_identity,
    get_file_manifest,
)
from lcmd.core.path_security import PathSecurityError, validate_knowledge_path
from lcmd.core.update import (
    KNOWLEDGE_REPOSITORY,
    ReleaseAsset,
    ReleaseInfo,
    UpdateCheckResult,
    UpdateStatus,
    check_for_update,
)
from lcmd.core.update_download import AssetDownloadError, download_release_asset
from lcmd.knowledge.loader import (
    KnowledgeLoadError,
    discover_catalog,
    load_knowledge,
)

_JOURNAL_NAME = ".lcmd-knowledge-update.json"
_JOURNAL_VERSION = 1

_MAX_ZIP_ENTRIES = 10_000
_MAX_FILE_SIZE = 64 * 1024 * 1024
_MAX_TOTAL_SIZE = 256 * 1024 * 1024
_COPY_CHUNK_SIZE = 1024 * 1024


class KnowledgeUpdateError(RuntimeError):
    """知识库在线更新或事务恢复失败。"""


@dataclass(frozen=True, slots=True)
class KnowledgeUpdateResult:
    """知识库更新检查及执行结果。"""

    status: UpdateStatus
    current_version: str
    latest_version: str | None = None
    release: ReleaseInfo | None = None
    updated: bool = False
    error: str | None = None


def _write_journal(config_path: Path, data: dict[str, Any]) -> None:
    """原子写入知识库更新事务日志。"""
    journal_path = config_path.parent / _JOURNAL_NAME
    temporary_path: Path | None = None

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=config_path.parent,
            prefix=f".{_JOURNAL_NAME}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(data, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, journal_path)
        temporary_path = None

    except OSError as exc:
        raise KnowledgeUpdateError("无法写入知识库更新事务日志。") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _remove_journal(config_path: Path) -> None:
    """删除已完成的事务日志。"""
    journal_path = config_path.parent / _JOURNAL_NAME

    try:
        journal_path.unlink(missing_ok=True)
    except OSError as exc:
        raise KnowledgeUpdateError("无法清理知识库更新事务日志。") from exc


def _serialize_manifest(root: Path) -> dict[str, Any]:
    """生成可写入事务日志的目录身份和文件清单。"""
    try:
        files, directories = get_file_manifest(root)
        identity = get_directory_identity(root)
    except KnowledgeFilesError as exc:
        raise KnowledgeUpdateError(f"无法验证知识库目录：{exc}") from exc

    return {
        "identity": identity,
        "files": files,
        "directories": list(directories),
    }


def _matches_manifest(path: Path, expected: Any) -> bool:
    """检查目录身份和完整文件清单是否与事务记录一致。"""
    if not isinstance(expected, dict):
        return False

    try:
        expected_identity = expected["identity"]
        expected_files = expected["files"]
        expected_directories = expected["directories"]

        if not isinstance(expected_identity, dict):
            return False
        if not isinstance(expected_files, dict):
            return False
        if not isinstance(expected_directories, list):
            return False

        actual_identity = get_directory_identity(path)
        actual_files, actual_directories = get_file_manifest(path)

        return (
            actual_identity == expected_identity
            and actual_files == expected_files
            and list(actual_directories) == expected_directories
        )
    except (KeyError, OSError, KnowledgeFilesError, TypeError, ValueError):
        return False


def _remove_verified_directory(path: Path, expected: Any) -> None:
    """仅删除身份和内容均匹配事务记录的目录。"""
    if not path.exists():
        return

    if not _matches_manifest(path, expected):
        raise KnowledgeUpdateError(f"目录内容与事务记录不一致，为避免误删已保留现场：{path}")

    try:
        shutil.rmtree(path)
    except OSError as exc:
        raise KnowledgeUpdateError(f"无法清理更新临时目录：{path}") from exc


def _validate_zip_member(info: zipfile.ZipInfo) -> tuple[str, bool]:
    """验证 ZIP 成员路径和文件类型，返回规范相对路径及目录标记。"""
    name = info.filename
    if "\\" in name:
        raise KnowledgeUpdateError(
            f"知识库 ZIP 包含不安全的路径：{name}"
        )

    if not isinstance(name, str) or not name or "\x00" in name:
        raise KnowledgeUpdateError("知识库 ZIP 中存在无效路径。")

    # ZIP 内部路径只允许使用正斜杠。
    # Windows 反斜杠可能被解释为目录分隔符，必须直接拒绝。
    if "\\" in name or name.startswith("/"):
        raise KnowledgeUpdateError(f"知识库 ZIP 中存在不安全路径：{name!r}")

    is_directory = info.is_dir()
    normalized_name = name[:-1] if is_directory else name

    if not normalized_name:
        raise KnowledgeUpdateError("知识库 ZIP 中存在无效目录路径。")

    # 必须检查原始路径段，不能只检查 PurePosixPath.parts。
    # PurePosixPath 会规范化部分路径写法，例如重复斜杠和 "."。
    raw_parts = normalized_name.split("/")

    if any(part in {"", ".", ".."} for part in raw_parts):
        raise KnowledgeUpdateError(f"知识库 ZIP 中存在不安全路径段：{name!r}")

    path = PurePosixPath(normalized_name)

    if path.is_absolute() or not path.parts:
        raise KnowledgeUpdateError(f"知识库 ZIP 中存在绝对路径：{name!r}")

    if ":" in raw_parts[0]:
        raise KnowledgeUpdateError(f"知识库 ZIP 中存在盘符或设备路径：{name!r}")

    if info.flag_bits & 0x1:
        raise KnowledgeUpdateError(f"知识库 ZIP 中不允许加密文件：{name!r}")

    if info.create_system == 3:
        unix_mode = info.external_attr >> 16
        file_type = stat.S_IFMT(unix_mode)

        if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise KnowledgeUpdateError(f"知识库 ZIP 中存在符号链接或特殊文件：{name!r}")

        if file_type == stat.S_IFDIR and not is_directory:
            raise KnowledgeUpdateError(f"知识库 ZIP 文件类型与路径不一致：{name!r}")

        if file_type == stat.S_IFREG and is_directory:
            raise KnowledgeUpdateError(f"知识库 ZIP 文件类型与路径不一致：{name!r}")

    if not is_directory and info.file_size > _MAX_FILE_SIZE:
        raise KnowledgeUpdateError(f"知识库 ZIP 中的单个文件过大：{name!r}")

    return path.as_posix(), is_directory


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    """安全解压知识库 ZIP，不使用 ZipFile.extractall。"""
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            entries = archive.infolist()

            if not entries:
                raise KnowledgeUpdateError("知识库 ZIP 文件为空。")

            if len(entries) > _MAX_ZIP_ENTRIES:
                raise KnowledgeUpdateError("知识库 ZIP 文件数量超过安全限制。")

            validated: list[tuple[zipfile.ZipInfo, str, bool]] = []
            names: dict[str, bool] = {}
            total_size = 0

            for info in entries:
                relative, is_directory = _validate_zip_member(info)
                collision_key = relative.casefold()

                if collision_key in names:
                    raise KnowledgeUpdateError(f"知识库 ZIP 中存在重复或大小写冲突路径：{relative}")

                names[collision_key] = is_directory

                if not is_directory:
                    total_size += info.file_size

                    if total_size > _MAX_TOTAL_SIZE:
                        raise KnowledgeUpdateError("知识库 ZIP 解压总大小超过安全限制。")

                validated.append((info, relative, is_directory))

            # 不允许文件同时充当其他成员的父目录。
            file_names = {
                name.casefold() for name, is_directory in names.items() if not is_directory
            }

            for _, relative, _ in validated:
                parts = PurePosixPath(relative).parts

                for index in range(1, len(parts)):
                    parent_name = PurePosixPath(*parts[:index]).as_posix().casefold()

                    if parent_name in file_names:
                        raise KnowledgeUpdateError(
                            f"知识库 ZIP 中存在文件与目录路径冲突：{relative}"
                        )

            destination.mkdir(parents=True, exist_ok=False)

            for info, relative, is_directory in validated:
                target = destination.joinpath(*PurePosixPath(relative).parts)

                if is_directory:
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)

                written = 0

                with archive.open(info, "r") as source:
                    with target.open("xb") as output:
                        while True:
                            chunk = source.read(_COPY_CHUNK_SIZE)

                            if not chunk:
                                break

                            written += len(chunk)

                            if written > info.file_size or written > _MAX_FILE_SIZE:
                                raise KnowledgeUpdateError(
                                    f"知识库 ZIP 文件实际解压大小异常：{relative}"
                                )

                            output.write(chunk)

                if written != info.file_size:
                    raise KnowledgeUpdateError(f"知识库 ZIP 文件大小不匹配：{relative}")

    except KnowledgeUpdateError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        raise KnowledgeUpdateError("知识库 ZIP 解压失败或内容损坏。") from exc


def _validate_staged_knowledge(
    stage_path: Path,
    expected_version: str,
    platform: str,
    language: str,
) -> dict[str, Any]:
    """验证新版知识库结构、版本及当前平台语言能否正常加载。"""
    try:
        catalog = discover_catalog(stage_path)

        if catalog.version != expected_version:
            raise KnowledgeUpdateError("知识库 ZIP 内的 manifest 版本与 Release 版本不一致。")

        load_knowledge(catalog, platform, language)

    except KnowledgeUpdateError:
        raise
    except (KnowledgeLoadError, OSError) as exc:
        raise KnowledgeUpdateError(f"新版知识库验证失败：{exc}") from exc

    return _serialize_manifest(stage_path)


def _read_journal(config_path: Path) -> dict[str, Any] | None:
    """读取并验证更新事务日志。"""
    journal_path = config_path.parent / _JOURNAL_NAME

    if not journal_path.exists():
        return None

    try:
        if journal_path.is_symlink() or not journal_path.is_file():
            raise KnowledgeUpdateError("知识库更新事务日志不是普通文件。")

        data = json.loads(journal_path.read_text(encoding="utf-8"))

    except KnowledgeUpdateError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise KnowledgeUpdateError(
            "知识库更新事务日志无法读取或解析；为保护现有文件，未执行自动清理。"
        ) from exc

    required = {
        "schema_version",
        "state",
        "target",
        "stage",
        "backup",
        "old",
        "new",
    }

    if (
        not isinstance(data, dict)
        or set(data) != required
        or data["schema_version"] != _JOURNAL_VERSION
        or data["state"] not in {"prepared", "old_moved", "new_installed"}
    ):
        raise KnowledgeUpdateError("知识库更新事务日志格式无效，已保留现场。")

    for key in ("target", "stage", "backup"):
        if not isinstance(data[key], str) or not data[key]:
            raise KnowledgeUpdateError("知识库更新事务日志中的路径无效。")

    return data



def recover_knowledge_update(config_path: str | os.PathLike[str]) -> None:
    """在加载知识库前恢复上次中断的更新事务。"""
    config_path = Path(config_path)
    journal = _read_journal(config_path)

    if journal is None:
        return

    target = Path(journal["target"])
    stage = Path(journal["stage"])
    backup = Path(journal["backup"])

    if target == stage or target == backup or stage == backup:
        raise KnowledgeUpdateError("知识库更新事务路径冲突，已保留现场。")

    if target.parent != stage.parent or target.parent != backup.parent:
        raise KnowledgeUpdateError("知识库更新事务目录不在同一父目录，已保留现场。")

    # 临时目录名称必须符合本模块生成的格式。
    if not stage.name.startswith(".lcmd-knowledge-stage-"):
        raise KnowledgeUpdateError("知识库更新暂存目录名称无效，已保留现场。")

    if not backup.name.startswith(".lcmd-knowledge-backup-"):
        raise KnowledgeUpdateError("知识库更新备份目录名称无效，已保留现场。")

    transaction_id_stage = stage.name.removeprefix(".lcmd-knowledge-stage-")
    transaction_id_backup = backup.name.removeprefix(".lcmd-knowledge-backup-")

    if (
        len(transaction_id_stage) != 32
        or len(transaction_id_backup) != 32
        or transaction_id_stage != transaction_id_backup
        or any(char not in "0123456789abcdef" for char in transaction_id_stage)
    ):
        raise KnowledgeUpdateError("知识库更新事务目录标识无效，已保留现场。")

    for path in (target, stage, backup):
        if path.is_symlink():
            raise KnowledgeUpdateError(f"知识库更新事务目录不允许是符号链接：{path}")

    old_record = journal["old"]
    new_record = journal["new"]

    target_exists = target.exists()
    stage_exists = stage.exists()
    backup_exists = backup.exists()

    target_is_new = target_exists and _matches_manifest(target, new_record)
    target_is_old = target_exists and _matches_manifest(target, old_record)
    backup_is_old = backup_exists and _matches_manifest(backup, old_record)

    # 新版已经处于正式路径：更新完成，清理旧备份。
    if target_is_new:
        if backup_exists:
            _remove_verified_directory(backup, old_record)

        if stage_exists:
            _remove_verified_directory(stage, new_record)

        _remove_journal(config_path)
        return

    # 正式路径缺失，但旧版备份完整：恢复旧版。
    if not target_exists and backup_is_old:
        try:
            os.replace(backup, target)
        except OSError as exc:
            raise KnowledgeUpdateError("无法恢复更新前的知识库，旧版备份仍已保留。") from exc

        if stage_exists:
            _remove_verified_directory(stage, new_record)

        _remove_journal(config_path)
        return

    # 旧版仍在正式路径：替换尚未完成，保留旧版并清理可验证的临时目录。
    if target_is_old:
        if backup_exists:
            _remove_verified_directory(backup, old_record)

        if stage_exists:
            _remove_verified_directory(stage, new_record)

        _remove_journal(config_path)
        return

    # 其他情况无法证明哪个目录安全，不做删除或覆盖。
    raise KnowledgeUpdateError(
        "知识库更新事务中的目录身份或文件清单不匹配。"
        "为避免丢失数据，已保留所有现场，请勿手动删除相关目录。"
    )


def check_knowledge_update(current_version: str) -> UpdateCheckResult:
    """检查知识库仓库的最新稳定 Release。"""
    return check_for_update(KNOWLEDGE_REPOSITORY, current_version)


def _find_knowledge_asset(release: ReleaseInfo) -> ReleaseAsset:
    """按知识库 Release 版本查找唯一 ZIP 资产。"""
    expected_name = f"lcmd-kb-{release.version}.zip"
    matches = [asset for asset in release.assets if asset.name == expected_name]

    if len(matches) != 1:
        raise KnowledgeUpdateError(f"知识库 Release 缺少唯一的发行资产：{expected_name}")

    asset = matches[0]

    if asset.digest is None:
        raise KnowledgeUpdateError("知识库 Release 资产缺少 SHA-256，拒绝更新。")

    return asset


def update_knowledge(
    config_path: str | os.PathLike[str],
) -> KnowledgeUpdateResult:
    """检查并更新配置当前指向的知识库目录。"""
    config_path = Path(config_path)

    # 先恢复历史事务，再读取当前配置。
    recover_knowledge_update(config_path)

    try:
        config = load_config(config_path)

        if config.knowledge_path is None:
            raise KnowledgeUpdateError("当前配置没有指定知识库路径。")

        knowledge_path = validate_knowledge_path(config.knowledge_path)
        catalog = discover_catalog(knowledge_path)

    except KnowledgeUpdateError:
        raise
    except (OSError, KnowledgeLoadError, PathSecurityError, ValueError) as exc:
        raise KnowledgeUpdateError(f"当前知识库不可用，无法更新：{exc}") from exc

    current_version = catalog.version
    check_result = check_knowledge_update(current_version)

    if check_result.status == UpdateStatus.CHECK_FAILED:
        raise KnowledgeUpdateError(f"知识库更新检查失败：{check_result.error or '未知错误'}")

    if check_result.status == UpdateStatus.UP_TO_DATE:
        return KnowledgeUpdateResult(
            status=UpdateStatus.UP_TO_DATE,
            current_version=current_version,
            latest_version=check_result.latest_version,
            release=check_result.release,
        )

    release = check_result.release

    if release is None:
        raise KnowledgeUpdateError("知识库更新检查结果缺少 Release 信息。")

    asset = _find_knowledge_asset(release)
    parent = knowledge_path.parent
    transaction_id = uuid.uuid4().hex

    stage_path = parent / f".lcmd-knowledge-stage-{transaction_id}"
    backup_path = parent / f".lcmd-knowledge-backup-{transaction_id}"
    archive_path = parent / f".lcmd-knowledge-download-{transaction_id}.zip"

    old_record = _serialize_manifest(knowledge_path)
    stage_record: dict[str, Any] | None = None
    journal_written = False

    try:
        download_release_asset(asset, archive_path)

        _safe_extract_zip(archive_path, stage_path)

        stage_record = _validate_staged_knowledge(
            stage_path,
            release.version,
            config.platform,
            config.language,
        )

        journal: dict[str, Any] = {
            "schema_version": _JOURNAL_VERSION,
            "state": "prepared",
            "target": str(knowledge_path),
            "stage": str(stage_path),
            "backup": str(backup_path),
            "old": old_record,
            "new": stage_record,
        }

        _write_journal(config_path, journal)
        journal_written = True

        os.replace(knowledge_path, backup_path)

        journal["state"] = "old_moved"
        _write_journal(config_path, journal)

        os.replace(stage_path, knowledge_path)

        journal["state"] = "new_installed"
        _write_journal(config_path, journal)

        if not _matches_manifest(knowledge_path, stage_record):
            raise KnowledgeUpdateError("新版知识库切换后的完整性验证失败。")

        _remove_verified_directory(backup_path, old_record)
        _remove_journal(config_path)
        journal_written = False

        return KnowledgeUpdateResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            current_version=current_version,
            latest_version=release.version,
            release=release,
            updated=True,
        )

    except (
        AssetDownloadError,
        KnowledgeUpdateError,
        OSError,
    ) as exc:
        if journal_written:
            try:
                recover_knowledge_update(config_path)
            except KnowledgeUpdateError as recovery_error:
                raise KnowledgeUpdateError(
                    f"知识库更新失败：{exc}。自动恢复也未能完成：{recovery_error}"
                ) from exc

        raise KnowledgeUpdateError(f"知识库更新失败：{exc}") from exc

    finally:
        try:
            archive_path.unlink(missing_ok=True)
        except OSError:
            pass

        # 事务日志已写入时，stage 的清理由恢复逻辑负责。
        if not journal_written and stage_record is None and stage_path.exists():
            try:
                if not stage_path.is_symlink():
                    shutil.rmtree(stage_path)
            except OSError:
                pass
