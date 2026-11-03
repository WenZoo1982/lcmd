import json
from pathlib import Path

import pytest

from lcmd.core.config import AppConfig, load_config, save_config
from lcmd.core.migration import (
    MigrationCleanupWarning,
    MigrationConfirmationRequired,
    MigrationError,
    migrate_knowledge,
    recover_migration,
)


def create_knowledge(root: Path) -> Path:
    """创建最小有效知识库。"""
    (root / "commands" / "platforms" / "linux" / "zh-CN").mkdir(
        parents=True,
    )
    (root / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md").write_text(
        "---\nsummary: 列出目录内容\n---\n\n显示目录中的文件。\n",
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(
        json.dumps({"version": "0.1.0"}),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def migration_environment(tmp_path):
    source = create_knowledge(tmp_path / "source")
    target = tmp_path / "target"
    config_path = tmp_path / "config" / "config.toml"

    save_config(
        AppConfig(
            knowledge_path=source,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    return source, target, config_path


def test_migrate_knowledge_success(migration_environment):
    source, target, config_path = migration_environment

    result = migrate_knowledge(
        config_path,
        target,
        protected_paths=(),
    )

    assert result.knowledge_path == target
    assert result.platform == "linux"
    assert result.language == "zh-CN"

    assert load_config(config_path) == result
    assert target.is_dir()
    assert (target / "manifest.json").is_file()
    assert not source.exists()
    assert not (config_path.parent / ".lcmd-migration.json").exists()


def test_existing_target_requires_confirmation(migration_environment):
    source, target, config_path = migration_environment
    target.mkdir()

    original = target / "keep.txt"
    original.write_text("原有内容", encoding="utf-8")

    original_config = load_config(config_path)

    with pytest.raises(MigrationConfirmationRequired):
        migrate_knowledge(
            config_path,
            target,
            protected_paths=(),
        )

    assert source.is_dir()
    assert original.read_text(encoding="utf-8") == "原有内容"
    assert load_config(config_path) == original_config


def test_existing_target_is_replaced_after_confirmation(migration_environment):
    source, target, config_path = migration_environment
    target.mkdir()
    (target / "old.txt").write_text("旧内容", encoding="utf-8")

    migrate_knowledge(
        config_path,
        target,
        overwrite=True,
        protected_paths=(),
    )

    assert target.is_dir()
    assert not (target / "old.txt").exists()
    assert (target / "manifest.json").is_file()
    assert not source.exists()


def test_copy_failure_preserves_source_and_config(
    migration_environment,
    monkeypatch,
):
    import lcmd.core.migration as migration

    source, target, config_path = migration_environment
    original_config = load_config(config_path)

    def fail_copy(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(migration.shutil, "copy2", fail_copy)

    with pytest.raises(MigrationError):
        migrate_knowledge(
            config_path,
            target,
            protected_paths=(),
        )

    assert source.is_dir()
    assert load_config(config_path) == original_config


def test_integrity_failure_preserves_source_and_config(
    migration_environment,
    monkeypatch,
):
    import lcmd.core.migration as migration

    source, target, config_path = migration_environment
    original_config = load_config(config_path)

    def fail_verify(*args, **kwargs):
        raise MigrationError("simulated integrity failure")

    monkeypatch.setattr(migration, "_verify_copy", fail_verify)

    with pytest.raises(MigrationError):
        migrate_knowledge(
            config_path,
            target,
            protected_paths=(),
        )

    assert source.is_dir()
    assert target.is_dir()
    assert load_config(config_path) == original_config


def test_config_save_failure_preserves_source(
    migration_environment,
    monkeypatch,
):
    import lcmd.core.migration as migration

    source, target, config_path = migration_environment
    original_config = load_config(config_path)

    def fail_save(*args, **kwargs):
        raise migration.ConfigError("simulated config failure")

    monkeypatch.setattr(migration, "save_config", fail_save)

    with pytest.raises(MigrationError):
        migrate_knowledge(
            config_path,
            target,
            protected_paths=(),
        )

    assert source.is_dir()
    assert target.is_dir()
    assert load_config(config_path) == original_config


def test_migration_succeeds_when_old_source_cannot_be_removed(
    migration_environment,
    monkeypatch,
):
    import lcmd.core.migration as migration

    source, target, config_path = migration_environment
    original_rmtree = migration.shutil.rmtree

    def fail_source_removal(path, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("simulated file lock")

        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(migration.shutil, "rmtree", fail_source_removal)

    with pytest.warns(MigrationCleanupWarning) as captured:
        result = migrate_knowledge(
            config_path,
            target,
            protected_paths=(),
        )

    assert result.knowledge_path == target
    assert load_config(config_path) == result
    assert target.is_dir()
    assert source.is_dir()

    journal_path = config_path.parent / ".lcmd-migration.json"
    assert journal_path.is_file()

    journal = json.loads(journal_path.read_text(encoding="utf-8"))

    assert journal["source"] == str(source)
    assert journal["target"] == str(target)
    assert "source_manifest" in journal
    assert "source_identity" in journal

    assert str(source) in str(captured[0].message)
    assert str(target) in str(captured[0].message)


def test_recovery_removes_old_source_after_config_switch(
    migration_environment,
):
    source, target, config_path = migration_environment

    from lcmd.core.migration import _write_journal

    create_knowledge(target)

    save_config(
        AppConfig(
            knowledge_path=target,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    _write_journal(
        config_path,
        source,
        target,
        "ready_to_switch",
    )

    assert source.exists()

    recovered = recover_migration(
        config_path,
        protected_paths=(),
    )

    assert recovered is True
    assert target.is_dir()
    assert not source.exists()
    assert not (config_path.parent / ".lcmd-migration.json").exists()


def test_recovery_does_not_remove_source_when_config_still_points_to_source(
    migration_environment,
):
    source, target, config_path = migration_environment

    from lcmd.core.migration import _write_journal

    target.mkdir()

    _write_journal(
        config_path,
        source,
        target,
        "copying",
    )

    recovered = recover_migration(
        config_path,
        protected_paths=(),
    )

    assert recovered is False
    assert source.is_dir()
    assert target.is_dir()
    assert not (config_path.parent / ".lcmd-migration.json").exists()


def test_recovery_rejects_unrelated_config_path(
    migration_environment,
):
    source, target, config_path = migration_environment

    from lcmd.core.migration import _write_journal

    unrelated = create_knowledge(config_path.parent / "unrelated")

    _write_journal(
        config_path,
        source,
        target,
        "ready_to_switch",
    )

    save_config(
        AppConfig(
            knowledge_path=unrelated,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    with pytest.raises(MigrationError):
        recover_migration(
            config_path,
            protected_paths=(),
        )

    assert source.is_dir()
    assert unrelated.is_dir()


def test_recovery_rejects_protected_source_directory(
    migration_environment,
):
    source, target, config_path = migration_environment

    from lcmd.core.migration import _write_journal

    create_knowledge(target)

    save_config(
        AppConfig(
            knowledge_path=target,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    _write_journal(
        config_path,
        source,
        target,
        "ready_to_switch",
    )

    with pytest.raises(MigrationError):
        recover_migration(
            config_path,
            protected_paths=(source,),
        )

    assert source.is_dir()
    assert target.is_dir()


def test_recovery_rejects_replaced_source_directory(
    migration_environment,
):
    source, target, config_path = migration_environment

    from lcmd.core.migration import _write_journal

    create_knowledge(target)

    save_config(
        AppConfig(
            knowledge_path=target,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    _write_journal(
        config_path,
        source,
        target,
        "ready_to_switch",
    )

    replacement = source.with_name("replacement")
    source.rename(replacement)
    create_knowledge(source)

    with pytest.raises(MigrationError, match="目录身份"):
        recover_migration(
            config_path,
            protected_paths=(),
        )

    assert source.is_dir()
    assert replacement.is_dir()
    assert target.is_dir()


def test_recovery_accepts_partially_deleted_source(
    migration_environment,
):
    source, target, config_path = migration_environment

    from lcmd.core.migration import _write_journal

    create_knowledge(target)

    save_config(
        AppConfig(
            knowledge_path=target,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    _write_journal(
        config_path,
        source,
        target,
        "switched",
    )

    # 模拟上一次删除旧目录时，部分文件已经被删除。
    (source / "manifest.json").unlink()

    recovered = recover_migration(
        config_path,
        protected_paths=(),
    )

    assert recovered is True
    assert target.is_dir()
    assert not source.exists()
    assert not (config_path.parent / ".lcmd-migration.json").exists()


def test_recovery_rejects_unexpected_source_file(
    migration_environment,
):
    source, target, config_path = migration_environment

    from lcmd.core.migration import _write_journal

    create_knowledge(target)

    save_config(
        AppConfig(
            knowledge_path=target,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    _write_journal(
        config_path,
        source,
        target,
        "switched",
    )

    (source / "unexpected.txt").write_text(
        "不属于原始知识库的文件",
        encoding="utf-8",
    )

    with pytest.raises(MigrationError, match="不存在的文件"):
        recover_migration(
            config_path,
            protected_paths=(),
        )

    assert source.is_dir()
    assert target.is_dir()


def test_recovery_keeps_journal_when_cleanup_fails(
    migration_environment,
    monkeypatch,
):
    import lcmd.core.migration as migration

    source, target, config_path = migration_environment
    original_rmtree = migration.shutil.rmtree

    create_knowledge(target)

    save_config(
        AppConfig(
            knowledge_path=target,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    from lcmd.core.migration import _write_journal

    _write_journal(
        config_path,
        source,
        target,
        "switched",
    )

    def fail_source_removal(path, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("simulated file lock")

        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(migration.shutil, "rmtree", fail_source_removal)

    with pytest.warns(MigrationCleanupWarning) as captured:
        recovered = recover_migration(
            config_path,
            protected_paths=(),
        )

    assert recovered is False
    assert source.is_dir()
    assert target.is_dir()
    assert (config_path.parent / ".lcmd-migration.json").is_file()
    assert str(source) in str(captured[0].message)


def test_recovery_reports_old_and_new_paths_when_config_is_missing(
    migration_environment,
):
    source, target, config_path = migration_environment

    from lcmd.core.migration import _write_journal

    create_knowledge(target)

    save_config(
        AppConfig(
            knowledge_path=target,
            platform="linux",
            language="zh-CN",
        ),
        config_path,
    )

    _write_journal(
        config_path,
        source,
        target,
        "switched",
    )

    config_path.unlink()

    with pytest.raises(MigrationError) as captured:
        recover_migration(
            config_path,
            protected_paths=(),
        )

    message = str(captured.value)

    assert str(source) in message
    assert str(target) in message
    assert source.is_dir()
    assert target.is_dir()
    assert (config_path.parent / ".lcmd-migration.json").is_file()


def test_recovery_returns_false_when_journal_does_not_exist(
    migration_environment,
):
    source, target, config_path = migration_environment

    recovered = recover_migration(
        config_path,
        protected_paths=(),
    )

    assert recovered is False
    assert source.is_dir()
    assert not target.exists()


def test_recovery_rejects_corrupted_journal(
    migration_environment,
):
    source, target, config_path = migration_environment

    journal_path = config_path.parent / ".lcmd-migration.json"
    journal_path.write_text(
        "{invalid json",
        encoding="utf-8",
    )

    with pytest.raises(MigrationError):
        recover_migration(
            config_path,
            protected_paths=(),
        )

    assert source.is_dir()
    assert not target.exists()
