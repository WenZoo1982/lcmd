"""LCMD 命令精确查询测试."""

from pathlib import Path

from lcmd.knowledge.loader import LoadedDocument
from lcmd.knowledge.lookup import find_command


def make_command(name: str) -> LoadedDocument:
    """创建用于测试的命令文档."""
    return LoadedDocument(
        name=name,
        path=Path(f"commands/linux/zh-CN/{name}.md"),
        metadata={"summary": f"{name} 命令说明"},
        body=f"# {name}\n\n命令正文。",
    )


def test_find_command_returns_exact_match():
    """应返回名称完全匹配的命令."""
    command = make_command("ls")

    result = find_command([command], "ls")

    assert result is command


def test_find_command_is_case_insensitive():
    """命令名称应忽略大小写."""
    command = make_command("ls")

    result = find_command([command], "LS")

    assert result is command


def test_find_command_does_not_match_prefix():
    """不应将前缀匹配视为命令匹配."""
    command = make_command("ls")

    result = find_command([command], "l")

    assert result is None


def test_find_command_does_not_match_substring():
    """不应将子字符串匹配视为命令匹配."""
    command = make_command("ls")

    result = find_command([command], "sl")

    assert result is None


def test_find_command_returns_none_when_not_found():
    """知识库没有对应命令时应返回 None."""
    result = find_command([make_command("ls")], "grep")

    assert result is None


def test_find_command_returns_none_for_empty_name():
    """空命令名称应返回 None."""
    result = find_command([make_command("ls")], "")

    assert result is None


def test_find_command_rejects_case_insensitive_duplicate_names():
    """存在大小写不敏感的重复命令名称时应明确报错."""
    commands = [
        make_command("ls"),
        make_command("LS"),
    ]

    import pytest

    with pytest.raises(ValueError, match="重复的命令名称"):
        find_command(commands, "ls")
