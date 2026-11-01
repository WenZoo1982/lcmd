"""LCMD Markdown Front Matter 解析器."""

import tomllib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedDocument:
    """解析后的 Markdown 文档."""

    metadata: dict[str, Any]
    body: str


class DocumentParseError(ValueError):
    """Markdown 文档 Front Matter 解析异常."""


def parse_document(content: str) -> ParsedDocument:
    """解析 Markdown 文档中的 TOML Front Matter 和正文.

    Front Matter 必须以独立的 +++ 行开始和结束。
    正文内容原样保留，不进行清理或格式转换。
    """
    lines = content.splitlines(keepends=True)

    if not lines or lines[0].rstrip("\r\n") != "+++":
        raise DocumentParseError("Front Matter 必须以独立的 +++ 开始标记。")

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.rstrip("\r\n") == "+++"),
        None,
    )

    if closing_index is None:
        raise DocumentParseError("Front Matter 缺少独立的 +++ 结束标记。")

    front_matter = "".join(lines[1:closing_index])

    try:
        metadata = tomllib.loads(front_matter)
    except tomllib.TOMLDecodeError as exc:
        raise DocumentParseError(f"Front Matter TOML 格式错误：{exc}") from exc

    body = "".join(lines[closing_index + 1 :])

    return ParsedDocument(
        metadata=metadata,
        body=body,
    )
