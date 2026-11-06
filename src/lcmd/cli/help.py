"""LCMD 本地化 CLI 帮助系统。"""

import ctypes
import locale
import sys
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text
from typer.core import TyperCommand


def get_help_language() -> str:
    """根据系统界面语言选择帮助语言，中文以外默认使用英文。"""
    if sys.platform == "win32":
        try:
            language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if language_id & 0x3FF == 0x04:
                return "zh"
            if language_id:
                return "en"
        except (AttributeError, OSError):
            pass

    categories = []
    messages_category = getattr(locale, "LC_MESSAGES", None)

    if messages_category is not None:
        categories.append(messages_category)

    categories.append(locale.LC_CTYPE)

    for category in categories:
        try:
            language, _ = locale.getlocale(category)
        except (ValueError, OSError):
            continue

        if not language:
            continue

        normalized = language.lower().replace("-", "_")

        if normalized.startswith(("zh", "chinese")):
            return "zh"

        return "en"

    return "en"


def _option_text(
    short_option: str | None,
    long_option: str,
    placeholder: str = "",
) -> Text:
    """构造选项名称，短参数使用强调色，长参数保持普通颜色。"""
    result = Text()

    if short_option:
        result.append(short_option, style="bold cyan")
        result.append(", ")

    result.append(long_option)

    if placeholder:
        result.append(f" {placeholder}")

    return result


def _new_options_table() -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True)
    table.add_column()
    return table

def _render(*content: Any) -> str:
    """组合 Rich 内容并返回帮助文本。"""
    console = Console(
        record=True,
        force_terminal=True,
        color_system="standard",
        width=100,
    )

    with console.capture() as capture:
        console.print(*content, sep="\n")

    return capture.get().rstrip()

def render_main_help(ctx: Any) -> str:
    """生成主帮助内容。"""
    if get_help_language() == "zh":
        return _render_main_help_zh()

    return _render_main_help_en()


def _render_main_help_zh() -> str:
    title = Text("LCMD", style="bold cyan")
    title.append(" — 多平台命令速查与学习工具")

    description = Text(
        "查询 Linux、Windows 和第三方工具的命令知识，帮助了解命令用途、语法、常用参数与示例。"
    )

    usage = Text("用法：", style="bold")
    usage.append("lcmd [选项] [命令或工具] [子命令...]")

    options = _new_options_table()
    options.add_row(
        _option_text("-v", "--version"),
        "显示程序和知识库版本。",
    )
    options.add_row(
        _option_text("-c", "--config"),
        "查看或修改配置。",
    )
    options.add_row(
        _option_text(None, "--path", "PATH"),
        "迁移知识库到指定路径（需要配合 --config）。",
    )
    options.add_row(
        _option_text("-p", "--platform", "[PLATFORM]"),
        "查看可用平台或设置目标平台（需要配合 --config）。",
    )
    options.add_row(
        _option_text("-l", "--language", "[LANGUAGE]"),
        "查看可用语言或设置知识库语言（需要配合 --config）。",
    )
    options.add_row(
        _option_text("-h", "--help"),
        "显示帮助信息。",
    )

    commands = _new_options_table()
    commands.add_row(
        Text("COMMAND", style="bold"),
        "命令或工具名称，可以包含多级子命令。",
    )
    commands.add_row(
        Text("search", style="bold"),
        "按关键词搜索知识库。",
    )

    examples = Text()
    examples.append("查询命令\n", style="bold")
    examples.append("  lcmd ls\n")
    examples.append("  lcmd git status\n")
    examples.append("  lcmd docker compose up\n\n")

    examples.append("搜索知识库\n", style="bold")
    examples.append('  lcmd search "文件 权限"\n')
    examples.append("  lcmd search 文件 --full\n\n")

    examples.append("查看和修改配置\n", style="bold")
    examples.append("  lcmd -c\n")
    examples.append("  lcmd -c -p\n")
    examples.append("  lcmd -c -l\n")
    examples.append("  lcmd -c -p linux\n")
    examples.append("  lcmd -c -l en-US\n")
    examples.append("  lcmd -c -p linux -l zh-CN\n\n")

    examples.append("迁移知识库路径\n", style="bold")
    examples.append("  lcmd -c --path D:\\LCMD\\knowledge\n")
    examples.append('  lcmd -c --path "D:\\My Data\\LCMD Knowledge"\n')
    examples.append("  lcmd -c --path /home/user/LCMD/knowledge\n")
    examples.append('  lcmd -c --path "/home/user/My Data/LCMD Knowledge"')

    notes = Text()
    notes.append("说明\n", style="bold")
    notes.append("  • LCMD 只查询和展示命令知识，不会执行系统命令。\n")
    notes.append("  • --platform、--language 和 --path 必须配合 --config/-c 使用。\n")
    notes.append("  • --path 不能与 --platform 或 --language 同时使用。\n")
    notes.append("  • 平台和语言值必须是当前知识库支持的值。\n")
    notes.append("  • 参数值不含空格时可以不加引号；含空格时必须使用引号。\n")
    notes.append("  • 迁移路径已存在时，LCMD 会询问是否覆盖目标目录。\n")
    notes.append("  • 帮助语言根据系统语言选择，不受知识库查询语言设置影响。\n")
    notes.append("  • 使用 lcmd search --help 查看搜索帮助。")

    return _render(
        title,
        description,
        "",
        usage,
        "",
        Text("选项", style="bold"),
        options,
        "",
        Text("命令", style="bold"),
        commands,
        "",
        Text("常用示例", style="bold"),
        examples,
        "",
        notes,
    )


