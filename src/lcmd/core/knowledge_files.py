from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path


class KnowledgeFilesError(RuntimeError):
    """知识库文件清单或目录身份检查失败。"""


_HASH_CHUNK_SIZE = 1024 * 1024
_REPARSE_POINT_ATTRIBUTE = 0x0400


def is_reparse_point(metadata: os.stat_result) -> bool:
    """识别符号链接及 Windows 重解析点。"""
    attributes = getattr(metadata, "st_file_attributes", 0)

    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & _REPARSE_POINT_ATTRIBUTE)


def get_directory_identity(path: Path) -> dict[str, int]:
    """获取目录身份，用于事务恢复时识别原目录。"""
    try:
        metadata = path.stat()

        if not stat.S_ISDIR(metadata.st_mode):
            raise KnowledgeFilesError("旧知识库路径不是目录。")

        return {
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
        }

    except KnowledgeFilesError:
        raise
    except OSError as exc:
        raise KnowledgeFilesError("无法读取旧知识库的目录身份。") from exc


def get_file_manifest(
    root: Path,
) -> tuple[dict[str, str], tuple[str, ...]]:
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

                if is_reparse_point(metadata):
                    raise KnowledgeFilesError(f"知识库中不允许存在符号链接或重解析点：{relative}")

                if stat.S_ISDIR(metadata.st_mode):
                    directories.append(relative)
                    scan_directory(path)
                    continue

                if not stat.S_ISREG(metadata.st_mode):
                    raise KnowledgeFilesError(f"知识库中存在不支持的文件类型：{relative}")

                digest = hashlib.sha256()

                with path.open("rb") as file:
                    while chunk := file.read(_HASH_CHUNK_SIZE):
                        digest.update(chunk)

                files[relative] = digest.hexdigest()

        except KnowledgeFilesError:
            raise
        except OSError as exc:
            raise KnowledgeFilesError("无法读取知识库文件，文件清单生成失败。") from exc

    try:
        if not root.is_dir():
            raise KnowledgeFilesError("知识库目录不存在或无法访问。")

        scan_directory(root)

    except KnowledgeFilesError:
        raise
    except OSError as exc:
        raise KnowledgeFilesError("无法读取知识库目录，文件清单生成失败。") from exc

    return files, tuple(sorted(directories, key=str.casefold))
