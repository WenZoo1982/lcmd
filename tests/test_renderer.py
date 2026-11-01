"""LCMD Markdown 终端渲染测试."""

from io import StringIO

import pytest
from rich.console import Console

import lcmd.output.renderer as renderer


@pytest.fixture
def console_output(monkeypatch):
    """创建用于捕获终端输出的 Rich Console."""
    output = StringIO()
    console = Console(
        file=output,
        width=100,
        force_terminal=False,
        color_system=None,
    )
    monkeypatch.setattr(renderer, "console", console)
    return output


def test_print_markdown_renders_heading(console_output):
    """应正确渲染 Markdown 标题."""
    renderer.print_markdown("# 文件管理命令")

    assert "文件管理命令" in console_output.getvalue()


def test_print_markdown_renders_bullet_list(console_output):
    """应正确渲染无序列表."""
    renderer.print_markdown("- 显示文件\n- 显示隐藏文件\n- 显示详细信息\n")

    output = console_output.getvalue()

    assert "显示文件" in output
    assert "显示隐藏文件" in output
    assert "显示详细信息" in output


def test_print_markdown_renders_inline_code(console_output):
    """应正确渲染行内代码."""
    renderer.print_markdown("使用 `ls -lah` 查看目录内容。")

    assert "ls -lah" in console_output.getvalue()


def test_print_markdown_preserves_code_block(console_output):
    """应正确渲染多行代码块."""
    renderer.print_markdown("```bash\nls -lah\npwd\n```\n")

    output = console_output.getvalue()

    assert "ls -lah" in output
    assert "pwd" in output
