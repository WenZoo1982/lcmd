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


def test_get_knowledge_root_uses_default_when_config_path_missing(monkeypatch, tmp_path):
    """配置未指定知识库路径时应使用默认目录."""
    monkeypatch.setattr(paths, "get_default_knowledge_dir", lambda: tmp_path)

    result = get_knowledge_root(AppConfig(platform="linux"))

    assert result == tmp_path


def test_get_knowledge_root_uses_config_path(tmp_path):
    """配置指定知识库路径时应使用自定义目录."""
    knowledge_root = tmp_path / "custom-knowledge"
    config = AppConfig(platform="linux", path=knowledge_root)

    assert get_knowledge_root(config) == knowledge_root


def test_get_knowledge_root_ignores_environment_variable(monkeypatch, tmp_path):
    """旧环境变量不得覆盖配置中的知识库路径."""
    default_root = tmp_path / "default"
    environment_root = tmp_path / "environment"

    monkeypatch.setattr(paths, "get_default_knowledge_dir", lambda: default_root)
    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", str(environment_root))

    assert get_knowledge_root(AppConfig(platform="linux")) == default_root


def test_get_knowledge_root_prefers_config_path_over_environment_variable(monkeypatch, tmp_path):
    """配置中的自定义路径应优先于旧环境变量."""
    config_root = tmp_path / "config-knowledge"
    environment_root = tmp_path / "environment-knowledge"

    monkeypatch.setenv("LCMD_KNOWLEDGE_DIR", str(environment_root))
    config = AppConfig(platform="linux", path=config_root)

    assert get_knowledge_root(config) == config_root


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


def test_custom_missing_path_does_not_fallback_to_default(monkeypatch, tmp_path):
    """自定义目录不存在时应报错，不得回退默认目录."""
    default_root = tmp_path / "default"
    custom_root = tmp_path / "missing-custom"

    default_root.mkdir()
    monkeypatch.setattr(paths, "get_default_knowledge_dir", lambda: default_root)

    config = AppConfig(platform="linux", path=custom_root)
    selected_root = get_knowledge_root(config)

    assert selected_root == custom_root

    with pytest.raises(PathError, match="目录不存在"):
        validate_knowledge_root(selected_root)


def test_get_knowledge_dirs_uses_config(monkeypatch, tmp_path):
    """命令和任务目录应根据知识库路径、平台及语言配置推导."""
    knowledge_root = tmp_path / "knowledge"
    config = AppConfig(
        platform="windows",
        language="zh-CN",
        path=knowledge_root,
    )

    result = get_knowledge_dirs(config)

    assert result == KnowledgeDirs(
        root=knowledge_root,
        commands=knowledge_root / "commands" / "windows" / "zh-CN",
        tasks=knowledge_root / "tasks" / "windows" / "zh-CN",
    )


def test_get_knowledge_dirs_uses_default_when_config_path_missing(monkeypatch, tmp_path):
    """未指定自定义路径时应从默认知识库目录推导."""
    monkeypatch.setattr(paths, "get_default_knowledge_dir", lambda: tmp_path)

    result = get_knowledge_dirs(AppConfig(platform="linux"))

    assert result.root == tmp_path
    assert result.commands == tmp_path / "commands" / "linux" / "zh-CN"
    assert result.tasks == tmp_path / "tasks" / "linux" / "zh-CN"


def test_get_knowledge_dirs_does_not_create_directories(tmp_path):
    """计算路径时不得自动创建知识库目录."""
    knowledge_root = tmp_path / "knowledge"
    config = AppConfig(platform="linux", path=knowledge_root)

    result = get_knowledge_dirs(config)

    assert result.commands == knowledge_root / "commands" / "linux" / "zh-CN"
    assert result.tasks == knowledge_root / "tasks" / "linux" / "zh-CN"
    assert not result.root.exists()
