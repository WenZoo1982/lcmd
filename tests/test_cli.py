"""LCMD CLI 基础测试."""

from types import SimpleNamespace

import typer
from typer.testing import CliRunner

import lcmd.cli.app as cli_app
from lcmd import __version__
from lcmd.core.config import ConfigError
from lcmd.knowledge.loader import KnowledgeLoadError

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
    def probe(ctx: typer.Context) -> None:
        """用于触发 CLI 初始化的测试命令."""
        ctx.ensure_object(dict)

    return test_app


def test_help() -> None:
    """帮助参数应正常显示中文提示，且不初始化知识库."""
    result = runner.invoke(cli_app.app, ["--help"])

    assert result.exit_code == 0
    assert "LCMD" in result.stdout
    assert "--version" in result.stdout
    assert "显示此帮助信息并退出。" in result.stdout
    assert "Show this message and exit." not in result.stdout


def test_version(monkeypatch) -> None:
    """长版本参数应显示主程序和知识库版本."""
    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(
        cli_app,
        "load_knowledge_version",
        lambda config: "0.1.0",
    )

    result = runner.invoke(cli_app.app, ["--version"])

    assert result.exit_code == 0
    assert f"LCMD 主程序版本：{__version__}" in result.stdout
    assert "LCMD 知识库版本：0.1.0" in result.stdout


def test_short_version(monkeypatch) -> None:
    """短版本参数应显示主程序和知识库版本."""
    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(
        cli_app,
        "load_knowledge_version",
        lambda config: "0.1.0",
    )

    result = runner.invoke(cli_app.app, ["-v"])

    assert result.exit_code == 0
    assert f"LCMD 主程序版本：{__version__}" in result.stdout
    assert "LCMD 知识库版本：0.1.0" in result.stdout


def test_version_when_knowledge_is_unavailable(monkeypatch) -> None:
    """知识库不可用时仍应显示主程序版本和具体原因."""
    monkeypatch.setattr(cli_app, "load_config", lambda: object())

    def raise_load_error(config):
        raise KnowledgeLoadError("知识库目录不存在")

    monkeypatch.setattr(
        cli_app,
        "load_knowledge_version",
        raise_load_error,
    )

    result = runner.invoke(cli_app.app, ["--version"])

    assert result.exit_code == 0
    assert f"LCMD 主程序版本：{__version__}" in result.stdout
    assert "LCMD 知识库版本：不可用" in result.stdout
    assert "知识库目录不存在" in result.stdout


def test_initialization_loads_knowledge_into_context(monkeypatch) -> None:
    """CLI 应加载知识库并将结果保存到 Typer Context."""
    config = object()
    knowledge = SimpleNamespace(
        commands=[],
        tasks=[],
        diagnostics=[],
    )
    calls = []
    context_objects = []

    monkeypatch.setattr(
        cli_app,
        "load_config",
        lambda: calls.append("load_config") or config,
    )
    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        lambda value: calls.append(("load_knowledge", value)) or knowledge,
        raising=False,
    )

    test_app = typer.Typer(
        add_completion=False,
        no_args_is_help=True,
        invoke_without_command=True,
    )
    test_app.callback()(cli_app.main)

    @test_app.command()
    def probe(ctx: typer.Context) -> None:
        context_objects.append(ctx.obj)

    result = runner.invoke(test_app, ["probe"])

    assert result.exit_code == 0
    assert calls == [
        "load_config",
        ("load_knowledge", config),
    ]
    assert context_objects == [knowledge]


def test_initialization_displays_document_diagnostics(monkeypatch) -> None:
    """单篇文档加载诊断应显示警告，但不终止 CLI."""
    config = object()
    diagnostic = SimpleNamespace(
        path="commands/linux/zh-CN/ls.md",
        message="文档内容无效",
    )
    knowledge = SimpleNamespace(
        commands=[],
        tasks=[],
        diagnostics=[diagnostic],
    )
    warnings = []

    monkeypatch.setattr(cli_app, "load_config", lambda: config)
    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        lambda value: knowledge,
        raising=False,
    )
    monkeypatch.setattr(
        cli_app,
        "print_warning",
        warnings.append,
        raising=False,
    )

    result = runner.invoke(create_test_app(), ["probe"])

    assert result.exit_code == 0
    assert len(warnings) == 1
    assert "commands/linux/zh-CN/ls.md" in warnings[0]
    assert "文档内容无效" in warnings[0]


def test_knowledge_load_error_exits(monkeypatch) -> None:
    """知识库整体加载异常时应显示错误并以退出码 1 退出."""
    errors = []

    monkeypatch.setattr(cli_app, "load_config", lambda: object())

    def raise_load_error(config):
        raise KnowledgeLoadError("知识库版本不兼容")

    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        raise_load_error,
        raising=False,
    )
    monkeypatch.setattr(cli_app, "print_error", errors.append)

    result = runner.invoke(create_test_app(), ["probe"])

    assert result.exit_code == 1
    assert errors == ["知识库版本不兼容"]


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


def test_cli_displays_matching_command(monkeypatch):
    """输入命令名称时应显示对应的中文速查资料."""
    command = SimpleNamespace(
        name="ls",
        metadata={"summary": "查看目录中的文件和文件夹。"},
        body="## 常用示例\n\n```bash\nls -lah\n```",
    )
    knowledge = SimpleNamespace(
        commands=[command],
        tasks=[],
        diagnostics=[],
    )
    markdown_outputs = []

    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        lambda config: knowledge,
    )
    monkeypatch.setattr(
        cli_app,
        "print_markdown",
        markdown_outputs.append,
        raising=False,
    )

    result = runner.invoke(cli_app.app, ["ls"])

    assert result.exit_code == 0
    assert len(markdown_outputs) == 1
    assert "# ls" in markdown_outputs[0]
    assert "查看目录中的文件和文件夹。" in markdown_outputs[0]
    assert "常用示例" in markdown_outputs[0]


def test_cli_command_lookup_is_case_insensitive(monkeypatch):
    """CLI 命令查询应忽略大小写."""
    command = SimpleNamespace(
        name="ls",
        metadata={"summary": "查看目录内容。"},
        body="命令正文。",
    )
    knowledge = SimpleNamespace(
        commands=[command],
        tasks=[],
        diagnostics=[],
    )
    markdown_outputs = []

    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        lambda config: knowledge,
    )
    monkeypatch.setattr(
        cli_app,
        "print_markdown",
        markdown_outputs.append,
        raising=False,
    )

    result = runner.invoke(cli_app.app, ["LS"])

    assert result.exit_code == 0
    assert len(markdown_outputs) == 1
    assert "# ls" in markdown_outputs[0]


def test_cli_warns_when_command_is_not_in_knowledge(monkeypatch):
    """知识库没有对应命令时应明确提示."""
    knowledge = SimpleNamespace(
        commands=[],
        tasks=[],
        diagnostics=[],
    )
    warnings = []

    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        lambda config: knowledge,
    )
    monkeypatch.setattr(
        cli_app,
        "print_warning",
        warnings.append,
    )

    result = runner.invoke(cli_app.app, ["unknown-command"])

    assert result.exit_code == 0
    assert len(warnings) == 1
    assert "知识库尚未收录该命令" in warnings[0]
    assert "unknown-command" in warnings[0]
