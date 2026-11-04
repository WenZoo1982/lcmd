import warnings
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from typer.core import TyperGroup

from lcmd import __version__
from lcmd.cli.installer import (
    check_installer_destination,
    deploy_installer_knowledge,
)
from lcmd.core.config import AppConfig, ConfigError, load_config, save_config
from lcmd.core.installer import (
    InstallerError,
    KnowledgeDestinationState,
)
from lcmd.core.migration import (
    MigrationCleanupWarning,
    MigrationConfirmationRequired,
    MigrationError,
    migrate_knowledge,
    recover_migration,
)
from lcmd.core.path_security import PathSecurityError, validate_knowledge_path
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

    _OPTIONAL_VALUE_OPTIONS = {
        "--platform": "--platform=",
        "-p": "--platform=",
        "--language": "--language=",
        "-l": "--language=",
    }

    _ROOT_VALUE_OPTIONS = {
        "--path",
         "--installer-source",    
        "--installer-integrity",
    }

    _ROOT_FLAG_OPTIONS = {
        "--installer-init",
        "--config",
        "-c",
        "--update",
        "-u",
        "--version",
        "-v",
        "--help",
        "-h",
    }

    def parse_args(self, ctx: typer.Context, args: list[str]) -> list[str]:
        """允许平台、语言选项省略值；不处理子命令和动态查询参数。"""
        normalized: list[str] = []
        index = 0

        while index < len(args):
            token = args[index]

            if token in self._OPTIONAL_VALUE_OPTIONS:
                if index + 1 >= len(args) or args[index + 1].startswith("-"):
                    normalized.append(self._OPTIONAL_VALUE_OPTIONS[token])
                    index += 1
                    continue

                normalized.append(token)
                normalized.append(args[index + 1])
                index += 2
                continue

            if token.startswith("--platform=") or token.startswith("--language="):
                normalized.append(token)
                index += 1
                continue

            if token.startswith("-p") and token != "-p":
                normalized.append(f"--platform={token[2:]}")
                index += 1
                continue

            if token.startswith("-l") and token != "-l":
                normalized.append(f"--language={token[2:]}")
                index += 1
                continue

            if token in self._ROOT_VALUE_OPTIONS:
                normalized.append(token)
                if index + 1 < len(args):
                    normalized.append(args[index + 1])
                    index += 2
                else:
                    index += 1
                continue

            if token in self._ROOT_FLAG_OPTIONS:
                normalized.append(token)
                index += 1
                continue

            if token.startswith("-"):
                normalized.append(token)
                index += 1
                continue

            # 第一个非选项参数是固定子命令或动态查询的起点。
            normalized.extend(args[index:])
            break

        return super().parse_args(ctx, normalized)

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
    """恢复未完成的知识库迁移，然后初始化应用状态。"""
    config_file = config_file or get_config_file()

    # 必须先恢复迁移，再读取配置和加载知识库。
    recover_migration(config_file)

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
        return AppState(config=config, catalog=None, knowledge=None)

    if not config_file.is_file():
        save_config(config, config_file)

    return AppState(config=config, catalog=catalog, knowledge=knowledge)


def switch_platform(state: AppState, platform: str, config_file: Path) -> AppState:
    """验证并切换平台，成功加载后才保存配置。"""
    return switch_configuration(
        state,
        config_file,
        platform=platform,
    )


def switch_language(state: AppState, language: str, config_file: Path) -> AppState:
    """验证并切换语言，成功加载后才保存配置。"""
    return switch_configuration(
        state,
        config_file,
        language=language,
    )


def switch_configuration(
    state: AppState,
    config_file: Path,
    *,
    platform: str | None = None,
    language: str | None = None,
) -> AppState:
    """验证最终平台和语言组合，并且只保存一次配置。"""
    if state.catalog is None:
        raise KnowledgeLoadError("知识库不可用。")

    new_config = replace(
        state.config,
        platform=(platform.lower() if platform is not None else state.config.platform),
        language=(language if language is not None else state.config.language),
    )

    knowledge = load_knowledge(
        state.catalog,
        new_config.platform,
        new_config.language,
    )

    save_config(new_config, config_file)

    return AppState(
        config=new_config,
        catalog=state.catalog,
        knowledge=knowledge,
    )


def initialize_installer_config(knowledge_path: str) -> AppConfig:
    """验证安装器部署的知识库，并初始化配置文件。

    只更新知识库路径，保留已有平台和语言设置。
    不复制、迁移或修改知识库文件。
    """
    validated_path = validate_knowledge_path(knowledge_path)
    config_file = get_config_file()

    if config_file.is_file():
        config = load_config(config_file)
        new_config = replace(
            config,
            knowledge_path=validated_path,
        )
    else:
        new_config = AppConfig(
            knowledge_path=validated_path,
        )

    save_config(new_config, config_file)
    return new_config


