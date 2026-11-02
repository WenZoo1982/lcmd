"""Knowledge Loader 测试."""

import json
from pathlib import Path

import pytest

from lcmd.core.config import AppConfig
from lcmd.core.paths import KnowledgeDirs
from lcmd.knowledge.loader import (
    KnowledgeLoadError,
    load_knowledge,
    load_knowledge_version,
)


@pytest.fixture
def knowledge_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """创建临时知识库，并将 Loader 指向该目录."""
    import lcmd.knowledge.loader as loader

    root = tmp_path / "knowledge"
    commands = root / "commands" / "linux" / "zh-CN"

    root.mkdir()
    commands.mkdir(parents=True)

    (root / "manifest.json").write_text(
        json.dumps({"version": "0.1.0"}),
        encoding="utf-8",
    )

    dirs = KnowledgeDirs(
        root=root,
        commands=commands,
    )

    monkeypatch.setattr(loader, "get_knowledge_dirs", lambda config: dirs)
    monkeypatch.setattr(loader, "__version__", "0.1.0")

    return {
        "root": root,
        "commands": commands,
        "dirs": dirs,
        "config": AppConfig(platform="linux", language="zh-CN"),
    }


def test_load_knowledge_version(knowledge_env):
    """应只读取并返回知识库清单中的版本."""
    version = load_knowledge_version(knowledge_env["config"])

    assert version == "0.1.0"


def test_load_knowledge_version_does_not_load_markdown(knowledge_env):
    """读取知识库版本时不应加载 Markdown 文档."""
    (knowledge_env["commands"] / "invalid.md").write_text(
        "这不是有效的知识文档格式",
        encoding="utf-8",
    )

    version = load_knowledge_version(knowledge_env["config"])

    assert version == "0.1.0"


def write_document(path: Path, summary: str, body: str) -> None:
    """写入符合第一版格式的 Markdown 知识文档."""
    path.write_text(
        f'+++\nsummary = "{summary}"\n+++\n\n{body}\n',
        encoding="utf-8",
    )


def test_load_valid_command_document(knowledge_env):
    """有效命令文档应被正确加载."""
    write_document(
        knowledge_env["commands"] / "ls.md",
        "查看目录中的文件和文件夹",
        "## 基本语法\n\n`ls [选项] [目录]`",
    )

    result = load_knowledge(knowledge_env["config"])

    assert len(result.commands) == 1
    assert result.commands[0].name == "ls"
    assert result.commands[0].metadata["summary"] == "查看目录中的文件和文件夹"
    assert "`ls [选项] [目录]`" in result.commands[0].body
    assert result.commands[0].path == knowledge_env["commands"] / "ls.md"
    assert result.diagnostics == []


def test_load_multiple_documents_in_stable_name_order(knowledge_env):
    """多个文档应全部加载，并按名称稳定排序."""
    write_document(knowledge_env["commands"] / "pwd.md", "显示当前目录", "正文")
    write_document(knowledge_env["commands"] / "ls.md", "查看目录内容", "正文")
    write_document(knowledge_env["commands"] / "cd.md", "切换目录", "正文")

    result = load_knowledge(knowledge_env["config"])

    assert [document.name for document in result.commands] == [
        "cd",
        "ls",
        "pwd",
    ]


def test_missing_command_directory_is_allowed(knowledge_env):
    """命令目录不存在时仍应允许加载."""
    knowledge_env["commands"].rmdir()

    result = load_knowledge(knowledge_env["config"])

    assert result.commands == []
    assert result.diagnostics == []


def test_empty_command_directory_is_allowed(knowledge_env):
    """命令目录为空时不应报错."""
    result = load_knowledge(knowledge_env["config"])

    assert result.commands == []
    assert result.diagnostics == []


def test_only_current_platform_and_language_documents_are_loaded(
    knowledge_env,
):
    """只加载配置指定的平台和语言目录."""
    write_document(knowledge_env["commands"] / "ls.md", "Linux 中文命令", "正文")

    other_platform = knowledge_env["root"] / "commands" / "windows" / "zh-CN"
    other_language = knowledge_env["root"] / "commands" / "linux" / "en"
    other_platform.mkdir(parents=True)
    other_language.mkdir(parents=True)

    write_document(other_platform / "dir.md", "Windows 命令", "正文")
    write_document(other_language / "ls.md", "Linux 英文命令", "正文")

    result = load_knowledge(knowledge_env["config"])

    assert [document.name for document in result.commands] == ["ls"]
    assert result.commands[0].metadata["summary"] == "Linux 中文命令"


