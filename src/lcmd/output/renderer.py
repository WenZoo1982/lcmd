"""LCMD 统一终端输出."""

from rich.console import Console

console = Console()


def print_error(message: str) -> None:
    """显示统一格式的错误信息。"""
    console.print(f"[red]错误：{message}[/red]")


def print_info(message: str) -> None:
    """显示普通提示信息。"""
    console.print(message)
