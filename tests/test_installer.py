from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lcmd.core.installer import (
    InstallerError,
    KnowledgeDestinationState,
    deploy_knowledge_distribution,
    inspect_knowledge_destination,
    verify_knowledge_distribution,
)


def _write_distribution(
    base_dir: Path,
) -> tuple[Path, Path]:
    knowledge_dir = base_dir / "knowledge"
    command_file = knowledge_dir / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md"

    command_file.parent.mkdir(parents=True)
    command_file.write_text(
        "# ls\n\n列出目录内容。\n",
        encoding="utf-8",
    )

    (knowledge_dir / "manifest.json").write_text(
        json.dumps({"version": "0.1.0"}, ensure_ascii=False),
        encoding="utf-8",
    )

    files = []
    for path in sorted(knowledge_dir.rglob("*")):
        if not path.is_file():
            continue

        content = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(knowledge_dir).as_posix(),
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    integrity_file = base_dir / "knowledge-integrity.json"
    integrity_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "main_version": "0.1.0",
                "main_prerelease": "beta.1",
                "knowledge_version": "0.1.0",
                "knowledge_archive_sha256": "0" * 64,
                "file_count": len(files),
                "files": files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return knowledge_dir, integrity_file


def _file_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


# ---------------------------------------------------------------------------
# 发行知识库完整性验证
# ---------------------------------------------------------------------------


def test_verify_valid_distribution(tmp_path: Path) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    result = verify_knowledge_distribution(
        knowledge_dir,
        integrity_file,
    )

    assert result.main_version == "0.1.0"
    assert result.main_prerelease == "beta.1"
    assert result.knowledge_version == "0.1.0"
    assert result.file_count == 2