def test_invalid_document_is_skipped_and_valid_document_is_loaded(
    knowledge_env,
):
    """无效文档应被跳过，不影响其他有效文档."""
    write_document(knowledge_env["commands"] / "ls.md", "查看目录内容", "有效正文")

    (knowledge_env["commands"] / "bad.md").write_text(
        "这不是有效的 Front Matter 文档",
        encoding="utf-8",
    )

    result = load_knowledge(knowledge_env["config"])

    assert [document.name for document in result.commands] == ["ls"]
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].path == knowledge_env["commands"] / "bad.md"
    assert result.diagnostics[0].message


def test_schema_invalid_document_is_skipped(knowledge_env):
    """Schema 校验失败的文档应被跳过并记录诊断."""
    write_document(knowledge_env["commands"] / "ls.md", "查看目录内容", "有效正文")

    (knowledge_env["commands"] / "bad.md").write_text(
        '+++\nunknown = "value"\n+++\n\n正文\n',
        encoding="utf-8",
    )

    result = load_knowledge(knowledge_env["config"])

    assert [document.name for document in result.commands] == ["ls"]
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].path == knowledge_env["commands"] / "bad.md"


def test_unreadable_utf8_document_is_skipped(knowledge_env):
    """无法按 UTF-8 解码的文档应被跳过并记录诊断."""
    write_document(knowledge_env["commands"] / "ls.md", "查看目录内容", "有效正文")

    invalid_file = knowledge_env["commands"] / "bad.md"
    invalid_file.write_bytes(b"\xff\xfe\xfa")

    result = load_knowledge(knowledge_env["config"])

    assert [document.name for document in result.commands] == ["ls"]
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].path == invalid_file


def test_missing_manifest_raises_knowledge_load_error(knowledge_env):
    """缺少 manifest.json 属于知识库级错误."""
    (knowledge_env["root"] / "manifest.json").unlink()

    with pytest.raises(KnowledgeLoadError, match="manifest"):
        load_knowledge(knowledge_env["config"])


def test_invalid_manifest_json_raises_knowledge_load_error(knowledge_env):
    """manifest.json JSON 格式错误应终止加载."""
    (knowledge_env["root"] / "manifest.json").write_text(
        '{"version": ',
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeLoadError, match="manifest"):
        load_knowledge(knowledge_env["config"])


@pytest.mark.parametrize(
    "manifest_content",
    [
        "[]",
        '"0.1.0"',
        '{"version": "0.1.0", "platforms": ["linux"]}',
        '{"platforms": ["linux"]}',
        '{"version": 1}',
        '{"version": ""}',
        '{"version": "v0.1.0"}',
        '{"version": "0.1"}',
        '{"version": "00.1.0"}',
    ],
)
def test_invalid_manifest_schema_or_version_raises_error(
    knowledge_env,
    manifest_content,
):
    """清单结构错误或版本格式错误应终止加载."""
    (knowledge_env["root"] / "manifest.json").write_text(
        manifest_content,
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeLoadError):
        load_knowledge(knowledge_env["config"])


@pytest.mark.parametrize(
    "knowledge_version",
    [
        "0.0.1",
        "0.1.0",
        "0.9.9",
        "0.1.0-beta.1",
        "0.1.0+build.1",
    ],
)
def test_same_major_version_is_compatible(
    knowledge_env,
    knowledge_version,
):
    """主版本号相同即兼容，Minor、Patch 和 SemVer 附加信息不影响判断."""
    (knowledge_env["root"] / "manifest.json").write_text(
        json.dumps({"version": knowledge_version}),
        encoding="utf-8",
    )

    result = load_knowledge(knowledge_env["config"])

    assert result.commands == []


