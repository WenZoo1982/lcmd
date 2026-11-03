from io import StringIO

import pytest
from rich.console import Console

from lcmd.knowledge.models import (
    KnowledgeDocument,
    QueryResult,
    SearchResult,
)
from lcmd.output.renderer import (
    render_document,
    render_query_result,
    render_search_results,
)


def make_document(
    document_id="platforms/windows/zh-CN/dir.md",
    category="platforms",
    platform="windows",
    tool=None,
    summary="查看当前目录中的文件和子目录。",
    body="---\n\n## 用途\n\n显示文件和子目录。\n",
):
    return KnowledgeDocument(
        id=document_id,
        category=category,
        platform=platform,
        tool=tool,
        language="zh-CN",
        summary=summary,
        body=body,
    )


def make_console(force_terminal=False):
    stream = StringIO()

    console = Console(
        file=stream,
        force_terminal=force_terminal,
        width=120,
        color_system=None,
    )

    return console, stream


def make_search_results(count):
    return tuple(
        SearchResult(
            document=make_document(
                document_id=f"platforms/windows/zh-CN/command-{index}.md",
                summary=f"命令 {index} 的用途摘要。",
            ),
            score=float(count - index),
        )
        for index in range(count)
    )


def test_render_document_displays_platform_document():
    console, stream = make_console()

    render_document(make_document(), console)

    output = stream.getvalue()

    assert "dir" in output
    assert "平台命令" in output
    assert "windows" in output
    assert "显示文件和子目录" in output


def test_render_document_displays_tool_document():
    console, stream = make_console()

    document = make_document(
        document_id="tools/git/zh-CN/compose/up.md",
        category="tools",
        platform=None,
        tool="git",
    )

    render_document(document, console)

    output = stream.getvalue()

    assert "compose up" in output
    assert "第三方工具" in output
    assert "git" in output


def test_render_query_result_displays_documents():
    console, stream = make_console()

    result = QueryResult(
        documents=(make_document(),),
        children=(),
    )

    render_query_result(result, console)

    output = stream.getvalue()

    assert "dir" in output
    assert "平台命令" in output


def test_render_query_result_displays_children():
    console, stream = make_console()

    result = QueryResult(
        documents=(),
        children=("compose", "run"),
    )

    render_query_result(result, console)

    output = stream.getvalue()

    assert "可用子命令" in output
    assert "compose" in output
    assert "run" in output


def test_render_query_result_displays_documents_and_children():
    console, stream = make_console()

    result = QueryResult(
        documents=(make_document(),),
        children=("compose", "run"),
    )

    render_query_result(result, console)

    output = stream.getvalue()

    assert "dir" in output
    assert "compose" in output
    assert "run" in output


def test_render_query_result_displays_platform_command_and_same_named_tool():
    console, stream = make_console()

    platform_document = make_document(
        document_id="platforms/windows/zh-CN/git.md",
        body="---\n\n## 用途\n\nWindows 平台 Git 命令正文。\n",
    )

    tool_document = make_document(
        document_id="tools/git/zh-CN/git.md",
        category="tools",
        platform=None,
        tool="git",
        body="---\n\n## 用途\n\nGit 第三方工具正文。\n",
    )

    result = QueryResult(
        documents=(platform_document, tool_document),
        children=(),
    )

    render_query_result(result, console)

    output = stream.getvalue()

    assert output.count("git") >= 2
    assert "平台命令" in output
    assert "第三方工具" in output
    assert "Windows 平台 Git 命令正文" in output
    assert "Git 第三方工具正文" in output


def test_render_query_result_displays_empty_message():
    console, stream = make_console()

    render_query_result(
        QueryResult(documents=(), children=()),
        console,
    )

    assert "未找到相关命令或工具" in stream.getvalue()


def test_render_search_results_displays_empty_message():
    console, stream = make_console()

    render_search_results((), console)

    assert "未找到相关命令或工具" in stream.getvalue()


def test_render_search_results_displays_results():
    console, stream = make_console()

    render_search_results(make_search_results(3), console)

    output = stream.getvalue()

    assert "command-0" in output
    assert "command-1" in output
    assert "command-2" in output
    assert "命令 0 的用途摘要" in output


def test_render_search_results_does_not_paginate_five_results():
    console, stream = make_console(force_terminal=True)

    render_search_results(make_search_results(5), console)

    output = stream.getvalue()

    assert "command-0" in output
    assert "command-4" in output
    assert "按 Enter 查看下一页" not in output


def test_render_search_results_non_terminal_displays_all_results():
    console, stream = make_console(force_terminal=False)

    render_search_results(make_search_results(12), console)

    output = stream.getvalue()

    for index in range(12):
        assert f"command-{index}" in output

    assert "按 Enter 查看下一页" not in output


def test_render_search_results_paginates_interactively(monkeypatch):
    console, stream = make_console(force_terminal=True)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    answers = iter(["", ""])

    monkeypatch.setattr(
        console,
        "input",
        lambda prompt: next(answers),
    )

    render_search_results(make_search_results(12), console)

    output = stream.getvalue()

    assert "command-0" in output
    assert "command-5" in output
    assert "command-10" in output
    assert output.count("搜索结果") == 3


def test_render_search_results_quits_when_user_enters_q(monkeypatch):
    console, stream = make_console(force_terminal=True)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    monkeypatch.setattr(
        console,
        "input",
        lambda prompt: "q",
    )

    render_search_results(make_search_results(12), console)

    output = stream.getvalue()

    assert "command-0" in output
    assert "command-4" in output
    assert "command-5" not in output


def test_render_search_results_ignores_invalid_input(monkeypatch):
    console, stream = make_console(force_terminal=True)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    answers = iter(["invalid", "", "q"])

    monkeypatch.setattr(
        console,
        "input",
        lambda prompt: next(answers),
    )

    render_search_results(make_search_results(12), console)

    output = stream.getvalue()

    assert "command-0" in output
    assert "command-5" in output
    assert "command-10" not in output


def test_render_search_results_supports_custom_page_size(monkeypatch):
    console, stream = make_console(force_terminal=True)

    answers = iter([""])

    monkeypatch.setattr(
        console,
        "input",
        lambda prompt: next(answers),
    )

    render_search_results(
        make_search_results(6),
        console,
        page_size=3,
    )

    output = stream.getvalue()

    assert "command-0" in output
    assert "command-2" in output
    assert "command-3" in output


def test_render_search_results_rejects_invalid_page_size():
    console, _ = make_console()

    with pytest.raises(ValueError):
        render_search_results(
            make_search_results(3),
            console,
            page_size=0,
        )
