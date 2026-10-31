"""LCMD CLI 应用."""

import typer

from lcmd import __version__

app = typer.Typer(
    name="lcmd",
    help="简体中文命令行速查与学习工具。",
    add_completion=False,
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="显示 LCMD 版本。",
        is_eager=True,
    ),
) -> None:
    """LCMD 命令行入口。"""
    if version:
        typer.echo(f"LCMD {__version__}")
        raise typer.Exit()