def _render_main_help_en() -> str:
    title = Text("LCMD", style="bold cyan")
    title.append(" — Multi-platform Command Reference and Learning Tool")

    description = Text(
        "Look up command knowledge for Linux, Windows, and third-party tools, "
        "including descriptions, syntax, common options, and examples."
    )

    usage = Text("Usage: ", style="bold")
    usage.append("lcmd [OPTIONS] [COMMAND OR TOOL] [SUBCOMMAND...]")

    options = _new_options_table()
    options.add_row(
        _option_text("-v", "--version"),
        "Show the application and knowledge base versions.",
    )
    options.add_row(
        _option_text("-c", "--config"),
        "View or modify configuration.",
    )
    options.add_row(
        _option_text(None, "--path", "PATH"),
        "Migrate the knowledge base to a new path (requires --config).",
    )
    options.add_row(
        _option_text("-p", "--platform", "[PLATFORM]"),
        "List available platforms or set the target platform (requires --config).",
    )
    options.add_row(
        _option_text("-l", "--language", "[LANGUAGE]"),
        "List available languages or set the knowledge language (requires --config).",
    )
    options.add_row(
        _option_text("-h", "--help"),
        "Show this help message.",
    )

    commands = _new_options_table()
    commands.add_row(
        Text("COMMAND", style="bold"),
        "A command or tool name, optionally followed by nested subcommands.",
    )
    commands.add_row(
        Text("search", style="bold"),
        "Search the knowledge base by keywords.",
    )

    examples = Text()
    examples.append("Query commands\n", style="bold")
    examples.append("  lcmd ls\n")
    examples.append("  lcmd git status\n")
    examples.append("  lcmd docker compose up\n\n")

    examples.append("Search the knowledge base\n", style="bold")
    examples.append('  lcmd search "file permissions"\n')
    examples.append("  lcmd search files --full\n\n")

    examples.append("View and modify configuration\n", style="bold")
    examples.append("  lcmd -c\n")
    examples.append("  lcmd -c -p\n")
    examples.append("  lcmd -c -l\n")
    examples.append("  lcmd -c -p linux\n")
    examples.append("  lcmd -c -l en-US\n")
    examples.append("  lcmd -c -p linux -l zh-CN\n\n")

    examples.append("Migrate the knowledge base\n", style="bold")
    examples.append("  lcmd -c --path D:\\LCMD\\knowledge\n")
    examples.append('  lcmd -c --path "D:\\My Data\\LCMD Knowledge"\n')
    examples.append("  lcmd -c --path /home/user/LCMD/knowledge\n")
    examples.append('  lcmd -c --path "/home/user/My Data/LCMD Knowledge"')

    notes = Text()
    notes.append("Notes\n", style="bold")
    notes.append(
        "  • LCMD looks up and displays command knowledge; it does not execute commands.\n"
    )
    notes.append("  • --platform, --language, and --path require --config/-c.\n")
    notes.append("  • --path cannot be used with --platform or --language.\n")
    notes.append(
        "  • Platform and language values must be supported by the current knowledge base.\n"
    )
    notes.append("  • Quote argument values only when they contain spaces.\n")
    notes.append("  • If the migration target already exists, LCMD asks before replacing it.\n")
    notes.append(
        "  • Help language follows the system language and is independent of knowledge language.\n"
    )
    notes.append("  • Run lcmd search --help for search-specific help.")

    return _render(
        title,
        description,
        "",
        usage,
        "",
        Text("Options", style="bold"),
        options,
        "",
        Text("Commands", style="bold"),
        commands,
        "",
        Text("Examples", style="bold"),
        examples,
        "",
        notes,
    )


