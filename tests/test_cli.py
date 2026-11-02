"""LCMD CLI 基础测试."""

from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

import lcmd.cli.app as cli_app
from lcmd import __version__
from lcmd.core.config import AppConfig, ConfigError
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


def test_cli_search_displays_command_names_and_summaries(monkeypatch):
    """搜索结果只显示命令名称和用途，不显示完整正文."""
    commands = [
        SimpleNamespace(
            name="cp",
            metadata={"summary": "复制文件和目录。"},
            body="详细语法和示例内容。",
        ),
        SimpleNamespace(
            name="robocopy",
            metadata={"summary": "复制目录及其内容。"},
            body="其他详细说明。",
        ),
    ]
    knowledge = SimpleNamespace(
        commands=commands,
        diagnostics=[],
    )
    outputs = []

    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(cli_app, "load_knowledge", lambda config: knowledge)
    monkeypatch.setattr(cli_app, "print_markdown", outputs.append)

    result = runner.invoke(cli_app.app, ["search", "复制"])

    assert result.exit_code == 0
    assert len(outputs) == 1
    assert "找到 2 条相关命令" in outputs[0]
    assert "`cp`" in outputs[0]
    assert "复制文件和目录。" in outputs[0]
    assert "`robocopy`" in outputs[0]
    assert "复制目录及其内容。" in outputs[0]
    assert "详细语法和示例内容" not in outputs[0]
    assert "其他详细说明" not in outputs[0]


def test_cli_search_passes_full_option(monkeypatch):
    """CLI 应将 --full 选项传递给搜索模块."""
    knowledge = SimpleNamespace(
        commands=[],
        diagnostics=[],
    )
    calls = []

    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(cli_app, "load_knowledge", lambda config: knowledge)
    monkeypatch.setattr(
        cli_app,
        "search_commands",
        lambda commands, query, full=False: calls.append((commands, query, full)) or [],
    )
    monkeypatch.setattr(cli_app, "print_warning", lambda message: None)

    result = runner.invoke(
        cli_app.app,
        ["search", "复制文件", "--full"],
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0] == (knowledge.commands, "复制文件", True)


def test_cli_search_displays_no_result_message(monkeypatch):
    """搜索无结果时应显示明确的重试提示."""
    knowledge = SimpleNamespace(
        commands=[],
        diagnostics=[],
    )
    warnings = []

    monkeypatch.setattr(cli_app, "load_config", lambda: object())
    monkeypatch.setattr(cli_app, "load_knowledge", lambda config: knowledge)
    monkeypatch.setattr(cli_app, "search_commands", lambda *args, **kwargs: [])
    monkeypatch.setattr(cli_app, "print_warning", warnings.append)

    result = runner.invoke(
        cli_app.app,
        ["search", "不存在的功能"],
    )

    assert result.exit_code == 0
    assert len(warnings) == 1
    assert "未找到匹配的命令" in warnings[0]
    assert "--full" in warnings[0]


def test_cli_help_lists_search_command():
    """主帮助信息应列出 search 子命令."""
    result = runner.invoke(cli_app.app, ["--help"])

    assert result.exit_code == 0
    assert "search" in result.stdout


def test_platform_displays_current_platform(monkeypatch):
    """platform 不带参数时应显示当前知识平台."""
    config = AppConfig(platform="windows", language="zh-CN")
    monkeypatch.setattr(cli_app, "load_config", lambda: config)

    result = runner.invoke(cli_app.app, ["platform"])

    assert result.exit_code == 0
    assert "当前知识平台：windows" in result.stdout


def test_platform_switches_platform(monkeypatch):
    """platform 应切换平台并保存配置."""
    config = AppConfig(platform="windows", language="zh-CN")
    saved_configs = []

    monkeypatch.setattr(cli_app, "load_config", lambda: config)
    monkeypatch.setattr(
        cli_app,
        "save_config",
        lambda value: saved_configs.append(value),
    )

    result = runner.invoke(cli_app.app, ["platform", "linux"])

    assert result.exit_code == 0
    assert "知识平台已切换为：linux" in result.stdout
    assert saved_configs == [AppConfig(platform="linux", language="zh-CN")]


