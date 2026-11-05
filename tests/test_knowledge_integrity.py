from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lcmd.core.knowledge_integrity import (
    KnowledgeIntegrityError,
    verify_knowledge_distribution,
)


# ---------------------------------------------------------------------------
# ????????????
# ---------------------------------------------------------------------------

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

    with pytest.raises(KnowledgeIntegrityError, match="大小|SHA-256"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_rejects_extra_file(tmp_path: Path) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    (knowledge_dir / "unexpected.txt").write_text(
        "extra",
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeIntegrityError, match="清单之外"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_rejects_missing_file(tmp_path: Path) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    command_file = knowledge_dir / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md"
    command_file.unlink()

    with pytest.raises(KnowledgeIntegrityError, match="缺少发行文件"):
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

    with pytest.raises(KnowledgeIntegrityError, match="版本"):
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

    with pytest.raises(KnowledgeIntegrityError, match="字段"):
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

    with pytest.raises(KnowledgeIntegrityError, match="非法目录"):
        verify_knowledge_distribution(knowledge_dir, integrity_file)


def test_verify_does_not_modify_distribution(
    tmp_path: Path,
) -> None:
    knowledge_dir, integrity_file = _write_distribution(tmp_path)

    before = _file_hashes(knowledge_dir)

    verify_knowledge_distribution(knowledge_dir, integrity_file)

    after = _file_hashes(knowledge_dir)

    assert after == before