def test_verify_rejects_modified_file(tmp_path: Path) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    command_file = knowledge_dir / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md"
    command_file.write_text("# 已修改\n", encoding="utf-8")

    with pytest.raises(InstallerError, match="大小|SHA-256"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_rejects_extra_file(tmp_path: Path) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    (knowledge_dir / "unexpected.txt").write_text(
        "extra",
        encoding="utf-8",
    )

    with pytest.raises(InstallerError, match="清单之外"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_rejects_missing_file(tmp_path: Path) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    command_file = knowledge_dir / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md"
    command_file.unlink()

    with pytest.raises(InstallerError, match="缺少发行文件"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_rejects_knowledge_version_mismatch(
    tmp_path: Path,
) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    data = json.loads(integrity_file.read_text(encoding="utf-8"))
    data["knowledge_version"] = "0.2.0"
    integrity_file.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    with pytest.raises(InstallerError, match="版本"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_rejects_invalid_manifest_schema(
    tmp_path: Path,
) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    data = json.loads(integrity_file.read_text(encoding="utf-8"))
    data["unexpected_field"] = True
    integrity_file.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    with pytest.raises(InstallerError, match="字段"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_rejects_invalid_relative_path(
    tmp_path: Path,
) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    data = json.loads(integrity_file.read_text(encoding="utf-8"))
    data["files"][0]["path"] = "../outside.txt"
    integrity_file.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    with pytest.raises(InstallerError, match="非法目录"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_does_not_modify_distribution(
    tmp_path: Path,
) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    before = _file_hashes(knowledge_dir)

    verify_knowledge_distribution(knowledge_dir, integrity_file)

    after = _file_hashes(knowledge_dir)

    assert after == before


# ---------------------------------------------------------------------------
# 知识库目标目录检查
# ---------------------------------------------------------------------------


def test_inspect_missing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "missing"

    result = inspect_knowledge_destination(destination)

    assert result.state is KnowledgeDestinationState.MISSING
    assert result.path == destination
    assert not destination.exists()


def test_inspect_empty_destination(tmp_path: Path) -> None:
    destination = tmp_path / "empty"
    destination.mkdir()

    result = inspect_knowledge_destination(destination)

    assert result.state is KnowledgeDestinationState.EMPTY
    assert list(destination.iterdir()) == []


def test_inspect_valid_knowledge_destination(tmp_path: Path) -> None:
    destination, _ = _write_distribution(tmp_path)

    result = inspect_knowledge_destination(destination)

    assert result.state is KnowledgeDestinationState.VALID
    assert result.reason is None


def test_inspect_invalid_nonempty_destination(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()

    existing_file = destination / "important.txt"
    existing_file.write_text("保留原始数据", encoding="utf-8")

    result = inspect_knowledge_destination(destination)

    assert result.state is KnowledgeDestinationState.INVALID
    assert result.reason is not None
    assert existing_file.read_text(encoding="utf-8") == "保留原始数据"


def test_inspect_does_not_modify_valid_destination(
    tmp_path: Path,
) -> None:
    destination, _ = _write_distribution(tmp_path)

    before = _file_hashes(destination)

    inspect_knowledge_destination(destination)

    after = _file_hashes(destination)

    assert after == before


# ---------------------------------------------------------------------------
# 知识库部署
# ---------------------------------------------------------------------------


def test_deploy_to_missing_destination(tmp_path: Path) -> None:
    source, integrity_file = _write_distribution(tmp_path / "source")
    destination = tmp_path / "new-parent" / "knowledge"

    result = deploy_knowledge_distribution(
        source,
        destination,
        integrity_file,
    )

    assert destination.is_dir()
    assert result.knowledge_version == "0.1.0"
    assert result.file_count == 2
    assert _file_hashes(destination) == _file_hashes(source)


def test_deploy_to_empty_destination(tmp_path: Path) -> None:
    source, integrity_file = _write_distribution(tmp_path / "source")
    destination = tmp_path / "existing"
    destination.mkdir()

    result = deploy_knowledge_distribution(
        source,
        destination,
        integrity_file,
    )

    assert result.file_count == 2
    assert _file_hashes(destination) == _file_hashes(source)


def test_deploy_refuses_to_replace_valid_destination(
    tmp_path: Path,
) -> None:
    source, integrity_file = _write_distribution(tmp_path / "source")
    destination, _ = _write_distribution(tmp_path / "existing")

    before = _file_hashes(destination)

    with pytest.raises(InstallerError, match="明确确认替换"):
        deploy_knowledge_distribution(
            source,
            destination,
            integrity_file,
        )

    assert _file_hashes(destination) == before


def test_deploy_replaces_valid_destination_when_authorized(
    tmp_path: Path,
) -> None:
    source, integrity_file = _write_distribution(tmp_path / "source")
    destination, _ = _write_distribution(tmp_path / "existing")

    result = deploy_knowledge_distribution(
        source,
        destination,
        integrity_file,
        replace_existing=True,
    )

    assert result.file_count == 2
    assert _file_hashes(destination) == _file_hashes(source)


def test_deploy_refuses_to_replace_invalid_destination(
    tmp_path: Path,
) -> None:
    source, integrity_file = _write_distribution(tmp_path / "source")
    destination = tmp_path / "existing"
    destination.mkdir()

    important_file = destination / "important.txt"
    important_file.write_text("用户原有数据", encoding="utf-8")

    with pytest.raises(InstallerError, match="明确确认替换"):
        deploy_knowledge_distribution(
            source,
            destination,
            integrity_file,
        )

    assert important_file.read_text(encoding="utf-8") == "用户原有数据"


def test_deploy_replaces_invalid_destination_when_authorized(
    tmp_path: Path,
) -> None:
    source, integrity_file = _write_distribution(tmp_path / "source")
    destination = tmp_path / "existing"
    destination.mkdir()

    important_file = destination / "important.txt"
    important_file.write_text("用户原有数据", encoding="utf-8")

    result = deploy_knowledge_distribution(
        source,
        destination,
        integrity_file,
        replace_existing=True,
    )

    assert result.file_count == 2
    assert not important_file.exists()
    assert _file_hashes(destination) == _file_hashes(source)


def test_deploy_rejects_invalid_source_without_modifying_destination(
    tmp_path: Path,
) -> None:
    source, integrity_file = _write_distribution(tmp_path / "source")
    destination = tmp_path / "existing"
    destination.mkdir()

    important_file = destination / "important.txt"
    important_file.write_text("用户原有数据", encoding="utf-8")

    command_file = source / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md"
    command_file.write_text("发行包文件已损坏", encoding="utf-8")

    with pytest.raises(InstallerError):
        deploy_knowledge_distribution(
            source,
            destination,
            integrity_file,
            replace_existing=True,
        )

    assert important_file.read_text(encoding="utf-8") == "用户原有数据"

def test_deploy_reports_actual_copy_progress(tmp_path: Path) -> None:
    source, integrity_file = _write_distribution(tmp_path / "source")
    destination = tmp_path / "installed"

    progress: list[tuple[int, int]] = []

    result = deploy_knowledge_distribution(
        source,
        destination,
        integrity_file,
        progress_callback=lambda copied, total: progress.append((copied, total)),
    )

    total_bytes = sum(
        path.stat().st_size
        for path in source.rglob("*")
        if path.is_file()
    )

    assert result.file_count == 2
    assert progress
    assert progress[-1] == (total_bytes, total_bytes)

    copied_values = [copied for copied, _ in progress]

    assert copied_values == sorted(copied_values)
    assert all(total == total_bytes for _, total in progress)