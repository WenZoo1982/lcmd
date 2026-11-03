from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from typer.core import TyperGroup

from lcmd import __version__
from lcmd.core.config import AppConfig, ConfigError, load_config, save_config
from lcmd.core.paths import get_config_file, get_default_knowledge_path
from lcmd.knowledge.loader import (
    KnowledgeLoadError,
    discover_catalog,
    load_knowledge,
)
from lcmd.knowledge.models import KnowledgeBase, KnowledgeCatalog
from lcmd.knowledge.query import query_document
from lcmd.knowledge.search import search_knowledge
from lcmd.output.renderer import render_query_result, render_search_results


@dataclass(frozen=True, slots=True)
class AppState:
    config: AppConfig
    catalog: KnowledgeCatalog | None
    knowledge: KnowledgeBase | None


class DynamicTyperGroup(TyperGroup):
    """将未注册的命令名及其参数交给动态知识库查询。"""

    def resolve_command(
        self,
        ctx: typer.Context,
        args: list[str],
    ) -> tuple[str | None, Any, list[str]]:
        if not args:
            return super().resolve_command(ctx, args)

        command_name = args[0]

        if command_name in self.commands or command_name.startswith("-"):
            return super().resolve_command(ctx, args)

        ctx.meta["lcmd_dynamic_arguments"] = list(args)

        placeholder_command = TyperGroup(
            name=command_name,
            commands={},
        )

        return command_name, placeholder_command, args[1:]


def initialize_state(
    config_file: Path | None = None,
    default_knowledge_path: Path | None = None,
) -> AppState:
    """读取配置并尝试初始化知识库。"""
    config_file = config_file or get_config_file()

    if config_file.is_file():
        config = load_config(config_file)
    else:
        config = AppConfig(knowledge_path=default_knowledge_path or get_default_knowledge_path())

    knowledge_path = config.knowledge_path
    if knowledge_path is None:
        knowledge_path = default_knowledge_path or get_default_knowledge_path()
        config = replace(config, knowledge_path=knowledge_path)

    try:
        catalog = discover_catalog(knowledge_path)
        knowledge = load_knowledge(catalog, config.platform, config.language)
    except (KnowledgeLoadError, OSError):
        return AppState(
            config=config,
            catalog=None,
            knowledge=None,
        )

    if not config_file.is_file():
        save_config(config, config_file)

    return AppState(
        config=config,
        catalog=catalog,
        knowledge=knowledge,
    )


def switch_platform(state: AppState, platform: str, config_file: Path) -> AppState:
    """验证并切换平台，成功加载后才保存配置。"""
    if state.catalog is None:
        raise KnowledgeLoadError("知识库不可用。")

    new_config = replace(state.config, platform=platform.lower())
    knowledge = load_knowledge(state.catalog, new_config.platform, new_config.language)

    save_config(new_config, config_file)

    return AppState(
        config=new_config,
        catalog=state.catalog,
        knowledge=knowledge,
    )


def switch_language(state: AppState, language: str, config_file: Path) -> AppState:
    """验证并切换语言，成功加载后才保存配置。"""
    if state.catalog is None:
        raise KnowledgeLoadError("知识库不可用。")

    new_config = replace(state.config, language=language)
    knowledge = load_knowledge(state.catalog, new_config.platform, new_config.language)

    save_config(new_config, config_file)

    return AppState(
        config=new_config,
        catalog=state.catalog,
        knowledge=knowledge,
    )


def _show_platforms(state: AppState, console: Console) -> None:
    console.print(f"当前平台：{state.config.platform}")

    if state.catalog is None:
        console.print("可用平台：无法获取（知识库不可用）", style="yellow")
        return

    console.print("可用平台：" + "、".join(item.name for item in state.catalog.platforms))


