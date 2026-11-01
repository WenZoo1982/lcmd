"""LCMD 统一终端输出."""

from rich.console import Console
from rich.markdown import Markdown

console = Console()


def print_error(message: str) -> None:
    """显示统一格式的错误信息."""
    console.print(f"[red]错误：{message}[/red]")


def print_warning(message: str) -> None:
    """显示统一格式的警告信息."""
    console.print(f"[yellow]警告：{message}[/yellow]")


def print_info(message: str) -> None:
    """显示普通提示信息."""
    console.print(message)


def print_markdown(content: str) -> None:
    """将 Markdown 内容渲染到终端."""
    console.print(Markdown(content))
