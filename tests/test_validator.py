"""LCMD 知识文档 Schema 校验器测试."""

import pytest

from lcmd.knowledge.parser import ParsedDocument
from lcmd.knowledge.validator import DocumentValidationError, validate_document


def make_document(metadata, body="# 示例\n\n文档正文。\n"):
    """创建用于测试的解析后文档."""
    return ParsedDocument(metadata=metadata, body=body)


def test_validate_command_document():
    """应接受符合 Schema 的命令文档."""
    document = make_document({"summary": "复制文件和目录。"})

    result = validate_document(document, document_type="command")

    assert result == {"summary": "复制文件和目录。"}


def test_validate_document_rejects_missing_summary():
    """缺少必填 summary 时应报错."""
    document = make_document({})

    with pytest.raises(DocumentValidationError, match="summary"):
        validate_document(document, document_type="command")


@pytest.mark.parametrize(
    "summary",
    [
        None,
        123,
        ["复制文件"],
    ],
)
def test_validate_document_rejects_non_string_summary(summary):
    """summary 不是字符串时应报错."""
    document = make_document({"summary": summary})

    with pytest.raises(DocumentValidationError, match="summary"):
        validate_document(document, document_type="command")


@pytest.mark.parametrize(
    "summary",
    [
        "",
        "   ",
        "\t\n",
    ],
)
def test_validate_document_rejects_empty_summary(summary):
    """summary 为空或只有空白字符时应报错."""
    document = make_document({"summary": summary})

    with pytest.raises(DocumentValidationError, match="summary"):
        validate_document(document, document_type="command")


@pytest.mark.parametrize(
    "metadata",
    [
        {
            "summary": "复制文件和目录。",
            "keywords": ["复制"],
        },
        {
            "summary": "查找大文件。",
            "commands": ["find", "du"],
        },
    ],
)
def test_validate_command_document_rejects_unknown_fields(metadata):
    """命令文档不允许出现未定义字段，包括旧任务文档字段."""
    document = make_document(metadata)

    with pytest.raises(DocumentValidationError):
        validate_document(document, document_type="command")


def test_validate_command_document_rejects_empty_body():
    """命令文档正文为空时应报错."""
    document = make_document(
        {"summary": "复制文件和目录。"},
        body="",
    )

    with pytest.raises(DocumentValidationError, match="正文"):
        validate_document(document, document_type="command")


def test_validate_command_document_rejects_whitespace_body():
    """命令文档正文只有空白字符时应报错."""
    document = make_document(
        {"summary": "查找大文件。"},
        body=" \n\t\n",
    )

    with pytest.raises(DocumentValidationError, match="正文"):
        validate_document(document, document_type="command")


def test_validate_document_rejects_unsupported_document_type():
    """不支持的文档类型应明确报错."""
    document = make_document({"summary": "测试。"})

    with pytest.raises(ValueError, match="不支持"):
        validate_document(document, document_type="other")