def _show_languages(state: AppState, console: Console) -> None:
    console.print(f"当前语言：{state.config.language}")

    if state.catalog is None:
        console.print("可用语言：无法获取（知识库不可用）", style="yellow")
        return

    selected = next(
        (item for item in state.catalog.platforms if item.name == state.config.platform),
        None,
    )

    if selected is None:
        console.print("可用语言：无法获取（当前平台不存在）", style="yellow")
        return

    console.print("可用语言：" + "、".join(selected.languages))


def _show_version(console: Console) -> None:
    """显示版本信息，不加载知识文档，也不写入配置。"""
    console.print(f"LCMD：{__version__}")

    try:
        config_file = get_config_file()

        if config_file.is_file():
            config = load_config(config_file)
        else:
            config = AppConfig(knowledge_path=get_default_knowledge_path())

        knowledge_path = config.knowledge_path or get_default_knowledge_path()
        catalog = discover_catalog(knowledge_path)
    except (ConfigError, KnowledgeLoadError, OSError):
        console.print("知识库：不可用", style="yellow")
    else:
        console.print(f"知识库：{catalog.version}")


def create_app() -> typer.Typer:
    """创建 LCMD 命令行应用。"""
    app = typer.Typer(
        cls=DynamicTyperGroup,
        invoke_without_command=True,
        no_args_is_help=True,
        add_completion=False,
        help="多平台命令速查与学习工具。",
    )

    @app.callback()
    def callback(
        ctx: typer.Context,
        version: bool = typer.Option(
            False,
            "--version",
            "-v",
            help="显示程序和知识库版本。",
        ),
    ) -> None:
        console = Console()

        if version:
            _show_version(console)
            raise typer.Exit()

        try:
            state = initialize_state()
        except (ConfigError, KnowledgeLoadError, OSError):
            console.print("LCMD 初始化失败，请检查配置。", style="red")
            raise typer.Exit(code=1) from None

        ctx.obj = state

        dynamic_arguments = ctx.meta.get("lcmd_dynamic_arguments")
        if dynamic_arguments is not None:
            if state.knowledge is None:
                console.print("知识库不可用，无法查询命令。", style="red")
                raise typer.Exit(code=1)

            result = query_document(state.knowledge, dynamic_arguments)
            render_query_result(result, console)
            raise typer.Exit()

        if ctx.invoked_subcommand is None and not ctx.args:
            console.print(ctx.get_help())
            raise typer.Exit()

    @app.command("search")
    def search_command(
        ctx: typer.Context,
        keyword: list[str] = typer.Argument(..., help="一个或多个搜索关键词。"),  # noqa: B008  # noqa: B008
        full: bool = typer.Option(
            False,
            "--full",
            help="搜索文档全文。",
        ),
    ) -> None:
        state: AppState = ctx.find_root().obj

        if state.knowledge is None:
            console = Console()
            console.print("知识库不可用，无法搜索。", style="red")
            raise typer.Exit(code=1)

        results = search_knowledge(
            state.knowledge,
            " ".join(keyword),
            full=full,
        )
        render_search_results(results)

    @app.command("platform")
    def platform_command(
        ctx: typer.Context,
        platform: str | None = typer.Argument(None),
    ) -> None:
        state: AppState = ctx.find_root().obj
        console = Console()
        config_file = get_config_file()

        if platform is None:
            _show_platforms(state, console)
            return

        try:
            new_state = switch_platform(state, platform, config_file)
        except (KnowledgeLoadError, ConfigError):
            console.print("平台切换失败，当前配置保持不变。", style="red")
            raise typer.Exit(code=1) from None

        console.print(f"已切换平台：{new_state.config.platform}")

    @app.command("language")
    def language_command(
        ctx: typer.Context,
        language: str | None = typer.Argument(None),
    ) -> None:
        state: AppState = ctx.find_root().obj
        console = Console()
        config_file = get_config_file()

        if language is None:
            _show_languages(state, console)
            return

        try:
            new_state = switch_language(state, language, config_file)
        except (KnowledgeLoadError, ConfigError):
            console.print("语言切换失败，当前配置保持不变。", style="red")
            raise typer.Exit(code=1) from None

        console.print(f"已切换语言：{new_state.config.language}")

    return app
