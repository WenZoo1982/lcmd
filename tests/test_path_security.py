from pathlib import Path

import pytest

from lcmd.core.path_security import (
    PathSecurityError,
    normalize_path,
    validate_knowledge_destination,
    validate_knowledge_path,
    validate_migration_target,
)


def create_knowledge(root: Path) -> Path:
    """创建最小有效知识库。"""
    (root / "commands" / "platforms" / "linux" / "zh-CN").mkdir(parents=True)
    (root / "manifest.json").write_text(
        '{"version": "0.1.0"}',
        encoding="utf-8",
    )
    (root / "commands" / "platforms" / "linux" / "zh-CN" / "ls.md").write_text(
        "---\nsummary: 列出目录内容\n---\n显示目录内容。\n",
        encoding="utf-8",
    )
    return root


def test_normalize_path_returns_absolute_path(tmp_path):
    result = normalize_path(tmp_path / "knowledge")

    assert result.is_absolute()
    assert result == (tmp_path / "knowledge").resolve()


def test_normalize_path_rejects_empty_path():
    with pytest.raises(PathSecurityError, match="不能为空"):
        normalize_path("   ")


def test_normalize_path_rejects_null_character():
    with pytest.raises(PathSecurityError):
        normalize_path("invalid\x00path")


@pytest.mark.parametrize(
    "path",
    [
        "",
        "   ",
    ],
)
def test_normalize_path_rejects_blank_values(path):
    with pytest.raises(PathSecurityError):
        normalize_path(path)


def test_validate_knowledge_path_accepts_valid_knowledge(tmp_path):
    knowledge = create_knowledge(tmp_path / "knowledge")

    result = validate_knowledge_path(
        knowledge,
        protected_paths=[tmp_path / "protected"],
    )

    assert result == knowledge.resolve()


