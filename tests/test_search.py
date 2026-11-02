"""LCMD 命令关键词搜索测试."""

from pathlib import Path

from lcmd.knowledge.loader import LoadedDocument
from lcmd.knowledge.search import search_commands


def make_command(
    name: str,
    summary: str,
    body: str = "",
) -> LoadedDocument:
    """创建测试命令文档."""
    return LoadedDocument(
        name=name,
        path=Path(f"commands/linux/zh-CN/{name}.md"),
        metadata={"summary": summary},
        body=body,
    )


def test_search_matches_command_name():
    """普通搜索应匹配命令名称."""
    command = make_command("copy", "复制文件")

    assert search_commands([command], "copy") == [command]


def test_search_matches_summary():
    """普通搜索应匹配 summary."""
    command = make_command("cp", "复制文件和目录")

    assert search_commands([command], "复制文件") == [command]


def test_search_does_not_match_body_without_full():
    """普通搜索不应匹配 Markdown 正文."""
    command = make_command("cp", "复制文件", "保留文件属性")

    assert search_commands([command], "保留文件") == []


def test_full_search_matches_body():
    """full 模式应额外匹配 Markdown 正文."""
    command = make_command("cp", "复制文件", "保留文件属性")

    assert search_commands([command], "保留文件", full=True) == [command]


def test_search_uses_or_matching():
    """多个关键词采用 OR 匹配."""
    command = make_command("cp", "复制文件")

    assert search_commands([command], "复制 删除") == [command]


def test_search_ranks_more_keyword_matches_first():
    """命中关键词更多的文档应排在前面."""
    first = make_command("cp", "复制文件")
    second = make_command("robocopy", "复制文件和目录")

    results = search_commands(
        [first, second],
        "复制 文件 目录",
    )

    assert results == [second, first]


def test_search_uses_name_order_when_relevance_is_equal():
    """相关度相同时应按命令名称排序."""
    commands = [
        make_command("robocopy", "复制目录"),
        make_command("cp", "复制文件"),
    ]

    results = search_commands(commands, "复制")

    assert [command.name for command in results] == ["cp", "robocopy"]


def test_search_is_case_insensitive():
    """搜索应忽略英文大小写."""
    command = make_command("Git", "版本控制工具")

    assert search_commands([command], "GIT") == [command]


def test_search_deduplicates_keywords():
    """重复关键词不应重复计分."""
    command = make_command("cp", "复制文件")

    assert search_commands([command], "复制 复制") == [command]


def test_search_returns_empty_for_no_match():
    """没有匹配项时应返回空列表."""
    command = make_command("ls", "查看目录")

    assert search_commands([command], "网络") == []


def test_search_returns_empty_for_blank_query():
    """空白搜索内容应返回空列表."""
    command = make_command("ls", "查看目录")

    assert search_commands([command], "   ") == []


def test_full_search_does_not_change_result_type():
    """full 模式仍然只返回命令文档."""
    command = make_command("cp", "复制文件", "保留属性")

    results = search_commands([command], "保留", full=True)

    assert len(results) == 1
    assert results[0] is command
