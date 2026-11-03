from pathlib import PurePosixPath

from lcmd.knowledge.models import KnowledgeBase, KnowledgeDocument, QueryResult


def _get_tool_documents(
    knowledge: KnowledgeBase,
    tool: str,
) -> tuple[tuple[KnowledgeDocument, tuple[str, ...]], ...]:
    """获取指定工具的文档及其相对路径段。"""
    results = []

    for document in knowledge.documents:
        if document.category != "tools":
            continue

        if document.tool is None or document.tool.lower() != tool:
            continue

        parts = PurePosixPath(document.id).parts

        if (
            len(parts) < 4
            or parts[0] != "tools"
            or parts[1].lower() != tool
            or parts[2] != knowledge.language
        ):
            continue

        results.append((document, parts[3:]))

    return tuple(results)


def _find_tool_entry(
    tool_documents: tuple[tuple[KnowledgeDocument, tuple[str, ...]], ...],
    tool: str,
) -> KnowledgeDocument | None:
    """查找工具入口文档。"""
    entry_name = f"{tool}.md"

    for document, relative_parts in tool_documents:
        if relative_parts == (entry_name,):
            return document

    return None


def _find_document(
    tool_documents: tuple[tuple[KnowledgeDocument, tuple[str, ...]], ...],
    target: tuple[str, ...],
) -> KnowledgeDocument | None:
    """查找指定子命令文档。"""
    if not target:
        return None

    expected_path = (*target[:-1], f"{target[-1]}.md")

    for document, relative_parts in tool_documents:
        if relative_parts == expected_path:
            return document

    return None


def _find_children(
    tool_documents: tuple[tuple[KnowledgeDocument, tuple[str, ...]], ...],
    target: tuple[str, ...],
    tool: str,
) -> tuple[str, ...]:
    """根据文档路径推导指定目录下的直接子命令。"""
    children = set()

    for _, relative_parts in tool_documents:
        if not relative_parts:
            continue

        if target:
            if relative_parts[: len(target)] != target:
                continue

            remaining = relative_parts[len(target) :]
        else:
            remaining = relative_parts

        if len(remaining) == 1:
            child_name = PurePosixPath(remaining[0]).stem

            if not target and child_name == tool:
                continue

            children.add(child_name)
        elif len(remaining) > 1:
            children.add(remaining[0])

    return tuple(sorted(children))


def _query_tool(
    knowledge: KnowledgeBase,
    tool: str,
    subcommands: tuple[str, ...],
) -> tuple[tuple[KnowledgeDocument, ...], tuple[str, ...]]:
    """查询工具入口或指定子命令。"""
    tool_documents = _get_tool_documents(knowledge, tool)

    if not tool_documents:
        return (), ()

    if not subcommands:
        entry = _find_tool_entry(tool_documents, tool)

        if entry is not None:
            return (
                (entry,),
                _find_children(tool_documents, (), tool),
            )

        documents = tuple(document for document, _ in tool_documents)

        if len(documents) == 1:
            return documents, ()

        return tuple(sorted(documents, key=lambda item: item.id)), ()

    document = _find_document(tool_documents, subcommands)
    children = _find_children(tool_documents, subcommands, tool)

    documents = (document,) if document is not None else ()

    return documents, children


def query_document(
    knowledge: KnowledgeBase,
    arguments: tuple[str, ...],
) -> QueryResult:
    """根据命令或工具路径查询知识文档。"""
    if not arguments:
        return QueryResult(documents=(), children=())

    normalized = tuple(argument.lower() for argument in arguments)

    matched_ids = set()
    children = set()

    # 单参数查询同时匹配平台命令和同名工具。
    if len(normalized) == 1:
        command = normalized[0]

        for document in knowledge.documents:
            if document.category != "platforms":
                continue

            if document.platform != knowledge.platform:
                continue

            if document.language != knowledge.language:
                continue

            if PurePosixPath(document.id).stem.lower() == command:
                matched_ids.add(document.id)

    tool_documents, tool_children = _query_tool(
        knowledge,
        normalized[0],
        normalized[1:],
    )

    matched_ids.update(document.id for document in tool_documents)
    children.update(tool_children)

    documents = tuple(
        sorted(
            (document for document in knowledge.documents if document.id in matched_ids),
            key=lambda item: item.id,
        )
    )

    return QueryResult(
        documents=documents,
        children=tuple(sorted(children)),
    )
