"""LCMD 知识库命令查询."""

from lcmd.knowledge.loader import LoadedDocument


def find_command(
    commands: list[LoadedDocument],
    name: str,
) -> LoadedDocument | None:
    """根据命令名称精确查询知识库.

    命令名称不区分大小写，不进行前缀或子字符串匹配。

    Args:
        commands: 已加载的命令文档列表。
        name: 用户输入的命令名称。

    Returns:
        匹配的命令文档；没有匹配结果时返回 None。

    Raises:
        ValueError: 知识库中存在大小写不敏感的重复命令名称。
    """
    if not name:
        return None

    normalized_name = name.casefold()

    matches = [command for command in commands if command.name.casefold() == normalized_name]

    if len(matches) > 1:
        raise ValueError(f"知识库中存在重复的命令名称：{name}")

    return matches[0] if matches else None
