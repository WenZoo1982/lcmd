from lcmd.knowledge.parser import ParsedDocument


class DocumentValidationError(ValueError):
    """知识文档不符合格式规范。"""


def validate_document(document: ParsedDocument) -> None:
    """验证解析后的知识文档是否符合 LCMD 文档格式。"""
    if not isinstance(document.metadata, dict):
        raise DocumentValidationError("Front Matter 必须是 TOML 表格。")

    if set(document.metadata) != {"summary"}:
        raise DocumentValidationError("Front Matter 必须且只能包含 summary 字段。")

    summary = document.metadata["summary"]

    if not isinstance(summary, str) or not summary.strip():
        raise DocumentValidationError("summary 必须是非空字符串。")

    body = document.body

    if not isinstance(body, str):
        raise DocumentValidationError("正文必须是字符串。")

    lines = body.splitlines()

    separator_index = next(
        (index for index, line in enumerate(lines) if line.strip()),
        None,
    )

    if separator_index is None or lines[separator_index] != "---":
        raise DocumentValidationError("正文必须以独立行 --- 开始。")

    content = "\n".join(lines[separator_index + 1 :])

    if not content.strip():
        raise DocumentValidationError("正文内容不能为空。")