def render_search_help(ctx: Any) -> str:
    """生成 search 子命令帮助内容。"""
    if get_help_language() == "zh":
        return _render_search_help_zh()

    return _render_search_help_en()


def _render_search_help_zh() -> str:
    title = Text("搜索知识库", style="bold cyan")

    usage = Text("用法：", style="bold")
    usage.append("lcmd search [选项] 关键词...")

    arguments = _new_options_table()
    arguments.add_row(
        Text("关键词", style="bold"),
        "一个或多个搜索关键词，多个关键词可以用空格分隔。",
    )

    options = _new_options_table()
    options.add_row(
        _option_text(None, "--full"),
        "搜索文档全文，而不只是标题和摘要。",
    )
    options.add_row(
        _option_text("-h", "--help"),
        "显示搜索帮助。",
    )

    examples = Text()
    examples.append("  lcmd search 文件\n")
    examples.append('  lcmd search "文件 权限"\n')
    examples.append("  lcmd search 网络 --full")

    return _render(
        title,
        "在当前平台和知识库语言对应的文档中搜索关键词。",
        "",
        usage,
        "",
        Text("参数", style="bold"),
        arguments,
        "",
        Text("选项", style="bold"),
        options,
        "",
        Text("示例", style="bold"),
        examples,
    )


def _render_search_help_en() -> str:
    title = Text("Search the Knowledge Base", style="bold cyan")

    usage = Text("Usage: ", style="bold")
    usage.append("lcmd search [OPTIONS] KEYWORD...")

    arguments = _new_options_table()
    arguments.add_row(
        Text("KEYWORD", style="bold"),
        "One or more search keywords. Separate multiple keywords with spaces.",
    )

    options = _new_options_table()
    options.add_row(
        _option_text(None, "--full"),
        "Search the full document content instead of titles and summaries only.",
    )
    options.add_row(
        _option_text("-h", "--help"),
        "Show search help.",
    )

    examples = Text()
    examples.append("  lcmd search files\n")
    examples.append('  lcmd search "file permissions"\n')
    examples.append("  lcmd search network --full")

    return _render(
        title,
        "Search documents for the current platform and knowledge language.",
        "",
        usage,
        "",
        Text("Arguments", style="bold"),
        arguments,
        "",
        Text("Options", style="bold"),
        options,
        "",
        Text("Examples", style="bold"),
        examples,
    )


class LocalizedTyperCommand(TyperCommand):
    """使用 LCMD 自定义格式显示子命令帮助。"""

    def get_help(self, ctx: Any) -> str:
        return render_search_help(ctx)