def test_platform_same_value_does_not_save(monkeypatch):
    """重复设置当前平台时不应重复保存."""
    config = AppConfig(platform="linux", language="zh-CN")
    saved_configs = []

    monkeypatch.setattr(cli_app, "load_config", lambda: config)
    monkeypatch.setattr(
        cli_app,
        "save_config",
        lambda value: saved_configs.append(value),
    )

    result = runner.invoke(cli_app.app, ["platform", "linux"])

    assert result.exit_code == 0
    assert "当前知识平台已经是：linux" in result.stdout
    assert saved_configs == []


@pytest.mark.parametrize("platform", ["macos", "other", "Windows"])
def test_platform_rejects_unsupported_value(monkeypatch, platform):
    """platform 应拒绝不支持的平台值."""
    config = AppConfig(platform="windows", language="zh-CN")
    saved_configs = []
    errors = []

    monkeypatch.setattr(cli_app, "load_config", lambda: config)
    monkeypatch.setattr(
        cli_app,
        "save_config",
        lambda value: saved_configs.append(value),
    )
    monkeypatch.setattr(cli_app, "print_error", errors.append)

    result = runner.invoke(cli_app.app, ["platform", platform])

    assert result.exit_code == 1
    assert errors
    assert saved_configs == []


def test_language_displays_current_language(monkeypatch):
    """language 不带参数时应显示当前知识语言."""
    config = AppConfig(platform="windows", language="zh-CN")
    monkeypatch.setattr(cli_app, "load_config", lambda: config)

    result = runner.invoke(cli_app.app, ["language"])

    assert result.exit_code == 0
    assert "当前知识语言：zh-CN" in result.stdout


def test_language_switches_language(monkeypatch):
    """language 应切换语言并保存配置."""
    config = AppConfig(platform="windows", language="zh-CN")
    saved_configs = []

    monkeypatch.setattr(cli_app, "load_config", lambda: config)
    monkeypatch.setattr(
        cli_app,
        "save_config",
        lambda value: saved_configs.append(value),
    )

    result = runner.invoke(cli_app.app, ["language", "en-US"])

    assert result.exit_code == 0
    assert "知识语言已切换为：en-US" in result.stdout
    assert saved_configs == [AppConfig(platform="windows", language="en-US")]


def test_language_same_value_does_not_save(monkeypatch):
    """重复设置当前语言时不应重复保存."""
    config = AppConfig(platform="windows", language="en-US")
    saved_configs = []

    monkeypatch.setattr(cli_app, "load_config", lambda: config)
    monkeypatch.setattr(
        cli_app,
        "save_config",
        lambda value: saved_configs.append(value),
    )

    result = runner.invoke(cli_app.app, ["language", "en-US"])

    assert result.exit_code == 0
    assert "当前知识语言已经是：en-US" in result.stdout
    assert saved_configs == []


@pytest.mark.parametrize("language", ["en", "zh", "fr-FR"])
def test_language_rejects_unsupported_value(monkeypatch, language):
    """language 应拒绝不支持的语言值."""
    config = AppConfig(platform="windows", language="zh-CN")
    saved_configs = []
    errors = []

    monkeypatch.setattr(cli_app, "load_config", lambda: config)
    monkeypatch.setattr(
        cli_app,
        "save_config",
        lambda value: saved_configs.append(value),
    )
    monkeypatch.setattr(cli_app, "print_error", errors.append)

    result = runner.invoke(cli_app.app, ["language", language])

    assert result.exit_code == 1
    assert errors
    assert saved_configs == []


@pytest.mark.parametrize("command", ["platform", "language"])
def test_management_commands_work_without_loading_knowledge(
    monkeypatch,
    tmp_path,
    command,
):
    """知识库路径失效时，平台和语言管理命令仍应可用."""
    config = AppConfig(
        platform="windows",
        language="zh-CN",
        path=tmp_path / "missing-knowledge",
    )

    monkeypatch.setattr(cli_app, "load_config", lambda: config)

    def unexpected_load(config):
        pytest.fail("管理命令不应加载知识库")

    monkeypatch.setattr(cli_app, "load_knowledge", unexpected_load)

    result = runner.invoke(cli_app.app, [command])

    assert result.exit_code == 0
