"""LCMD 知识库路径模块测试."""

import pytest

from lcmd.core import paths
from lcmd.core.config import AppConfig
from lcmd.core.paths import (
    KnowledgeDirs,
    PathError,
    get_default_knowledge_dir,
    get_knowledge_dirs,
    get_knowledge_root,
    validate_knowledge_root,
)


def test_get_default_knowledge_dir_uses_platformdirs(monkeypatch, tmp_path):
    """默认知识库目录应由 platformdirs 提供."""
    monkeypatch.setattr(paths, "user_data_path", lambda *args, **kwargs: tmp_path)

    assert get_default_knowledge_dir() == tmp_path / "knowledge"


def test_get_knowledge_root_uses_default_when_env_missing(monkeypatch, tmp_path):
    """未设置环境变量时应使用默认目录."""
    monkeypatch.delenv("LCMD_KNOWLEDGE_DIR", raising=False)
    monkeypatch.setattr(paths, "get_default_knowledge_dir", lambda: tmp_path)

    assert get_knowledge_root() == tmp_path


def test_get_knowledge_root_uses_environment_variable(monkeypatch, tmp_path):
    """环境变量应覆盖默认目录."""
    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", str(tmp_path))

    assert get_knowledge_root() == tmp_path.resolve()


def test_get_knowledge_root_rejects_empty_environment_variable(monkeypatch):
    """环境变量为空时应明确报错."""
    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", "")

    with pytest.raises(PathError, match="不能为空"):
        get_knowledge_root()


def test_get_knowledge_root_rejects_whitespace_environment_variable(monkeypatch):
    """环境变量只有空白字符时应明确报错."""
    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", "   ")

    with pytest.raises(PathError, match="不能为空"):
        get_knowledge_root()


def test_get_knowledge_root_resolves_relative_path(monkeypatch, tmp_path):
    """相对路径应根据当前工作目录解析."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", "my-knowledge")

    assert get_knowledge_root() == (tmp_path / "my-knowledge").resolve()


def test_validate_knowledge_root_accepts_existing_directory(tmp_path):
    """有效目录应通过检查."""
    root = tmp_path / "knowledge"
    root.mkdir()

    assert validate_knowledge_root(root) == root.resolve()


def test_validate_knowledge_root_rejects_missing_directory(tmp_path):
    """不存在的目录应明确报错."""
    root = tmp_path / "missing"

    with pytest.raises(PathError, match="目录不存在"):
        validate_knowledge_root(root)


def test_validate_knowledge_root_rejects_file(tmp_path):
    """普通文件不能作为知识库根目录."""
    root = tmp_path / "knowledge.txt"
    root.write_text("test", encoding="utf-8")

    with pytest.raises(PathError, match="不是目录"):
        validate_knowledge_root(root)


def test_validate_knowledge_root_uses_environment_variable(monkeypatch, tmp_path):
    """未传入路径时应验证环境变量指定的目录."""
    root = tmp_path / "knowledge"
    root.mkdir()
    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", str(root))

    assert validate_knowledge_root() == root.resolve()


def test_get_knowledge_dirs_uses_config(monkeypatch, tmp_path):
    """命令和任务目录应根据平台及语言配置推导."""
    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", str(tmp_path))
    config = AppConfig(platform="windows", language="zh-CN")

    result = get_knowledge_dirs(config)

    assert result == KnowledgeDirs(
        root=tmp_path.resolve(),
        commands=tmp_path / "commands" / "windows" / "zh-CN",
        tasks=tmp_path / "tasks" / "windows" / "zh-CN",
    )


def test_get_knowledge_dirs_does_not_create_directories(monkeypatch, tmp_path):
    """计算路径时不得自动创建知识库目录."""
    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))

    result = get_knowledge_dirs(AppConfig(platform="linux"))

    assert result.commands == (tmp_path / "knowledge" / "commands" / "linux" / "zh-CN")
    assert result.tasks == (tmp_path / "knowledge" / "tasks" / "linux" / "zh-CN")
    assert not result.root.exists()
