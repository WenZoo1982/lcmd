import pytest

from lcmd.knowledge.parser import (
    DocumentParseError,
    ParsedDocument,
    parse_document,
)


def test_parse_document_returns_metadata_and_body():
    content = (
        "+++\n"
        'summary = "查看目录内容。"\n'
        'custom = "保留未知字段"\n'
        "+++\n"
        "\n"
        "---\n"
        "\n"
        "## 用途\n"
        "\n"
        "查看当前目录。\n"
    )

    result = parse_document(content)

    assert isinstance(result, ParsedDocument)
    assert result.metadata == {
        "summary": "查看目录内容。",
        "custom": "保留未知字段",
    }
    assert result.body == ("\n---\n\n## 用途\n\n查看当前目录。\n")


def test_parse_document_preserves_markdown_separator():
    content = '+++\nsummary = "测试"\n+++\n---\n正文\n'

    result = parse_document(content)

    assert result.body.startswith("---\n")


def test_parse_document_preserves_empty_metadata():
    content = "+++\n+++\n---\n正文\n"

    result = parse_document(content)

    assert result.metadata == {}
    assert result.body == "---\n正文\n"


def test_parse_document_preserves_multiline_toml_values():
    content = '+++\nsummary = """\n多行摘要\n第二行\n"""\n+++\n---\n正文\n'

    result = parse_document(content)

    assert result.metadata["summary"] == "多行摘要\n第二行\n"


def test_parse_document_rejects_missing_opening_marker():
    with pytest.raises(DocumentParseError):
        parse_document('summary = "测试"\n+++\n---\n正文\n')


def test_parse_document_rejects_missing_closing_marker():
    with pytest.raises(DocumentParseError):
        parse_document('+++\nsummary = "测试"\n')


def test_parse_document_rejects_invalid_toml():
    content = '+++\nsummary = "未闭合字符串\n+++\n---\n正文\n'

    with pytest.raises(DocumentParseError):
        parse_document(content)


def test_parse_document_rejects_duplicate_toml_keys():
    content = '+++\nsummary = "第一条"\nsummary = "第二条"\n+++\n---\n正文\n'

    with pytest.raises(DocumentParseError):
        parse_document(content)


def test_parse_document_does_not_validate_summary():
    content = '+++\nother = "没有 summary"\n+++\n---\n正文\n'

    result = parse_document(content)

    assert result.metadata == {"other": "没有 summary"}


def test_parse_document_does_not_validate_body_separator():
    content = '+++\nsummary = "测试"\n+++\n这里没有正文分隔线\n'

    result = parse_document(content)

    assert result.body == "这里没有正文分隔线\n"


def test_parse_document_accepts_empty_body_for_validator():
    content = '+++\nsummary = "测试"\n+++\n'

    result = parse_document(content)

    assert result.body == ""


def test_parse_document_rejects_empty_content():
    with pytest.raises(DocumentParseError):
        parse_document("")
