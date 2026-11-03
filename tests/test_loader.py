import json
import shutil
from pathlib import Path

import pytest

from lcmd.knowledge.loader import (
    KnowledgeLoadError,
    discover_catalog,
    load_knowledge,
)


def create_knowledge_root(tmp_path):
    root = tmp_path / "knowledge"

    for path in (
        "commands/platforms/windows/zh-CN",
        "commands/platforms/linux/en-US",
        "commands/tools/git/zh-CN",
    ):
        (root / path).mkdir(parents=True)

    (root / "manifest.json").write_text(
        json.dumps({"version": "0.1.0"}),
        encoding="utf-8",
    )

    return root


def write_document(path, summary="测试文档。", body="测试正文。"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'+++\nsummary = "{summary}"\n+++\n---\n\n{body}\n',
        encoding="utf-8",
    )


class FakeEntry:
    """用于模拟 Windows 文件系统无法直接创建的大小写冲突目录项。"""

    def __init__(self, directory, name, is_directory=False):
        self.directory = directory
        self.name = name
        self._is_directory = is_directory

    @property
    def suffix(self):
        return Path(self.name).suffix

    @property
    def stem(self):
        return Path(self.name).stem

    def is_symlink(self):
        return False

    def is_dir(self):
        return self._is_directory

    def is_file(self):
        return not self._is_directory

    def resolve(self, strict=False):
        if self._is_directory:
            return self.directory.resolve(strict=strict)

        return (self.directory / "dir.md").resolve(strict=strict)

    def iterdir(self):
        if not self._is_directory:
            raise NotADirectoryError(self.name)

        return iter([FakeEntry(self.directory, f"{self.name}/child.md")])

    def relative_to(self, other):
        return (self.directory / self.name).relative_to(other)

    def read_text(self, encoding=None):
        return '+++\nsummary = "冲突测试文档。"\n+++\n---\n\n测试正文。\n'


def add_fake_entries(monkeypatch, directory, fake_entries):
    """在指定目录的枚举结果中加入模拟目录项。"""
    original_iterdir = Path.iterdir

    def patched_iterdir(path):
        if path == directory:
            return iter([*original_iterdir(path), *fake_entries])

        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", patched_iterdir)


def test_discover_catalog_returns_platforms_and_tools(tmp_path):
    root = create_knowledge_root(tmp_path)

    catalog = discover_catalog(root)

    assert catalog.version == "0.1.0"
    assert catalog.root == root.resolve()

    assert [(item.name, item.languages) for item in catalog.platforms] == [
        ("linux", ("en-US",)),
        ("windows", ("zh-CN",)),
    ]

    assert [(item.name, item.languages) for item in catalog.tools] == [
        ("git", ("zh-CN",)),
    ]


def test_discover_catalog_accepts_missing_tools_directory(tmp_path):
    root = create_knowledge_root(tmp_path)
    shutil.rmtree(root / "commands" / "tools")

    catalog = discover_catalog(root)

    assert catalog.tools == ()


def test_discover_catalog_rejects_missing_root(tmp_path):
    with pytest.raises(KnowledgeLoadError):
        discover_catalog(tmp_path / "missing")


def test_discover_catalog_rejects_missing_manifest(tmp_path):
    root = create_knowledge_root(tmp_path)
    (root / "manifest.json").unlink()

    with pytest.raises(KnowledgeLoadError):
        discover_catalog(root)


def test_discover_catalog_rejects_invalid_manifest_json(tmp_path):
    root = create_knowledge_root(tmp_path)
    (root / "manifest.json").write_text("{invalid", encoding="utf-8")

    with pytest.raises(KnowledgeLoadError):
        discover_catalog(root)


def test_discover_catalog_rejects_unknown_manifest_field(tmp_path):
    root = create_knowledge_root(tmp_path)
    (root / "manifest.json").write_text(
        json.dumps({"version": "0.1.0", "name": "test"}),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeLoadError):
        discover_catalog(root)


@pytest.mark.parametrize(
    "version",
    ["1.0.0", "0.1", "0.1.0-beta", "v0.1.0", "", 1],
)
def test_discover_catalog_rejects_invalid_version(tmp_path, version):
    root = create_knowledge_root(tmp_path)
    (root / "manifest.json").write_text(
        json.dumps({"version": version}),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeLoadError):
        discover_catalog(root)


