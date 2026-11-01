"""LCMD 知识文档 Schema 校验器."""

from typing import Literal

from lcmd.knowledge.parser import ParsedDocument


class DocumentValidationError(ValueError):
    """知识文档 Schema 校验异常."""


def validate_document(
    document: ParsedDocument,
    document_type: Literal["command", "task"],
) -> dict:
    """校验解析后的知识文档，并返回符合 Schema 的元数据.

    Args:
        document: Parser 返回的解析结果。
        document_type: 文档类型，支持 command 和 task。

    Returns:
        通过校验的元数据字典。任务文档缺少 commands 时补充空数组。

    Raises:
        ValueError: 文档类型不受支持。
        DocumentValidationError: 文档不符合 Schema。
    """
    if document_type not in ("command", "task"):
        raise ValueError(f"不支持的文档类型：{document_type}")

    allowed_fields = {"summary"} if document_type == "command" else {"summary", "commands"}

    unknown_fields = set(document.metadata) - allowed_fields
    if unknown_fields:
        fields = "、".join(sorted(unknown_fields))
        raise DocumentValidationError(f"存在未定义字段：{fields}")

    summary = document.metadata.get("summary")

    if not isinstance(summary, str) or not summary.strip():
        raise DocumentValidationError("必填字段 summary 必须是非空字符串。")

    if not document.body.strip():
        raise DocumentValidationError("Markdown 正文不能为空。")

    metadata = dict(document.metadata)

    if document_type == "task":
        commands = metadata.setdefault("commands", [])

        if not isinstance(commands, list):
            raise DocumentValidationError("字段 commands 必须是字符串数组。")

        if not all(isinstance(command, str) for command in commands):
            raise DocumentValidationError("字段 commands 中的每一项都必须是字符串。")

    return metadata
