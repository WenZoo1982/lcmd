import sys
from pathlib import PurePosixPath

from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from lcmd.knowledge.models import KnowledgeDocument, QueryResult, SearchResult


def _get_document_name(document: KnowledgeDocument) -> str:
    """根据文档 ID 获取显示名称。"""
    parts = PurePosixPath(document.id).parts

    if document.category == "platforms":
        return PurePosixPath(parts[-1]).stem

    if document.category == "tools":
        relative_parts = parts[3:]
        names = [PurePosixPath(part).stem for part in relative_parts]

        return " ".join(names)

    return PurePosixPath(document.id).stem


def _get_document_source(document: KnowledgeDocument) -> str:
    """获取文档来源说明。"""
    if document.category == "platforms":
        return f"平台命令 · {document.platform}"

    return f"第三方工具 · {document.tool}"


def _get_console(console: Console | None) -> Console:
    """获取终端输出实例。"""
    return console if console is not None else Console()


def render_document(
    document: KnowledgeDocument,
    console: Console | None = None,
) -> None:
    """显示一篇知识文档。"""
    output = _get_console(console)

    title = _get_document_name(document)
    source = _get_document_source(document)

    output.print(
        Panel(
            Markdown(document.body),
            title=title,
            subtitle=source,
            border_style="cyan",
            expand=True,
        )
    )


def render_query_result(
    result: QueryResult,
    console: Console | None = None,
) -> None:
    """显示精确查询结果及可用子命令。"""
    output = _get_console(console)

    if not result.documents and not result.children:
        output.print("未找到相关命令或工具。", style="yellow")
        return

    for index, document in enumerate(result.documents):
        if index:
            output.print()

        render_document(document, output)

    if result.children:
        commands = Columns(
            [Text(child, style="green") for child in result.children],
            equal=False,
            expand=True,
        )

        output.print(
            Panel(
                commands,
                title="可用子命令",
                border_style="cyan",
                expand=True,
            )
        )


def _render_search_page(
    results: tuple[SearchResult, ...],
    start: int,
    end: int,
    console: Console,
) -> None:
    """显示一页搜索结果。"""
    table = Table(
        title=f"搜索结果（{start + 1}-{end}）",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
        expand=True,
    )

    table.add_column("名称", style="green", no_wrap=True)
    table.add_column("来源", style="cyan", no_wrap=True)
    table.add_column("用途摘要", overflow="fold")

    for result in results[start:end]:
        document = result.document

        table.add_row(
            _get_document_name(document),
            _get_document_source(document),
            document.summary,
        )

    console.print(table)


def render_search_results(
    results: tuple[SearchResult, ...],
    console: Console | None = None,
    page_size: int = 5,
) -> None:
    """显示搜索结果，必要时提供交互式分页。"""
    output = _get_console(console)

    if page_size < 1:
        raise ValueError("page_size 必须大于 0。")

    if not results:
        output.print("未找到相关命令或工具。", style="yellow")
        return

    total = len(results)

    # 非交互终端或结果数量未超过分页阈值时，一次性显示。
    if total <= page_size or not output.is_terminal or not sys.stdin.isatty():
        _render_search_page(results, 0, total, output)
        return

    start = 0

    while start < total:
        end = min(start + page_size, total)

        _render_search_page(results, start, end, output)

        start = end

        if start >= total:
            break

        while True:
            answer = output.input("[dim]按 Enter 查看下一页，按 Q 退出：[/dim]").strip().casefold()

            if answer == "q":
                return

            if not answer:
                break

        output.print()