def test_discover_catalog_rejects_missing_platforms_directory(tmp_path):
    root = create_knowledge_root(tmp_path)
    shutil.rmtree(root / "commands" / "platforms")

    with pytest.raises(KnowledgeLoadError):
        discover_catalog(root)


@pytest.mark.parametrize(
    "platform",
    ["Windows", "my_platform", "my platform", "中文", "CON"],
)
def test_discover_catalog_rejects_invalid_platform_name(
    tmp_path,
    platform,
):
    root = create_knowledge_root(tmp_path)
    original = root / "commands" / "platforms" / "windows"
    original.rename(original.with_name(platform))

    with pytest.raises(KnowledgeLoadError):
        discover_catalog(root)


@pytest.mark.parametrize(
    "language",
    ["zh-cn", "ZH-CN", "zh_CN", "中文", "english"],
)
def test_discover_catalog_rejects_invalid_language_name(
    tmp_path,
    language,
):
    root = create_knowledge_root(tmp_path)
    original = root / "commands" / "platforms" / "windows" / "zh-CN"
    original.rename(original.with_name(language))

    with pytest.raises(KnowledgeLoadError):
        discover_catalog(root)


def test_discover_catalog_rejects_invalid_tool_name(tmp_path):
    root = create_knowledge_root(tmp_path)
    original = root / "commands" / "tools" / "git"
    original.rename(original.with_name("my_tool"))

    with pytest.raises(KnowledgeLoadError):
        discover_catalog(root)


def test_load_knowledge_loads_platform_and_tool_documents(tmp_path):
    root = create_knowledge_root(tmp_path)

    write_document(
        root / "commands/platforms/windows/zh-CN/dir.md",
        "查看目录内容。",
    )
    write_document(
        root / "commands/tools/git/zh-CN/status.md",
        "查看 Git 状态。",
    )

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    assert knowledge.platform == "windows"
    assert knowledge.language == "zh-CN"

    assert [item.id for item in knowledge.documents] == [
        "platforms/windows/zh-CN/dir.md",
        "tools/git/zh-CN/status.md",
    ]


def test_load_knowledge_accepts_uppercase_platform_input(tmp_path):
    root = create_knowledge_root(tmp_path)
    write_document(root / "commands/platforms/windows/zh-CN/dir.md")

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "WINDOWS", "zh-CN")

    assert knowledge.platform == "windows"


def test_load_knowledge_rejects_unknown_platform(tmp_path):
    root = create_knowledge_root(tmp_path)
    catalog = discover_catalog(root)

    with pytest.raises(KnowledgeLoadError):
        load_knowledge(catalog, "macos", "zh-CN")


def test_load_knowledge_rejects_unavailable_language(tmp_path):
    root = create_knowledge_root(tmp_path)
    catalog = discover_catalog(root)

    with pytest.raises(KnowledgeLoadError):
        load_knowledge(catalog, "windows", "en-US")


def test_load_knowledge_rejects_platform_without_valid_documents(tmp_path):
    root = create_knowledge_root(tmp_path)
    catalog = discover_catalog(root)

    with pytest.raises(KnowledgeLoadError):
        load_knowledge(catalog, "windows", "zh-CN")


def test_load_knowledge_skips_invalid_document(tmp_path):
    root = create_knowledge_root(tmp_path)

    write_document(root / "commands/platforms/windows/zh-CN/dir.md")
    (root / "commands/platforms/windows/zh-CN/bad.md").write_text(
        "这不是有效的知识文档。",
        encoding="utf-8",
    )

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    assert [item.id for item in knowledge.documents] == [
        "platforms/windows/zh-CN/dir.md",
    ]


def test_load_knowledge_skips_tool_without_current_language(tmp_path):
    root = create_knowledge_root(tmp_path)

    write_document(root / "commands/platforms/windows/zh-CN/dir.md")
    write_document(root / "commands/platforms/linux/en-US/ls.md")
    write_document(root / "commands/tools/git/zh-CN/status.md")

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "linux", "en-US")

    assert [item.id for item in knowledge.documents] == [
        "platforms/linux/en-US/ls.md",
    ]


