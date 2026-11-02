"""LCMD 命令关键词搜索."""

from lcmd.knowledge.loader import LoadedDocument


def _normalize_keywords(query: str) -> list[str]:
    """按空白字符拆分关键词，并去除重复项."""
    return list(dict.fromkeys(keyword.casefold() for keyword in query.split()))


def search_commands(
    commands: list[LoadedDocument],
    query: str,
    full: bool = False,
) -> list[LoadedDocument]:
    """按关键词搜索命令文档，并按命中关键词数量排序.

    普通搜索匹配文件名和 summary。
    full 模式额外匹配 Markdown 正文。

    多关键词采用 OR 匹配。命中关键词越多，排名越靠前。
    相关度相同时，按命令名称排序。

    Args:
        commands: 已加载的命令文档。
        query: 用户输入的搜索关键词。
        full: 是否扩大到 Markdown 正文进行搜索。

    Returns:
        按相关度排序的命令文档列表。
    """
    keywords = _normalize_keywords(query)

    if not keywords:
        return []

    matches: list[tuple[int, str, LoadedDocument]] = []

    for command in commands:
        summary = str(command.metadata.get("summary", ""))
        searchable_text = f"{command.name}\n{summary}"

        if full:
            searchable_text += f"\n{command.body}"

        searchable_text = searchable_text.casefold()

        matched_count = sum(1 for keyword in keywords if keyword in searchable_text)

        if matched_count:
            matches.append((matched_count, command.name.casefold(), command))

    matches.sort(key=lambda item: (-item[0], item[1]))

    return [item[2] for item in matches]
