"""LCMD CLI 基础测试."""

from types import SimpleNamespace

import typer
from typer.testing import CliRunner

import lcmd.cli.app as cli_app
from lcmd import __version__
from lcmd.core.config import ConfigError
from lcmd.core.paths import PathError

runner = CliRunner()


def create_test_app() -> typer.Typer:
    """创建带有测试命令的临时 CLI 应用."""
    test_app = typer.Typer(
        add_completion=False,
        no_args_is_help=True,
        invoke_without_command=True,
    )

    test_app.callback()(cli_app.main)

    @test_app.command()
    def probe() -> None:
        """用于触发 CLI 初始化的测试命令."""

    return test_app


def test_help() -> None:
    """帮助参数应正常显示."""
    result = runner.invoke(cli_app.app, ["--help"])

    assert result.exit_code == 0
    assert "LCMD" in result.stdout
    assert "--version" in result.stdout


def test_version() -> None:
    """版本参数应显示当前程序版本."""
    result = runner.invoke(cli_app.app, ["--version"])

    assert result.exit_code == 0
    assert f"LCMD {__version__}" in result.stdout


def test_short_version() -> None:
    """短版本参数应正常工作."""
    result = runner.invoke(cli_app.app, ["-v"])

    assert result.exit_code == 0
    assert f"LCMD {__version__}" in result.stdout


def test_initialization_success(monkeypatch, tmp_path) -> None:
    """配置读取和知识库路径验证成功时应正常执行命令."""
    config = object()
    knowledge_dirs = SimpleNamespace(root=tmp_path)
    calls = []

    monkeypatch.setattr(
        cli_app,
        "load_config",
        lambda: calls.append("load_config") or config,
    )
    monkeypatch.setattr(
        cli_app,
        "get_knowledge_dirs",
        lambda value: calls.append(("get_knowledge_dirs", value)) or knowledge_dirs,
    )
    monkeypatch.setattr(
        cli_app,
        "validate_knowledge_root",
        lambda path: calls.append(("validate_knowledge_root", path)) or path,
    )

    result = runner.invoke(create_test_app(), ["probe"])

    assert result.exit_code == 0
    assert calls == [
        "load_config",
        ("get_knowledge_dirs", config),
        ("validate_knowledge_root", tmp_path),
    ]


def test_config_error_exits(monkeypatch) -> None:
    """配置异常时应显示错误并以退出码 1 退出."""
    errors = []

    def raise_config_error():
        raise ConfigError("配置文件损坏")

    monkeypatch.setattr(cli_app, "load_config", raise_config_error)
    monkeypatch.setattr(cli_app, "print_error", errors.append)

    result = runner.invoke(create_test_app(), ["probe"])

    assert result.exit_code == 1
    assert errors == ["配置文件损坏"]


def test_path_error_exits(monkeypatch, tmp_path) -> None:
    """知识库根目录验证失败时应显示错误并以退出码 1 退出."""
    errors = []
    knowledge_dirs = SimpleNamespace(root=tmp_path)

    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(
        cli_app,
        "get_knowledge_dirs",
        lambda config: knowledge_dirs,
    )

    def raise_path_error(path):
        raise PathError(f"知识库目录不存在：{path}")

    monkeypatch.setattr(
        cli_app,
        "validate_knowledge_root",
        raise_path_error,
    )
    monkeypatch.setattr(cli_app, "print_error", errors.append)

    result = runner.invoke(create_test_app(), ["probe"])

    assert result.exit_code == 1
    assert errors == [f"知识库目录不存在：{tmp_path}"]