def test_older_knowledge_major_version_raises_error(knowledge_env):
    """知识库 Major 低于主程序时应要求更新知识库."""
    (knowledge_env["root"] / "manifest.json").write_text(
        json.dumps({"version": "0.9.9"}),
        encoding="utf-8",
    )

    import lcmd.knowledge.loader as loader

    monkeypatch_version = loader.__version__
    try:
        loader.__version__ = "1.0.0"

        with pytest.raises(KnowledgeLoadError, match="知识库"):
            load_knowledge(knowledge_env["config"])
    finally:
        loader.__version__ = monkeypatch_version


def test_newer_knowledge_major_version_raises_error(knowledge_env):
    """知识库 Major 高于主程序时应要求升级主程序."""
    (knowledge_env["root"] / "manifest.json").write_text(
        json.dumps({"version": "1.0.0"}),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeLoadError, match="主程序"):
        load_knowledge(knowledge_env["config"])


def test_missing_knowledge_root_raises_knowledge_load_error(
    knowledge_env,
):
    """知识库根目录不存在时应终止加载."""
    import lcmd.knowledge.loader as loader

    missing_root = knowledge_env["root"] / "missing"
    missing_dirs = KnowledgeDirs(
        root=missing_root,
        commands=missing_root / "commands",
    )
    monkeypatch_dirs = loader.get_knowledge_dirs
    try:
        loader.get_knowledge_dirs = lambda config: missing_dirs

        with pytest.raises(KnowledgeLoadError):
            load_knowledge(knowledge_env["config"])
    finally:
        loader.get_knowledge_dirs = monkeypatch_dirs


def test_knowledge_root_is_file_raises_knowledge_load_error(
    knowledge_env,
):
    """知识库根路径是普通文件时应终止加载."""
    import lcmd.knowledge.loader as loader

    file_root = knowledge_env["root"] / "not-a-directory"
    file_root.write_text("not a directory", encoding="utf-8")

    file_dirs = KnowledgeDirs(
        root=file_root,
        commands=file_root / "commands",
    )
    monkeypatch_dirs = loader.get_knowledge_dirs
    try:
        loader.get_knowledge_dirs = lambda config: file_dirs

        with pytest.raises(KnowledgeLoadError):
            load_knowledge(knowledge_env["config"])
    finally:
        loader.get_knowledge_dirs = monkeypatch_dirs


def test_load_common_command_when_platform_command_missing(knowledge_env):
    """平台没有对应命令时应回退加载 common 文档."""
    common_dir = knowledge_env["root"] / "commands" / "common" / "zh-CN"
    common_dir.mkdir(parents=True)

    write_document(common_dir / "git.md", "版本控制工具", "Git 通用说明")

    result = load_knowledge(knowledge_env["config"])

    assert [document.name for document in result.commands] == ["git"]
    assert result.commands[0].metadata["summary"] == "版本控制工具"
    assert result.commands[0].path == common_dir / "git.md"


def test_platform_command_takes_priority_over_common(knowledge_env):
    """平台与 common 存在同名命令时只加载平台文档."""
    common_dir = knowledge_env["root"] / "commands" / "common" / "zh-CN"
    common_dir.mkdir(parents=True)

    write_document(common_dir / "git.md", "通用 Git 说明", "Common Git")
    write_document(
        knowledge_env["commands"] / "git.md",
        "Linux Git 说明",
        "Linux Git",
    )

    result = load_knowledge(knowledge_env["config"])

    assert [document.name for document in result.commands] == ["git"]
    assert result.commands[0].metadata["summary"] == "Linux Git 说明"
    assert result.commands[0].path == knowledge_env["commands"] / "git.md"


def test_common_fills_commands_missing_from_platform(knowledge_env):
    """common 应补充平台目录中没有的命令."""
    common_dir = knowledge_env["root"] / "commands" / "common" / "zh-CN"
    common_dir.mkdir(parents=True)

    write_document(common_dir / "git.md", "通用 Git", "Common Git")
    write_document(common_dir / "ls.md", "通用 ls", "Common ls")
    write_document(
        knowledge_env["commands"] / "ls.md",
        "Linux ls",
        "Linux ls",
    )

    result = load_knowledge(knowledge_env["config"])
    documents = {doc.name: doc for doc in result.commands}

    assert set(documents) == {"git", "ls"}
    assert documents["git"].metadata["summary"] == "通用 Git"
    assert documents["ls"].metadata["summary"] == "Linux ls"