def test_validate_knowledge_path_rejects_missing_directory(tmp_path):
    with pytest.raises(PathSecurityError, match="不存在"):
        validate_knowledge_path(
            tmp_path / "missing",
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_knowledge_path_rejects_invalid_knowledge(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()

    with pytest.raises(PathSecurityError, match="结构无效"):
        validate_knowledge_path(
            knowledge,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_knowledge_path_rejects_file(tmp_path):
    file_path = tmp_path / "knowledge.txt"
    file_path.write_text("not a directory", encoding="utf-8")

    with pytest.raises(PathSecurityError, match="不是目录"):
        validate_knowledge_path(
            file_path,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_migration_target_accepts_new_directory(tmp_path):
    source = create_knowledge(tmp_path / "source")
    target = tmp_path / "destination"

    result = validate_migration_target(
        target,
        source,
        protected_paths=[tmp_path / "protected"],
    )

    assert result == target.resolve()
    assert not target.exists()


def test_validate_migration_target_accepts_existing_directory(tmp_path):
    source = create_knowledge(tmp_path / "source")
    target = tmp_path / "destination"
    target.mkdir()

    result = validate_migration_target(
        target,
        source,
        protected_paths=[tmp_path / "protected"],
    )

    assert result == target.resolve()
    assert target.is_dir()


def test_validate_migration_target_rejects_file(tmp_path):
    source = create_knowledge(tmp_path / "source")
    target = tmp_path / "destination.txt"
    target.write_text("not a directory", encoding="utf-8")

    with pytest.raises(PathSecurityError, match="不是目录"):
        validate_migration_target(
            target,
            source,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_migration_target_rejects_missing_parent(tmp_path):
    source = create_knowledge(tmp_path / "source")
    target = tmp_path / "missing" / "destination"

    with pytest.raises(PathSecurityError, match="父目录不存在"):
        validate_migration_target(
            target,
            source,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_migration_target_rejects_source_itself(tmp_path):
    source = create_knowledge(tmp_path / "source")

    with pytest.raises(PathSecurityError, match="不能与当前知识库相同"):
        validate_migration_target(
            source,
            source,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_migration_target_rejects_source_child(tmp_path):
    source = create_knowledge(tmp_path / "source")

    with pytest.raises(PathSecurityError, match="不能与当前知识库相同"):
        validate_migration_target(
            source / "child",
            source,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_migration_target_rejects_source_parent(tmp_path):
    source = create_knowledge(tmp_path / "parent" / "source")

    with pytest.raises(PathSecurityError, match="不能与当前知识库相同"):
        validate_migration_target(
            source.parent,
            source,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_migration_target_rejects_protected_directory(tmp_path):
    source = create_knowledge(tmp_path / "source")
    protected = tmp_path / "protected"
    protected.mkdir()

    with pytest.raises(PathSecurityError, match="受保护目录"):
        validate_migration_target(
            protected,
            source,
            protected_paths=[protected],
        )


def test_validate_migration_target_rejects_child_of_protected_directory(
    tmp_path,
):
    source = create_knowledge(tmp_path / "source")
    protected = tmp_path / "protected"
    protected.mkdir()

    with pytest.raises(PathSecurityError, match="受保护目录"):
        validate_migration_target(
            protected / "knowledge",
            source,
            protected_paths=[protected],
        )


def test_validate_migration_target_rejects_parent_of_protected_directory(
    tmp_path,
):
    source = create_knowledge(tmp_path / "source")
    protected = tmp_path / "protected" / "config"
    protected.mkdir(parents=True)

    with pytest.raises(PathSecurityError, match="受保护目录"):
        validate_migration_target(
            protected.parent,
            source,
            protected_paths=[protected],
        )


def test_validate_migration_target_does_not_modify_source_or_target(
    tmp_path,
):
    source = create_knowledge(tmp_path / "source")
    target = tmp_path / "destination"

    validate_migration_target(
        target,
        source,
        protected_paths=[tmp_path / "protected"],
    )

    assert source.is_dir()
    assert (source / "manifest.json").is_file()
    assert not target.exists()


def test_validate_migration_target_rejects_symlink(tmp_path):
    source = create_knowledge(tmp_path / "source")
    real_target = tmp_path / "real-target"
    real_target.mkdir()
    link = tmp_path / "linked-target"

    try:
        link.symlink_to(real_target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建目录符号链接")

    with pytest.raises(PathSecurityError, match="符号链接"):
        validate_migration_target(
            link,
            source,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_migration_target_rejects_symlink_in_parent(tmp_path):
    source = create_knowledge(tmp_path / "source")
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    link_parent = tmp_path / "linked-parent"

    try:
        link_parent.symlink_to(real_parent, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建目录符号链接")

    with pytest.raises(PathSecurityError, match="符号链接"):
        validate_migration_target(
            link_parent / "destination",
            source,
            protected_paths=[tmp_path / "protected"],
        )


@pytest.mark.skipif(
    not hasattr(Path, "is_junction"),
    reason="当前 Python 版本不提供 Path.is_junction",
)
def test_validate_migration_target_rejects_junction(tmp_path):
    source = create_knowledge(tmp_path / "source")
    real_target = tmp_path / "real-target"
    real_target.mkdir()
    junction = tmp_path / "junction"

    import subprocess

    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(real_target)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.skip("当前环境无法创建目录联接")

    with pytest.raises(PathSecurityError, match="符号链接"):
        validate_migration_target(
            junction,
            source,
            protected_paths=[tmp_path / "protected"],
        )

def test_validate_knowledge_destination_accepts_new_directory(tmp_path):
    target = tmp_path / "destination"

    result = validate_knowledge_destination(
        target,
        protected_paths=[tmp_path / "protected"],
    )

    assert result == target.resolve()
    assert not target.exists()


def test_validate_knowledge_destination_accepts_empty_directory(tmp_path):
    target = tmp_path / "destination"
    target.mkdir()

    result = validate_knowledge_destination(
        target,
        protected_paths=[tmp_path / "protected"],
    )

    assert result == target.resolve()
    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_validate_knowledge_destination_accepts_nonempty_directory(tmp_path):
    target = tmp_path / "destination"
    target.mkdir()
    existing_file = target / "existing.txt"
    existing_file.write_text("keep this file", encoding="utf-8")

    result = validate_knowledge_destination(
        target,
        protected_paths=[tmp_path / "protected"],
    )

    assert result == target.resolve()
    assert existing_file.read_text(encoding="utf-8") == "keep this file"


def test_validate_knowledge_destination_rejects_file(tmp_path):
    target = tmp_path / "destination.txt"
    target.write_text("not a directory", encoding="utf-8")

    with pytest.raises(PathSecurityError, match="不是目录"):
        validate_knowledge_destination(
            target,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_knowledge_destination_rejects_missing_parent(tmp_path):
    target = tmp_path / "missing" / "destination"

    with pytest.raises(PathSecurityError, match="父目录不存在"):
        validate_knowledge_destination(
            target,
            protected_paths=[tmp_path / "protected"],
        )


def test_validate_knowledge_destination_rejects_protected_directory(tmp_path):
    protected = tmp_path / "protected"
    protected.mkdir()

    with pytest.raises(PathSecurityError, match="受保护目录"):
        validate_knowledge_destination(
            protected,
            protected_paths=[protected],
        )


def test_validate_knowledge_destination_rejects_symlink(tmp_path):
    real_target = tmp_path / "real-target"
    real_target.mkdir()
    link = tmp_path / "linked-target"

    try:
        link.symlink_to(real_target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建目录符号链接")

    with pytest.raises(PathSecurityError, match="符号链接"):
        validate_knowledge_destination(
            link,
            protected_paths=[tmp_path / "protected"],
        )

def test_validate_knowledge_destination_accepts_default_knowledge_path(
    tmp_path,
    monkeypatch,
):
    """默认知识库目录位于配置目录内，应允许使用。"""
    import lcmd.core.path_security as path_security

    config_dir = tmp_path / "lcmd"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    knowledge_dir = config_dir / "knowledge"

    monkeypatch.setattr(
        path_security,
        "get_config_file",
        lambda: config_file,
    )
    monkeypatch.setattr(
        path_security,
        "_get_install_dir",
        lambda: tmp_path / "Programs" / "LCMD",
    )

    result = validate_knowledge_destination(knowledge_dir)

    assert result == knowledge_dir.resolve()


def test_validate_knowledge_destination_rejects_config_directory(
    tmp_path,
    monkeypatch,
):
    """配置目录本身仍然受到保护。"""
    import lcmd.core.path_security as path_security

    config_dir = tmp_path / "lcmd"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"

    monkeypatch.setattr(
        path_security,
        "get_config_file",
        lambda: config_file,
    )
    monkeypatch.setattr(
        path_security,
        "_get_install_dir",
        lambda: tmp_path / "Programs" / "LCMD",
    )

    with pytest.raises(PathSecurityError, match="受保护目录"):
        validate_knowledge_destination(config_dir)        