def test_load_knowledge_skips_invalid_tool_document(tmp_path):
    root = create_knowledge_root(tmp_path)

    write_document(root / "commands/platforms/windows/zh-CN/dir.md")
    (root / "commands/tools/git/zh-CN/bad.md").write_text(
        "无效文档",
        encoding="utf-8",
    )

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    assert [item.id for item in knowledge.documents] == [
        "platforms/windows/zh-CN/dir.md",
    ]


@pytest.mark.parametrize(
    "filename",
    ["Bad.md", "my_file.md", "CON.md", "bad.MD"],
)
def test_load_knowledge_skips_invalid_document_filename(
    tmp_path,
    filename,
):
    root = create_knowledge_root(tmp_path)

    write_document(root / "commands/platforms/windows/zh-CN/dir.md")
    write_document(root / "commands/platforms/windows/zh-CN" / filename)

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    assert [item.id for item in knowledge.documents] == [
        "platforms/windows/zh-CN/dir.md",
    ]


def test_load_knowledge_loads_nested_tool_documents(tmp_path):
    root = create_knowledge_root(tmp_path)

    write_document(root / "commands/platforms/windows/zh-CN/dir.md")
    write_document(root / "commands/tools/git/zh-CN/remote/add.md")

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    assert "tools/git/zh-CN/remote/add.md" in [item.id for item in knowledge.documents]


def test_load_knowledge_skips_symlinked_document(tmp_path):
    root = create_knowledge_root(tmp_path)

    write_document(root / "commands/platforms/windows/zh-CN/dir.md")

    outside = tmp_path / "outside.md"
    write_document(outside)

    link = root / "commands/platforms/windows/zh-CN/external.md"

    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建符号链接。")

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    assert "platforms/windows/zh-CN/external.md" not in [item.id for item in knowledge.documents]


def test_load_knowledge_skips_symlinked_directory(tmp_path):
    root = create_knowledge_root(tmp_path)

    write_document(root / "commands/platforms/windows/zh-CN/dir.md")

    outside = tmp_path / "outside"
    outside.mkdir()
    write_document(outside / "external.md")

    link = root / "commands/platforms/windows/zh-CN/external"

    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建符号链接。")

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    assert not any("external" in item.id for item in knowledge.documents)


def test_load_knowledge_loads_document_and_same_named_directory(tmp_path):
    root = create_knowledge_root(tmp_path)
    directory = root / "commands/platforms/windows/zh-CN"

    write_document(directory / "dir.md")
    write_document(directory / "foo.md")
    write_document(directory / "foo" / "bar.md")

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    document_ids = {item.id for item in knowledge.documents}

    assert "platforms/windows/zh-CN/foo.md" in document_ids
    assert "platforms/windows/zh-CN/foo/bar.md" in document_ids


def test_load_knowledge_rejects_all_case_conflicting_markdown_files(
    tmp_path,
    monkeypatch,
):
    root = create_knowledge_root(tmp_path)
    directory = root / "commands/platforms/windows/zh-CN"

    write_document(directory / "dir.md")

    fake_entries = [
        FakeEntry(directory, "Foo.md"),
        FakeEntry(directory, "foo.md"),
    ]
    add_fake_entries(monkeypatch, directory, fake_entries)

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    document_ids = {item.id for item in knowledge.documents}

    assert document_ids == {"platforms/windows/zh-CN/dir.md"}
    assert not any(item.endswith("/Foo.md") for item in document_ids)
    assert not any(item.endswith("/foo.md") for item in document_ids)


def test_load_knowledge_rejects_all_case_conflicting_directories(
    tmp_path,
    monkeypatch,
):
    root = create_knowledge_root(tmp_path)
    directory = root / "commands/platforms/windows/zh-CN"

    write_document(directory / "dir.md")

    fake_entries = [
        FakeEntry(directory, "Foo", is_directory=True),
        FakeEntry(directory, "foo", is_directory=True),
    ]
    add_fake_entries(monkeypatch, directory, fake_entries)

    catalog = discover_catalog(root)
    knowledge = load_knowledge(catalog, "windows", "zh-CN")

    document_ids = {item.id for item in knowledge.documents}

    assert document_ids == {"platforms/windows/zh-CN/dir.md"}
    assert not any("/Foo/" in item for item in document_ids)
    assert not any("/foo/" in item for item in document_ids)
