from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from lcmd.knowledge.models import (
    KnowledgeBase,
    KnowledgeCatalog,
    KnowledgeDocument,
    PlatformInfo,
    QueryResult,
    SearchResult,
    ToolInfo,
)


def test_platform_info() -> None:
    platform = PlatformInfo(
        name="windows",
        languages=("zh-CN", "en-US"),
    )

    assert platform.name == "windows"
    assert platform.languages == ("zh-CN", "en-US")


def test_tool_info() -> None:
    tool = ToolInfo(
        name="git",
        languages=("zh-CN",),
    )

    assert tool.name == "git"
    assert tool.languages == ("zh-CN",)


def test_knowledge_catalog() -> None:
    catalog = KnowledgeCatalog(
        root=Path("D:/lcmd-kb"),
        version="0.1.0",
        platforms=(PlatformInfo("windows", ("zh-CN",)),),
        tools=(ToolInfo("git", ("zh-CN",)),),
    )

    assert catalog.root == Path("D:/lcmd-kb")
    assert catalog.version == "0.1.0"
    assert len(catalog.platforms) == 1
    assert len(catalog.tools) == 1


def test_platform_document() -> None:
    document = KnowledgeDocument(
        id="platforms/windows/zh-CN/dir.md",
        category="platforms",
        platform="windows",
        tool=None,
        language="zh-CN",
        summary="查看目录内容。",
        body="## 用途\n\n查看文件和目录。",
    )

    assert document.category == "platforms"
    assert document.platform == "windows"
    assert document.tool is None


def test_tool_document() -> None:
    document = KnowledgeDocument(
        id="tools/git/zh-CN/init.md",
        category="tools",
        platform=None,
        tool="git",
        language="zh-CN",
        summary="初始化 Git 仓库。",
        body="## 用途\n\n创建 Git 仓库。",
    )

    assert document.category == "tools"
    assert document.platform is None
    assert document.tool == "git"


def test_document_requires_exactly_one_owner() -> None:
    with pytest.raises(ValueError):
        KnowledgeDocument(
            id="invalid.md",
            category="platforms",
            platform=None,
            tool=None,
            language="zh-CN",
            summary="测试。",
            body="正文。",
        )

    with pytest.raises(ValueError):
        KnowledgeDocument(
            id="invalid.md",
            category="platforms",
            platform="windows",
            tool="git",
            language="zh-CN",
            summary="测试。",
            body="正文。",
        )


def test_document_category_must_match_owner() -> None:
    with pytest.raises(ValueError):
        KnowledgeDocument(
            id="invalid.md",
            category="platforms",
            platform=None,
            tool="git",
            language="zh-CN",
            summary="测试。",
            body="正文。",
        )

    with pytest.raises(ValueError):
        KnowledgeDocument(
            id="invalid.md",
            category="tools",
            platform="windows",
            tool=None,
            language="zh-CN",
            summary="测试。",
            body="正文。",
        )


def test_knowledge_base() -> None:
    document = KnowledgeDocument(
        id="platforms/windows/zh-CN/dir.md",
        category="platforms",
        platform="windows",
        tool=None,
        language="zh-CN",
        summary="查看目录内容。",
        body="正文。",
    )

    knowledge = KnowledgeBase(
        platform="windows",
        language="zh-CN",
        documents=(document,),
    )

    assert knowledge.platform == "windows"
    assert knowledge.language == "zh-CN"
    assert knowledge.documents == (document,)


def test_query_result_supports_documents_and_children() -> None:
    document = KnowledgeDocument(
        id="tools/docker/zh-CN/compose.md",
        category="tools",
        platform=None,
        tool="docker",
        language="zh-CN",
        summary="管理 Docker Compose。",
        body="正文。",
    )

    result = QueryResult(
        documents=(document,),
        children=("up", "down"),
    )

    assert result.documents == (document,)
    assert result.children == ("up", "down")


def test_search_result() -> None:
    document = KnowledgeDocument(
        id="platforms/linux/zh-CN/ls.md",
        category="platforms",
        platform="linux",
        tool=None,
        language="zh-CN",
        summary="列出目录内容。",
        body="正文。",
    )

    result = SearchResult(
        document=document,
        score=1.5,
    )

    assert result.document == document
    assert result.score == 1.5


def test_models_are_immutable() -> None:
    platform = PlatformInfo(
        name="windows",
        languages=("zh-CN",),
    )

    with pytest.raises(FrozenInstanceError):
        platform.name = "linux"  # type: ignore[misc]


def test_models_use_slots() -> None:
    platform = PlatformInfo(
        name="windows",
        languages=("zh-CN",),
    )

    assert not hasattr(platform, "__dict__")
