"""LCMD CLI 应用."""

from dataclasses import replace
from typing import Any

import typer
from typer.core import TyperGroup

from lcmd import __version__
from lcmd.core.config import (
    SUPPORTED_LANGUAGES,
    SUPPORTED_PLATFORMS,
    AppConfig,
    ConfigError,
    load_config,
    save_config,
)
from lcmd.knowledge.loader import (
    KnowledgeLoadError,
    load_knowledge,
    load_knowledge_version,
)
from lcmd.knowledge.lookup import find_command
from lcmd.knowledge.search import search_commands
from lcmd.output.renderer import print_error, print_markdown, print_warning


class LCMDGroup(TyperGroup):
    """支持直接查询命令名称的 Typer 命令组."""

    def get_help_option(self, ctx: typer.Context) -> Any:
        """将默认帮助选项的英文提示改为中文."""
        option = super().get_help_option(ctx)

        if option is not None:
            option.help = "显示此帮助信息并退出。"

        return option

    def resolve_command(
        self,
        ctx: typer.Context,
        args: list[str],
    ) -> tuple[str | None, Any, list[str]]:
        """优先解析已注册子命令，未匹配时转入知识库查询."""
        if args:
            command_name = args[0]
            registered_command = self.get_command(ctx, command_name)

            if registered_command is None:
                lookup_command = self.get_command(
                    ctx,
                    "_lcmd_lookup_internal",
                )

                if lookup_command is not None:
                    ctx.meta["lcmd_lookup_name"] = command_name
                    return command_name, lookup_command, args[1:]

        return super().resolve_command(ctx, args)


app = typer.Typer(
    name="lcmd",
    help="简体中文命令行速查与学习工具。",
    cls=LCMDGroup,
    add_completion=False,
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="显示 LCMD 版本。",
        is_eager=True,
    ),
) -> None:
    """LCMD 命令行入口."""
    if version:
        typer.echo(f"LCMD 主程序版本：{__version__}")

        try:
            config = load_config()
            knowledge_version = load_knowledge_version(config)
            typer.echo(f"LCMD 知识库版本：{knowledge_version}")
        except (ConfigError, KnowledgeLoadError) as exc:
            typer.echo(f"LCMD 知识库版本：不可用（{exc}）")

        raise typer.Exit()

    try:
        config = load_config()
    except ConfigError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc

    # 平台和语言管理只依赖配置，不需要加载知识库。
    if ctx.invoked_subcommand in {"platform", "language"}:
        ctx.obj = config
        return

    try:
        knowledge = load_knowledge(config)
    except KnowledgeLoadError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc

    ctx.obj = knowledge

    for diagnostic in knowledge.diagnostics:
        print_warning(f"{diagnostic.path}：{diagnostic.message}")


@app.command()
def platform(
    ctx: typer.Context,
    name: str | None = typer.Argument(
        None,
        help="要切换到的平台：windows 或 linux。",
    ),
) -> None:
    """查看或切换知识平台."""
    config: AppConfig = ctx.obj

    if name is None:
        typer.echo(f"当前知识平台：{config.platform}")
        return

    if name not in SUPPORTED_PLATFORMS:
        allowed = "、".join(sorted(SUPPORTED_PLATFORMS))
        print_error(f"不支持的平台：{name}。允许的值：{allowed}。")
        raise typer.Exit(code=1)

    if name == config.platform:
        typer.echo(f"当前知识平台已经是：{name}")
        return

    updated_config = replace(config, platform=name)

    try:
        save_config(updated_config)
    except ConfigError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc

    typer.echo(f"知识平台已切换为：{name}")


@app.command()
def language(
    ctx: typer.Context,
    name: str | None = typer.Argument(
        None,
        help="要切换到的语言：zh-CN 或 en-US。",
    ),
) -> None:
    """查看或切换知识语言."""
    config: AppConfig = ctx.obj

    if name is None:
        typer.echo(f"当前知识语言：{config.language}")
        return

    if name not in SUPPORTED_LANGUAGES:
        allowed = "、".join(sorted(SUPPORTED_LANGUAGES))
        print_error(f"不支持的语言：{name}。允许的值：{allowed}。")
        raise typer.Exit(code=1)

    if name == config.language:
        typer.echo(f"当前知识语言已经是：{name}")
        return

    updated_config = replace(config, language=name)

    try:
        save_config(updated_config)
    except ConfigError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc

    typer.echo(f"知识语言已切换为：{name}")


@app.command()
def search(
    ctx: typer.Context,
    query: str = typer.Argument(
        ...,
        help="要搜索的功能或关键词。",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="扩大搜索范围，额外搜索 Markdown 正文。",
    ),
) -> None:
    """通过功能关键词搜索命令."""
    results = search_commands(
        ctx.obj.commands,
        query,
        full=full,
    )

    if not results:
        print_warning(
            "未找到匹配的命令。请尝试使用更简短、准确的关键词重新搜索，"
            "也可以使用 `--full` 扩大搜索范围。"
        )
        return

    lines = [
        f"# 搜索结果：{query}",
        "",
        f"找到 {len(results)} 条相关命令",
        "",
    ]

    for command in results:
        lines.extend(
            [
                f"- **`{command.name}`**",
                f"  {command.metadata['summary']}",
            ]
        )

    print_markdown("\n".join(lines))


@app.command(
    name="_lcmd_lookup_internal",
    hidden=True,
)
def _lookup_command(ctx: typer.Context) -> None:
    """执行 LCMD 内部命令查询."""
    parent_ctx = ctx.parent

    if parent_ctx is None:
        print_error("无法获取命令查询上下文。")
        raise typer.Exit(code=1)

    command_name = parent_ctx.meta.get("lcmd_lookup_name")

    if not isinstance(command_name, str):
        print_error("无法获取待查询的命令名称。")
        raise typer.Exit(code=1)

    try:
        command = find_command(ctx.obj.commands, command_name)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc

    if command is None:
        print_warning(f"知识库尚未收录该命令：{command_name}")
        return

    summary = command.metadata["summary"]
    content = f"# {command.name}\n\n{summary}\n\n{command.body}"

    print_markdown(content)
