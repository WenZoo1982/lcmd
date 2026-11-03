from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import warnings
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path, PurePosixPath

from lcmd.core.config import AppConfig, ConfigError, load_config, save_config
from lcmd.core.path_security import (
    PathSecurityError,
    validate_knowledge_path,
    validate_migration_target,
)


class MigrationError(RuntimeError):
    """知识库迁移失败。"""


class MigrationConfirmationRequired(MigrationError):
    """目标目录已存在，需要用户明确确认覆盖。"""


class MigrationCleanupWarning(UserWarning):
    """知识库迁移成功，但旧知识库未能完全清理。"""


ProgressCallback = Callable[[int, int], None]

_JOURNAL_NAME = ".lcmd-migration.json"
_HASH_CHUNK_SIZE = 1024 * 1024
_REPARSE_POINT_ATTRIBUTE = 0x0400


def _is_reparse_point(metadata: os.stat_result) -> bool:
    """识别符号链接及 Windows 重解析点。"""
    attributes = getattr(metadata, "st_file_attributes", 0)

    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & _REPARSE_POINT_ATTRIBUTE)


def _get_directory_identity(path: Path) -> dict[str, int]:
    """获取目录身份，用于恢复时识别原目录。"""
    try:
        metadata = path.stat()

        if not stat.S_ISDIR(metadata.st_mode):
            raise MigrationError("旧知识库路径不是目录。")

        return {
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
        }

    except OSError as exc:
        raise MigrationError("无法读取旧知识库的目录身份。") from exc


def _get_file_manifest(root: Path) -> tuple[dict[str, str], tuple[str, ...]]:
    """生成文件 SHA-256 清单和目录清单，拒绝链接及特殊文件。"""
    files: dict[str, str] = {}
    directories: list[str] = []

    def scan_directory(directory: Path) -> None:
        try:
            entries = sorted(
                os.scandir(directory),
                key=lambda entry: entry.name.casefold(),
            )

            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                metadata = entry.stat(follow_symlinks=False)

                if _is_reparse_point(metadata):
                    raise MigrationError(f"知识库中不允许存在符号链接或重解析点：{relative}")

                if stat.S_ISDIR(metadata.st_mode):
                    directories.append(relative)
                    scan_directory(path)
                    continue

                if not stat.S_ISREG(metadata.st_mode):
                    raise MigrationError(f"知识库中存在不支持的文件类型：{relative}")

                digest = hashlib.sha256()

                with path.open("rb") as file:
                    while chunk := file.read(_HASH_CHUNK_SIZE):
                        digest.update(chunk)

                files[relative] = digest.hexdigest()

        except MigrationError:
            raise
        except OSError as exc:
            raise MigrationError("无法读取知识库文件，迁移已停止。") from exc

    if not root.is_dir():
        raise MigrationError("知识库目录不存在或无法访问。")

    scan_directory(root)

    return files, tuple(sorted(directories, key=str.casefold))


def _manifest_to_dict(
    manifest: tuple[dict[str, str], tuple[str, ...]],
) -> dict[str, object]:
    """将文件清单转换为可写入迁移日志的数据。"""
    files, directories = manifest

    return {
        "files": files,
        "directories": list(directories),
    }


