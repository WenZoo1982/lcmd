"""LCMD CLI 基础测试."""

from typer.testing import CliRunner

from lcmd import __version__
from lcmd.cli.app import app

runner = CliRunner()


def test_help() -> None:
    """帮助参数应正常显示。"""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "LCMD" in result.stdout
    assert "--version" in result.stdout


def test_version() -> None:
    """版本参数应显示当前程序版本。"""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert f"LCMD {__version__}" in result.stdout


def test_short_version() -> None:
    """短版本参数应正常工作。"""
    result = runner.invoke(app, ["-v"])

    assert result.exit_code == 0
    assert f"LCMD {__version__}" in result.stdout
