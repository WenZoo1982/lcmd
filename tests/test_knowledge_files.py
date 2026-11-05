
import hashlib
import os

import pytest

from lcmd.core.knowledge_files import (
    KnowledgeFilesError,
    get_directory_identity,
    get_file_manifest,
    is_reparse_point,
)


def test_get_file_manifest_returns_hashes_and_sorted_directories(tmp_path):
    root = tmp_path / "knowledge"
    nested = root / "commands" / "platforms" / "linux"

    nested.mkdir(parents=True)
    (root / "manifest.json").write_text(
        '{"version": "0.1.0"}',
        encoding="utf-8",
    )
    (nested / "ls.md").write_text(
        "列出目录内容",
        encoding="utf-8",
    )

    files, directories = get_file_manifest(root)

    assert files == {
        "manifest.json": hashlib.sha256(
            b'{"version": "0.1.0"}'
        ).hexdigest(),
        "commands/platforms/linux/ls.md": hashlib.sha256(
            "列出目录内容".encode()
        ).hexdigest(),
    }

    assert directories == (
        "commands",
        "commands/platforms",
        "commands/platforms/linux",
    )


def test_get_file_manifest_rejects_missing_directory(tmp_path):
    with pytest.raises(KnowledgeFilesError, match="目录不存在"):
        get_file_manifest(tmp_path / "missing")


def test_get_directory_identity_returns_directory_identity(tmp_path):
    directory = tmp_path / "knowledge"
    directory.mkdir()

    identity = get_directory_identity(directory)

    assert set(identity) == {"device", "inode"}
    assert all(isinstance(value, int) for value in identity.values())


def test_get_directory_identity_rejects_file(tmp_path):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("content", encoding="utf-8")

    with pytest.raises(KnowledgeFilesError, match="不是目录"):
        get_directory_identity(file_path)


def test_get_file_manifest_rejects_symlink(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()

    target = tmp_path / "target.txt"
    target.write_text("outside", encoding="utf-8")

    link = root / "link.txt"

    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建符号链接")

    with pytest.raises(KnowledgeFilesError, match="符号链接"):
        get_file_manifest(root)


def test_is_reparse_point_recognizes_regular_file_as_false(tmp_path):
    file_path = tmp_path / "regular.txt"
    file_path.write_text("content", encoding="utf-8")

    metadata = file_path.lstat()

    assert is_reparse_point(metadata) is False


def test_get_file_manifest_rejects_special_file(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows 环境不支持此测试所需的 FIFO 文件")


    root = tmp_path / "knowledge"
    root.mkdir()

    fifo = root / "special"
    os.mkfifo(fifo)

    with pytest.raises(KnowledgeFilesError, match="不支持的文件类型"):
        get_file_manifest(root)