def _manifest_from_dict(
    data: object,
) -> tuple[dict[str, str], tuple[str, ...]]:
    """读取并严格验证迁移日志中的文件清单。"""
    if not isinstance(data, dict) or set(data) != {"files", "directories"}:
        raise MigrationError("迁移记录中的文件清单格式无效。")

    raw_files = data["files"]
    raw_directories = data["directories"]

    if not isinstance(raw_files, dict) or not isinstance(raw_directories, list):
        raise MigrationError("迁移记录中的文件清单格式无效。")

    files: dict[str, str] = {}

    for relative, digest in raw_files.items():
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise MigrationError("迁移记录中的文件信息无效。")

        relative_path = PurePosixPath(relative)

        if (
            relative_path.is_absolute()
            or not relative_path.parts
            or any(part in {"", ".", ".."} for part in relative_path.parts)
            or "\\" in relative
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise MigrationError("迁移记录中的文件路径或校验值无效。")

        if relative in files:
            raise MigrationError("迁移记录中存在重复文件路径。")

        files[relative] = digest

    directories: list[str] = []

    for relative in raw_directories:
        if not isinstance(relative, str):
            raise MigrationError("迁移记录中的目录信息无效。")

        relative_path = PurePosixPath(relative)

        if (
            relative_path.is_absolute()
            or not relative_path.parts
            or any(part in {"", ".", ".."} for part in relative_path.parts)
            or "\\" in relative
        ):
            raise MigrationError("迁移记录中的目录路径无效。")

        if relative in directories:
            raise MigrationError("迁移记录中存在重复目录路径。")

        directories.append(relative)

    return files, tuple(sorted(directories, key=str.casefold))


def _write_journal(
    config_path: Path,
    source: Path,
    target: Path,
    state: str,
    source_manifest: tuple[dict[str, str], tuple[str, ...]] | None = None,
    source_identity: dict[str, int] | None = None,
) -> None:
    """原子写入迁移记录，独立保存新旧路径、文件清单和旧目录身份。"""
    journal_path = config_path.parent / _JOURNAL_NAME
    temporary_path: Path | None = None

    if source_manifest is None:
        source_manifest = _get_file_manifest(source)

    if source_identity is None:
        # 更新迁移状态时优先保留首次记录的目录身份，
        # 避免后续状态写入意外改变身份基准。
        try:
            old_data = json.loads(journal_path.read_text(encoding="utf-8"))
            old_identity = old_data.get("source_identity")

            if (
                isinstance(old_identity, dict)
                and set(old_identity) == {"device", "inode"}
                and all(
                    isinstance(value, int) and not isinstance(value, bool)
                    for value in old_identity.values()
                )
            ):
                source_identity = old_identity
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            pass

    if source_identity is None:
        source_identity = _get_directory_identity(source)

    content = json.dumps(
        {
            "source": str(source),
            "target": str(target),
            "state": state,
            "source_identity": source_identity,
            "source_manifest": _manifest_to_dict(source_manifest),
        },
        ensure_ascii=False,
        indent=2,
    )

    try:
        journal_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=journal_path.parent,
            prefix=".lcmd-migration.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, journal_path)

    except OSError as exc:
        raise MigrationError("无法保存迁移状态记录。") from exc

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _remove_journal(config_path: Path) -> None:
    """删除迁移状态记录。"""
    try:
        (config_path.parent / _JOURNAL_NAME).unlink(missing_ok=True)
    except OSError as exc:
        raise MigrationError("迁移记录无法清理，请检查配置目录权限。") from exc


def _copy_knowledge(
    source: Path,
    target: Path,
    progress_callback: ProgressCallback | None,
) -> None:
    """复制知识库并报告总体字节进度。"""
    source_files, _ = _get_file_manifest(source)
    total_bytes = sum((source / name).stat().st_size for name in source_files)
    copied_bytes = 0

    def copy_file(source_file: str, target_file: str) -> str:
        nonlocal copied_bytes

        result = shutil.copy2(source_file, target_file)
        copied_bytes += Path(source_file).stat().st_size

        if progress_callback is not None:
            progress_callback(copied_bytes, total_bytes)

        return result

    try:
        shutil.copytree(
            source,
            target,
            copy_function=copy_file,
        )

        if progress_callback is not None and total_bytes == 0:
            progress_callback(0, 0)

    except Exception as exc:
        if isinstance(exc, MigrationError):
            raise
        raise MigrationError("知识库复制失败，原知识库和配置保持不变。") from exc


def _verify_copy(source: Path, target: Path) -> None:
    """比较源和目标的目录清单及文件 SHA-256。"""
    source_files, source_directories = _get_file_manifest(source)
    target_files, target_directories = _get_file_manifest(target)

    if source_directories != target_directories:
        raise MigrationError("迁移完整性检查失败：目录结构不一致。")

    if source_files != target_files:
        raise MigrationError("迁移完整性检查失败：文件内容或文件清单不一致。")

    try:
        validate_knowledge_path(target)
    except PathSecurityError as exc:
        raise MigrationError(f"迁移目标知识库验证失败：{exc}") from exc


def _validate_source_snapshot(
    source: Path,
    expected: tuple[dict[str, str], tuple[str, ...]],
    *,
    allow_partial: bool,
) -> None:
    """核对旧知识库是否仍与迁移记录相符。"""
    actual_files, actual_directories = _get_file_manifest(source)
    expected_files, expected_directories = expected

    if not set(actual_files).issubset(expected_files):
        raise MigrationError("旧知识库出现迁移记录中不存在的文件，拒绝自动删除。")

    if not set(actual_directories).issubset(expected_directories):
        raise MigrationError("旧知识库出现迁移记录中不存在的目录，拒绝自动删除。")

    for relative, digest in actual_files.items():
        if expected_files[relative] != digest:
            raise MigrationError(f"旧知识库文件与迁移记录不一致，拒绝自动删除：{relative}")

    if not allow_partial:
        if actual_files != expected_files or actual_directories != expected_directories:
            raise MigrationError("旧知识库内容在迁移期间发生变化，拒绝自动删除。")


def _warn_cleanup_pending(source: Path, target: Path, reason: str) -> None:
    """迁移成功但旧知识库清理失败时，向调用方发出可见警告。"""
    message = (
        "知识库迁移已完成，但旧知识库无法完全删除。\n\n"
        f"旧知识库路径：\n{source}\n\n"
        f"新知识库路径：\n{target}\n\n"
        f"可能原因：{reason}\n\n"
        "建议：\n"
        "1. 关闭正在使用旧知识库的程序。\n"
        "2. 如果仍无法删除，请重启 Windows。\n"
        "3. 重启后手动删除上述旧知识库目录。\n\n"
        "当前 LCMD 已经使用新的知识库路径，不影响正常使用。"
    )

    warnings.warn(message, MigrationCleanupWarning, stacklevel=2)


def _try_cleanup_source(
    source: Path,
    target: Path,
    expected_manifest: tuple[dict[str, str], tuple[str, ...]],
    expected_identity: dict[str, int],
    *,
    protected_paths: Iterable[str | os.PathLike[str]] | None,
) -> bool:
    """安全验证后尽力删除旧知识库。"""
    try:
        safe_source = validate_migration_target(
            source,
            target,
            protected_paths=protected_paths,
        )

        if _get_directory_identity(safe_source) != expected_identity:
            raise MigrationError("旧知识库目录身份发生变化，拒绝自动删除。")

        _validate_source_snapshot(
            safe_source,
            expected_manifest,
            allow_partial=False,
        )

        shutil.rmtree(safe_source)
        return True

    except (OSError, PathSecurityError, MigrationError):
        return False


def migrate_knowledge(
    config_path: Path,
    target_path: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    progress_callback: ProgressCallback | None = None,
    protected_paths: Iterable[str | os.PathLike[str]] | None = None,
) -> AppConfig:
    """迁移知识库；验证和配置切换成功后尽力清理旧知识库。"""
    config_path = Path(config_path)

    try:
        config = load_config(config_path)

        if config.knowledge_path is None:
            raise MigrationError("当前配置没有指定知识库路径。")

        source = validate_knowledge_path(
            config.knowledge_path,
            protected_paths=protected_paths,
        )

        target = validate_migration_target(
            target_path,
            source,
            protected_paths=protected_paths,
        )

        source_manifest = _get_file_manifest(source)
        source_identity = _get_directory_identity(source)

    except (ConfigError, PathSecurityError) as exc:
        raise MigrationError(str(exc)) from exc

    if target.exists() and not overwrite:
        raise MigrationConfirmationRequired(
            "迁移目标目录已经存在。覆盖将删除该目录及其全部原有内容；"
            "请在用户明确确认后重新执行迁移。"
        )

    try:
        # 在任何目标目录删除操作之前保存旧路径、清单和目录身份。
        _write_journal(
            config_path,
            source,
            target,
            "copying",
            source_manifest,
            source_identity,
        )

        if target.exists():
            shutil.rmtree(target)

        _copy_knowledge(source, target, progress_callback)
        _verify_copy(source, target)

        _write_journal(
            config_path,
            source,
            target,
            "ready_to_switch",
            source_manifest,
            source_identity,
        )

        new_config = replace(config, knowledge_path=target)
        save_config(new_config, config_path)

    except MigrationError:
        raise
    except (OSError, ConfigError) as exc:
        raise MigrationError(
            "知识库迁移未能完成。原知识库不会因复制或配置保存失败而被主动删除；"
            "请检查配置和迁移记录后再恢复。"
        ) from exc

    # 配置切换已经成功。此后的清理失败不再判定迁移失败。
    try:
        _write_journal(
            config_path,
            source,
            target,
            "switched",
            source_manifest,
            source_identity,
        )
    except MigrationError:
        # ready_to_switch 记录仍然存在，可在下次恢复时判断配置状态。
        pass

    if not _try_cleanup_source(
        source,
        target,
        source_manifest,
        source_identity,
        protected_paths=protected_paths,
    ):
        _warn_cleanup_pending(
            source,
            target,
            "旧目录中的文件可能正被其他程序占用，或者当前用户没有足够的删除权限。",
        )
        return new_config

    try:
        _remove_journal(config_path)
    except MigrationError:
        # 旧目录已经删除，残留记录可在下次恢复时安全清理。
        pass

    return new_config


def recover_migration(
    config_path: Path,
    *,
    protected_paths: Iterable[str | os.PathLike[str]] | None = None,
) -> bool:
    """根据迁移记录恢复迁移。

    返回 True 表示旧目录已经清理或确认不存在；
    返回 False 表示没有执行清理。
    """
    config_path = Path(config_path)
    journal_path = config_path.parent / _JOURNAL_NAME

    if not journal_path.is_file():
        return False

    try:
        data = json.loads(journal_path.read_text(encoding="utf-8"))

        if not isinstance(data, dict) or set(data) != {
            "source",
            "target",
            "state",
            "source_identity",
            "source_manifest",
        }:
            raise MigrationError("迁移记录格式无效。")

        if not isinstance(data["source"], str) or not isinstance(data["target"], str):
            raise MigrationError("迁移记录中的路径格式无效。")

        source = Path(data["source"])
        target = Path(data["target"])
        state = data["state"]

        if not isinstance(state, str) or state not in {
            "copying",
            "ready_to_switch",
            "switched",
        }:
            raise MigrationError("迁移记录状态无效。")

        source_identity = data["source_identity"]

        if (
            not isinstance(source_identity, dict)
            or set(source_identity) != {"device", "inode"}
            or any(
                not isinstance(value, int) or isinstance(value, bool)
                for value in source_identity.values()
            )
        ):
            raise MigrationError("迁移记录中的旧目录身份无效。")

        source_manifest = _manifest_from_dict(data["source_manifest"])

    except MigrationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise MigrationError("无法读取迁移记录，拒绝自动清理。") from exc

    # 配置文件可能已经丢失，但迁移日志仍保留新旧路径。
    # 没有配置证据时，绝不自动删除旧知识库。
    try:
        config = load_config(config_path)
    except (OSError, ConfigError) as exc:
        raise MigrationError(
            "无法读取当前配置，不能确认当前正在使用的知识库。\n"
            f"旧知识库路径：{source}\n"
            f"新知识库路径：{target}\n"
            "迁移记录仍然保留，未自动删除任何目录。"
        ) from exc

    if config.knowledge_path is None:
        raise MigrationError(
            "当前配置没有指定知识库路径，拒绝自动清理。\n"
            f"旧知识库路径：{source}\n"
            f"新知识库路径：{target}"
        )

    try:
        configured_path = config.knowledge_path.resolve(strict=False)
        source_path = source.resolve(strict=False)
        target_path = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise MigrationError(
            f"迁移记录中的路径无法解析。\n旧知识库路径：{source}\n新知识库路径：{target}"
        ) from exc

    if configured_path == source_path:
        # 配置仍指向旧知识库，绝不删除源目录。
        _remove_journal(config_path)
        return False

    if configured_path != target_path:
        raise MigrationError(
            "当前配置与迁移记录不匹配，拒绝自动删除任何目录。\n"
            f"旧知识库路径：{source}\n"
            f"新知识库路径：{target}"
        )

    if state == "copying":
        raise MigrationError(
            "迁移记录显示复制尚未完成，拒绝自动清理。\n"
            f"旧知识库路径：{source}\n"
            f"新知识库路径：{target}"
        )

    try:
        validate_knowledge_path(
            target_path,
            protected_paths=protected_paths,
        )
    except PathSecurityError as exc:
        raise MigrationError(
            "当前配置指向的目标知识库验证失败，拒绝删除旧知识库。\n"
            f"旧知识库路径：{source}\n"
            f"新知识库路径：{target}"
        ) from exc

    if not source_path.exists():
        _remove_journal(config_path)
        return True

    try:
        safe_source = validate_migration_target(
            source_path,
            target_path,
            protected_paths=protected_paths,
        )

        actual_identity = _get_directory_identity(safe_source)

        if actual_identity != source_identity:
            raise MigrationError(f"旧知识库目录身份与迁移记录不一致，拒绝自动删除：{source_path}")

        _validate_source_snapshot(
            safe_source,
            source_manifest,
            allow_partial=True,
        )

    except PathSecurityError as exc:
        raise MigrationError(f"旧知识库路径安全检查失败，拒绝自动删除：{source_path}") from exc

    except MigrationError as exc:
        raise MigrationError(
            f"旧知识库与迁移记录不一致，拒绝自动删除：{source_path}。{exc}"
        ) from exc

    try:
        shutil.rmtree(safe_source)
    except OSError:
        _warn_cleanup_pending(
            source_path,
            target_path,
            "旧目录仍有文件被占用，或者当前用户没有足够的删除权限。",
        )
        return False

    _remove_journal(config_path)
    return True