def _show_configuration(state: AppState, console: Console) -> None:
    console.print(f"知识库路径：{state.config.knowledge_path}")
    console.print(f"当前平台：{state.config.platform}")
    console.print(f"当前语言：{state.config.language}")


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
        config: bool = typer.Option(
            False,
            "--config",
            "-c",
            help="查看或修改配置。",
        ),
        path: str | None = typer.Option(
            None,
            "--path",
            help="设置知识库路径（需要配合 --config）。",
        ),
        platform: str | None = typer.Option(
            None,
            "--platform",
            "-p",
            help="查看或设置目标平台。",
        ),
        language: str | None = typer.Option(
            None,
            "--language",
            "-l",
            help="查看或设置目标语言。",
        ),
        update: bool = typer.Option(
            False,
            "--update",
            "-u",
            help="更新知识库（暂未实现）。",
        ),
                installer_check: bool = typer.Option(
            False,
            "--installer-check",
            hidden=True,
        ),
        installer_deploy: bool = typer.Option(
            False,
            "--installer-deploy",
            hidden=True,
        ),
        installer_replace: bool = typer.Option(
            False,
            "--installer-replace",
            hidden=True,
        ),
        installer_source: str | None = typer.Option(
            None,
            "--installer-source",
            hidden=True,
        ),
        installer_integrity: str | None = typer.Option(
            None,
            "--installer-integrity",
            hidden=True,
        ),
        installer_init: bool = typer.Option(
            False,
            "--installer-init",
            hidden=True,
        ),


    ) -> None:
        console = Console()

        installer_operation = installer_check or installer_deploy

        if (
            installer_operation
            or installer_replace
            or installer_source is not None
            or installer_integrity is not None
        ):
            invalid_common_options = (
                version
                or config
                or path is not None
                or platform is not None
                or language is not None
                or update
                or installer_init
                or ctx.invoked_subcommand is not None
                or ctx.meta.get("lcmd_dynamic_arguments") is not None
            )

            valid_check = (
                installer_check
                and not installer_deploy
                and not installer_replace
                and installer_source is None
                and installer_integrity is None
            )

            valid_deploy = (
                installer_deploy
                and not installer_check
                and installer_source is not None
                and bool(installer_source.strip())
                and installer_integrity is not None
                and bool(installer_integrity.strip())
            )

            if invalid_common_options or not (valid_check or valid_deploy):
                console.print("安装器参数组合无效。", style="red")
                raise typer.Exit(code=2)

            if installer_check:
                try:
                    destination_state = check_installer_destination()
                except (InstallerError, PathSecurityError, OSError) as exc:
                    console.print(f"知识库目录检查失败：{exc}", style="red")
                    raise typer.Exit(code=1) from None

                if destination_state in (
                    KnowledgeDestinationState.MISSING,
                    KnowledgeDestinationState.EMPTY,
                ):
                    console.print("知识库安装目标可以直接部署。")
                    raise typer.Exit(code=0)

                if destination_state == KnowledgeDestinationState.VALID:
                    console.print("安装目标已有有效知识库，需要确认替换。")
                    raise typer.Exit(code=10)

                if destination_state == KnowledgeDestinationState.INVALID:
                    console.print("安装目标已有无效或非空内容，需要确认替换。")
                    raise typer.Exit(code=11)

                console.print("无法识别知识库安装目标状态。", style="red")
                raise typer.Exit(code=1)

            try:
                with Progress(
                    TextColumn("{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console,
                ) as progress:
                    task_id = progress.add_task(
                        "正在部署知识库",
                        total=1,
                    )

                    def update_progress(
                        copied_bytes: int,
                        total_bytes: int,
                    ) -> None:
                        progress.update(
                            task_id,
                            total=max(total_bytes, 1),
                            completed=(
                                copied_bytes if total_bytes > 0 else 1
                            ),
                        )

                    deployed_path = deploy_installer_knowledge(
                        installer_source,
                        installer_integrity,
                        replace_existing=installer_replace,
                        progress_callback=update_progress,
                    )

                initialized_config = initialize_installer_config(
                    str(deployed_path),
                )

            except (
                InstallerError,
                PathSecurityError,
                ConfigError,
                OSError,
            ) as exc:
                console.print(f"知识库部署失败：{exc}", style="red")
                raise typer.Exit(code=1) from None

            console.print(
                f"知识库部署及配置初始化成功：{initialized_config.knowledge_path}",
                style="green",
            )
            raise typer.Exit(code=0)            

        if installer_init:
            if (
                path is None
                or version
                or config
                or platform is not None
                or language is not None
                or update
                or ctx.invoked_subcommand is not None
                or ctx.meta.get("lcmd_dynamic_arguments") is not None
            ):
                console.print(
                    "--installer-init 必须单独配合 --path 使用。",
                    style="red",
                )
                raise typer.Exit(code=2)

            try:
                initialized_config = initialize_installer_config(path)
            except (PathSecurityError, ConfigError, OSError) as exc:
                console.print(
                    f"安装配置初始化失败：{exc}",
                    style="red",
                )
                raise typer.Exit(code=1) from None

            console.print(
                f"安装配置初始化成功，知识库路径：{initialized_config.knowledge_path}",
                style="green",
            )
            raise typer.Exit()

        config_options_used = (
            config or path is not None or platform is not None or language is not None
        )

        if version:
            if config_options_used or update:
                console.print("--version 不能与配置或更新参数同时使用。", style="red")
                raise typer.Exit(code=2)

            _show_version(console)
            raise typer.Exit()

        if update:
            if config_options_used:
                console.print("--update 不能与配置参数同时使用。", style="red")
                raise typer.Exit(code=2)

            console.print("知识库更新功能尚未实现。", style="yellow")
            raise typer.Exit()

        if (path is not None or platform is not None or language is not None) and not config:
            console.print(
                "--path、--platform 和 --language 必须配合 --config/-c 使用。",
                style="red",
            )
            raise typer.Exit(code=2)

        if path is not None and (platform is not None or language is not None):
            console.print("--path 不能与 --platform 或 --language 同时使用。", style="red")
            raise typer.Exit(code=2)

        try:
            state = initialize_state()
        except MigrationError as exc:
            console.print(f"知识库迁移恢复失败：{exc}", style="red")
            raise typer.Exit(code=1) from None
        except (ConfigError, KnowledgeLoadError, OSError):
            console.print("LCMD 初始化失败，请检查配置。", style="red")
            raise typer.Exit(code=1) from None

        ctx.obj = state

        if config:
            if path is not None:
                config_file = get_config_file()

                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console,
                ) as progress:
                    task_id = progress.add_task("复制知识库", total=None)

                    def report_progress(
                        copied_bytes: int,
                        total_bytes: int,
                    ) -> None:
                        total = max(total_bytes, 1)
                        completed = 1 if total_bytes == 0 else copied_bytes

                        progress.update(
                            task_id,
                            total=total,
                            completed=completed,
                        )

                    try:
                        with warnings.catch_warnings(record=True) as migration_warnings:
                            warnings.simplefilter(
                                "always",
                                MigrationCleanupWarning,
                            )

                            try:
                                migrated_config = migrate_knowledge(
                                    config_file,
                                    path,
                                    progress_callback=report_progress,
                                )
                            except MigrationConfirmationRequired as exc:
                                console.print(str(exc), style="yellow")

                                confirmed = typer.confirm(
                                    "覆盖将删除目标目录及其全部原有内容，是否继续？",
                                    default=False,
                                )

                                if not confirmed:
                                    console.print("已取消知识库迁移，当前配置未更改。")
                                    raise typer.Exit() from None

                                migrated_config = migrate_knowledge(
                                    config_file,
                                    path,
                                    overwrite=True,
                                    progress_callback=report_progress,
                                )

                    except MigrationError as exc:
                        console.print(
                            f"知识库迁移失败：{exc}",
                            style="red",
                        )
                        raise typer.Exit(code=1) from None

                for warning in migration_warnings:
                    console.print(
                        f"迁移警告：{warning.message}",
                        style="yellow",
                    )

                console.print(
                    f"知识库迁移成功，新路径：{migrated_config.knowledge_path}",
                    style="green",
                )
                raise typer.Exit()

            if platform is None and language is None:
                _show_configuration(state, console)
                raise typer.Exit()

            if platform == "" or platform is None:
                if platform is not None:
                    _show_platforms(state, console)

            if language == "":
                _show_languages(state, console)

            if platform == "" and language not in (None, ""):
                console.print("不能在查看平台的同时切换语言。", style="red")
                raise typer.Exit(code=2)

            if language == "" and platform not in (None, ""):
                console.print("不能在查看语言的同时切换平台。", style="red")
                raise typer.Exit(code=2)

            if platform == "" or language == "":
                raise typer.Exit()

            if platform is None and language is None:
                raise typer.Exit()

            try:
                new_state = switch_configuration(
                    state,
                    get_config_file(),
                    platform=platform,
                    language=language,
                )
            except (KnowledgeLoadError, ConfigError):
                console.print("配置修改失败，当前配置保持不变。", style="red")
                raise typer.Exit(code=1) from None

            if platform is not None:
                console.print(f"已切换平台：{new_state.config.platform}")
            if language is not None:
                console.print(f"已切换语言：{new_state.config.language}")

            raise typer.Exit()

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
        keyword: Annotated[
            list[str],
            typer.Argument(help="一个或多个搜索关键词。"),
        ],
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

    return app
