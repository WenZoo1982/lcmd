from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from lcmd.core.config import AppConfig, save_config
from lcmd.core.update import (
    ReleaseAsset,
    ReleaseInfo,
    UpdateCheckResult,
    UpdateStatus,
)
from lcmd.core.update_knowledge import (
    KnowledgeUpdateError,
    _find_knowledge_asset,
    _safe_extract_zip,
    _serialize_manifest,
    _validate_staged_knowledge,
    _validate_zip_member,
    check_knowledge_update,
    recover_knowledge_update,
)


def make_knowledge(
    root: Path,
    version: str = "0.1.0",
) -> Path:
    """创建一个能被真实加载器识别的知识库。"""
    root.mkdir(parents=True, exist_ok=True)

    (root / "manifest.json").write_text(
        json.dumps({"version": version}, ensure_ascii=False),
        encoding="utf-8",
    )

    document = """+++
summary = "列出目录内容"
+++

---
# ls

列出当前目录中的文件和子目录。
"""

    document_path = root / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md"
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_text(document, encoding="utf-8")

    return root


def make_zip(
    root: Path,
    files: dict[str, str],
) -> Path:
    """创建测试 ZIP。"""
    archive_path = root / "test.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    return archive_path


def make_release(
    version: str = "0.2.0",
    digest: str | None = "sha256:" + "a" * 64,
) -> ReleaseInfo:
    """创建测试 Release。"""
    asset = ReleaseAsset(
        name=f"lcmd-kb-{version}.zip",
        download_url="https://github.com/WenZoo1982/lcmd-kb/releases/download/"
        f"v{version}/lcmd-kb-{version}.zip",
        size=100,
        digest=digest,
    )

    return ReleaseInfo(
        version=version,
        tag_name=f"v{version}",
        html_url=f"https://github.com/WenZoo1982/lcmd-kb/releases/tag/v{version}",
        published_at=None,
        assets=(asset,),
    )


