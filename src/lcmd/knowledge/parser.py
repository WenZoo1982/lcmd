import tomllib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """解析后的文档中间数据。"""

    metadata: dict[str, object]
    body: str


class DocumentParseError(ValueError):
    """文档 Front Matter 无法解析。"""


def parse_document(content: str) -> ParsedDocument:
    """解析 TOML Front Matter，并保留完整 Markdown 正文。"""
    lines = content.splitlines(keepends=True)

    if not lines or lines[0].rstrip("\r\n") != "+++":
        raise DocumentParseError("文档缺少 Front Matter 起始标记。")

    closing_index = None

    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == "+++":
            closing_index = index
            break

    if closing_index is None:
        raise DocumentParseError("文档缺少 Front Matter 结束标记。")

    front_matter = "".join(lines[1:closing_index])

    try:
        metadata = tomllib.loads(front_matter)
    except tomllib.TOMLDecodeError as exc:
        raise DocumentParseError("Front Matter TOML 格式错误。") from exc

    body = "".join(lines[closing_index + 1 :])

    return ParsedDocument(
        metadata=metadata,
        body=body,
    )