def make_config(
    config_path: Path,
    knowledge_path: Path,
) -> None:
    """创建指向测试知识库的配置文件。"""
    save_config(
        AppConfig(
            knowledge_path=knowledge_path,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )


def make_journal(
    config_path: Path,
    target: Path,
    stage: Path,
    backup: Path,
    old_record: dict,
    new_record: dict,
    state: str = "old_moved",
) -> None:
    """写入测试事务日志。"""
    journal = {
        "schema_version": 1,
        "state": state,
        "target": str(target),
        "stage": str(stage),
        "backup": str(backup),
        "old": old_record,
        "new": new_record,
    }

    journal_path = config_path.parent / ".lcmd-knowledge-update.json"
    journal_path.write_text(
        json.dumps(journal, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_safe_extract_zip_accepts_root_level_knowledge(tmp_path):
    source = make_knowledge(tmp_path / "source", "0.2.0")
    archive_path = tmp_path / "knowledge.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())

    destination = tmp_path / "stage"
    _safe_extract_zip(archive_path, destination)

    assert (destination / "manifest.json").is_file()
    assert (destination / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md").is_file()


@pytest.mark.parametrize(
    "member_name",
    [
        "../outside.txt",
        "commands/../../outside.txt",
        "/absolute.txt",
        "C:/outside.txt",
        r"commands\..\outside.txt",
        "commands//outside.txt",
        "commands/./outside.txt",
        "commands/../outside.txt",
    ],
)
def test_safe_extract_zip_rejects_unsafe_paths(tmp_path, member_name):
    archive_path = make_zip(
        tmp_path,
        {member_name: "unsafe"},
    )

    with pytest.raises(KnowledgeUpdateError):
        _safe_extract_zip(archive_path, tmp_path / "stage")


def test_safe_extract_zip_rejects_duplicate_names(tmp_path):
    archive_path = tmp_path / "duplicate.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("README.md", "first")
        archive.writestr("README.md", "second")

    with pytest.raises(KnowledgeUpdateError):
        _safe_extract_zip(archive_path, tmp_path / "stage")


def test_safe_extract_zip_rejects_case_conflicts(tmp_path):
    archive_path = make_zip(
        tmp_path,
        {
            "README.md": "first",
            "readme.md": "second",
        },
    )

    with pytest.raises(KnowledgeUpdateError):
        _safe_extract_zip(archive_path, tmp_path / "stage")


def test_safe_extract_zip_rejects_file_directory_conflict(tmp_path):
    archive_path = make_zip(
        tmp_path,
        {
            "commands": "file",
            "commands/ls.md": "content",
        },
    )

    with pytest.raises(KnowledgeUpdateError):
        _safe_extract_zip(archive_path, tmp_path / "stage")


def test_safe_extract_zip_rejects_empty_archive(tmp_path):
    archive_path = tmp_path / "empty.zip"

    with zipfile.ZipFile(archive_path, "w"):
        pass

    with pytest.raises(KnowledgeUpdateError):
        _safe_extract_zip(archive_path, tmp_path / "stage")


def test_validate_staged_knowledge_accepts_valid_knowledge(tmp_path):
    stage = make_knowledge(tmp_path / "stage", version="0.2.0")

    record = _validate_staged_knowledge(
        stage,
        "0.2.0",
        "linux",
        "zh-CN",
    )

    assert record["identity"]["device"] >= 0
    assert record["identity"]["inode"] >= 0
    assert "manifest.json" in record["files"]
    assert record["directories"]


def test_validate_staged_knowledge_rejects_version_mismatch(tmp_path):
    stage = make_knowledge(tmp_path / "stage", version="0.3.0")

    with pytest.raises(KnowledgeUpdateError):
        _validate_staged_knowledge(
            stage,
            "0.2.0",
            "linux",
            "zh-CN",
        )


def test_validate_staged_knowledge_rejects_missing_language_document(tmp_path):
    stage = tmp_path / "stage"
    stage.mkdir()

    (stage / "manifest.json").write_text(
        '{"version":"0.2.0"}',
        encoding="utf-8",
    )

    (stage / "commands" / "platforms" / "linux" / "zh-CN").mkdir(parents=True)

    with pytest.raises(KnowledgeUpdateError):
        _validate_staged_knowledge(
            stage,
            "0.2.0",
            "linux",
            "zh-CN",
        )


def test_recover_knowledge_update_without_journal(tmp_path):
    config_path = tmp_path / "config.toml"

    recover_knowledge_update(config_path)


def test_recover_knowledge_update_restores_old_directory(tmp_path):
    config_path = tmp_path / "config.toml"

    target = tmp_path / "knowledge"
    backup = tmp_path / (".lcmd-knowledge-backup-" + "a" * 32)
    stage = tmp_path / (".lcmd-knowledge-stage-" + "a" * 32)

    old_record = _serialize_manifest(make_knowledge(backup, "0.1.0"))
    new_record = _serialize_manifest(make_knowledge(stage, "0.2.0"))

    make_config(config_path, target)

    make_journal(
        config_path,
        target,
        stage,
        backup,
        old_record,
        new_record,
    )

    recover_knowledge_update(config_path)

    assert target.is_dir()
    assert (target / "manifest.json").read_text(encoding="utf-8")
    assert not backup.exists()
    assert not stage.exists()
    assert not (tmp_path / ".lcmd-knowledge-update.json").exists()


def test_recover_knowledge_update_cleans_backup_when_new_installed(tmp_path):
    config_path = tmp_path / "config.toml"

    target = tmp_path / "knowledge"
    backup = tmp_path / (".lcmd-knowledge-backup-" + "b" * 32)
    stage = tmp_path / (".lcmd-knowledge-stage-" + "b" * 32)

    old_record = _serialize_manifest(make_knowledge(backup, "0.1.0"))
    new_record = _serialize_manifest(make_knowledge(target, "0.2.0"))

    make_config(config_path, target)

    make_journal(
        config_path,
        target,
        stage,
        backup,
        old_record,
        new_record,
        state="new_installed",
    )

    recover_knowledge_update(config_path)

    assert target.is_dir()
    assert not backup.exists()
    assert not (tmp_path / ".lcmd-knowledge-update.json").exists()


def test_recover_knowledge_update_cleans_stage_when_old_remains(tmp_path):
    config_path = tmp_path / "config.toml"

    target = tmp_path / "knowledge"
    backup = tmp_path / (".lcmd-knowledge-backup-" + "c" * 32)
    stage = tmp_path / (".lcmd-knowledge-stage-" + "c" * 32)

    old_record = _serialize_manifest(make_knowledge(target, "0.1.0"))
    new_record = _serialize_manifest(make_knowledge(stage, "0.2.0"))

    make_config(config_path, target)

    make_journal(
        config_path,
        target,
        stage,
        backup,
        old_record,
        new_record,
    )

    recover_knowledge_update(config_path)

    assert target.is_dir()
    assert not stage.exists()
    assert not backup.exists()
    assert not (tmp_path / ".lcmd-knowledge-update.json").exists()


def test_recover_knowledge_update_preserves_unrecognized_target(tmp_path):
    config_path = tmp_path / "config.toml"

    target = make_knowledge(tmp_path / "knowledge", "0.3.0")
    backup = tmp_path / (".lcmd-knowledge-backup-" + "d" * 32)
    stage = tmp_path / (".lcmd-knowledge-stage-" + "d" * 32)

    old_record = _serialize_manifest(make_knowledge(tmp_path / "old", "0.1.0"))
    new_record = _serialize_manifest(make_knowledge(stage, "0.2.0"))

    make_config(config_path, target)

    make_journal(
        config_path,
        target,
        stage,
        backup,
        old_record,
        new_record,
    )

    with pytest.raises(KnowledgeUpdateError):
        recover_knowledge_update(config_path)

    assert target.exists()
    assert stage.exists()
    assert (tmp_path / ".lcmd-knowledge-update.json").exists()


def test_recover_knowledge_update_rejects_invalid_journal(tmp_path):
    config_path = tmp_path / "config.toml"
    journal_path = tmp_path / ".lcmd-knowledge-update.json"

    journal_path.write_text(
        '{"invalid": true}',
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeUpdateError):
        recover_knowledge_update(config_path)


def test_recover_knowledge_update_rejects_uncontrolled_stage_name(tmp_path):
    config_path = tmp_path / "config.toml"

    target = tmp_path / "knowledge"
    stage = tmp_path / "unexpected-stage"
    backup = tmp_path / (".lcmd-knowledge-backup-" + "e" * 32)

    old_record = {}
    new_record = {}

    make_journal(
        config_path,
        target,
        stage,
        backup,
        old_record,
        new_record,
    )

    with pytest.raises(KnowledgeUpdateError):
        recover_knowledge_update(config_path)


def test_check_knowledge_update_uses_knowledge_repository(monkeypatch):
    import lcmd.core.update_knowledge as module

    captured = {}

    def fake_check(repository, current_version):
        captured["repository"] = repository
        captured["version"] = current_version

        return UpdateCheckResult(
            status=UpdateStatus.UP_TO_DATE,
            current_version=current_version,
            latest_version=current_version,
        )

    monkeypatch.setattr(module, "check_for_update", fake_check)

    result = check_knowledge_update("0.1.0")

    assert result.status == UpdateStatus.UP_TO_DATE
    assert captured["repository"] == "WenZoo1982/lcmd-kb"
    assert captured["version"] == "0.1.0"


def test_find_knowledge_asset_accepts_expected_asset():
    release = make_release()

    asset = _find_knowledge_asset(release)

    assert asset.name == "lcmd-kb-0.2.0.zip"
    assert asset.digest is not None


def test_find_knowledge_asset_rejects_missing_digest():
    release = make_release(digest=None)

    with pytest.raises(KnowledgeUpdateError):
        _find_knowledge_asset(release)


def test_find_knowledge_asset_rejects_missing_asset():
    release = ReleaseInfo(
        version="0.2.0",
        tag_name="v0.2.0",
        html_url="https://github.com/WenZoo1982/lcmd-kb/releases/tag/v0.2.0",
        published_at=None,
        assets=(),
    )

    with pytest.raises(KnowledgeUpdateError):
        _find_knowledge_asset(release)


def test_validate_zip_member_returns_normalized_path():
    info = zipfile.ZipInfo("commands/platforms/linux/")

    relative, is_directory = _validate_zip_member(info)

    assert relative == "commands/platforms/linux"
    assert is_directory is True


def test_validate_zip_member_rejects_backslash():
    info = zipfile.ZipInfo("placeholder.txt")

    # Windows 下 ZipInfo 构造时会自动转换反斜杠，
    # 因此这里直接设置 filename，模拟原始 ZIP 成员名称。
    info.filename = r"commands\outside.txt"

    with pytest.raises(KnowledgeUpdateError):
        _validate_zip_member(info)

def test_serialize_manifest_uses_shared_knowledge_file_tools(tmp_path):
    root = make_knowledge(tmp_path / "knowledge")

    record = _serialize_manifest(root)

    assert set(record) == {"identity", "files", "directories"}
    assert set(record["identity"]) == {"device", "inode"}
    assert "manifest.json" in record["files"]
