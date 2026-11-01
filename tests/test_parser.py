"""LCMD Markdown Front Matter 解析器测试."""

import pytest

from lcmd.knowledge.parser import DocumentParseError, parse_document


def test_parse_command_document():
    """应正确解析命令文档的元数据和正文."""
    content = '+++\nsummary = "复制文件和目录。"\n+++\n# cp\n\n复制文件和目录。\n'

    result = parse_document(content)

    assert result.metadata == {"summary": "复制文件和目录。"}
    assert result.body == "# cp\n\n复制文件和目录。\n"


def test_parse_task_document():
    """应正确解析任务文档及命令关联数组."""
    content = (
        "+++\n"
        'summary = "查找占用磁盘空间较大的文件。"\n'
        'commands = ["find", "du", "sort"]\n'
        "+++\n"
        "# 查找大文件\n"
        "\n"
        "使用 find 和 du 查找大文件。\n"
    )

    result = parse_document(content)

    assert result.metadata == {
        "summary": "查找占用磁盘空间较大的文件。",
        "commands": ["find", "du", "sort"],
    }
    assert result.body == "# 查找大文件\n\n使用 find 和 du 查找大文件。\n"


def test_parse_document_supports_crlf():
    """应支持 Windows CRLF 换行."""
    content = '+++\r\nsummary = "显示文件内容。"\r\n+++\r\n# cat\r\n\r\n显示文件内容。\r\n'

    result = parse_document(content)

    assert result.metadata == {"summary": "显示文件内容。"}
    assert result.body == "# cat\r\n\r\n显示文件内容。\r\n"


def test_parse_document_preserves_body_content():
    """应保留正文内容，不擅自修改正文格式."""
    body = "# 示例\n\n第一段。\n\n第二段。\n"

    content = '+++\nsummary = "测试。"\n+++\n' + body

    result = parse_document(content)

    assert result.body == body


def test_parse_document_allows_delimiter_in_body():
    """结束标记之后的正文可以包含 +++ 标记."""
    body = "# 示例\n\n+++\n\n正文内容。\n"
    content = '+++\nsummary = "测试。"\n+++\n' + body

    result = parse_document(content)

    assert result.body == body


def test_parse_document_rejects_missing_opening_delimiter():
    """缺少开头标记时应报错."""
    content = 'summary = "测试。"\n+++\n正文\n'

    with pytest.raises(DocumentParseError, match="必须以"):
        parse_document(content)


def test_parse_document_rejects_opening_delimiter_with_spaces():
    """开头标记不能包含额外空格."""
    content = ' +++\nsummary = "测试。"\n+++\n正文\n'

    with pytest.raises(DocumentParseError, match="必须以"):
        parse_document(content)


def test_parse_document_rejects_missing_closing_delimiter():
    """缺少结束标记时应报错."""
    content = '+++\nsummary = "测试。"\n正文\n'

    with pytest.raises(DocumentParseError, match="结束标记"):
        parse_document(content)


def test_parse_document_rejects_invalid_toml():
    """TOML 语法错误时应报错."""
    content = "+++\nsummary = \n+++\n正文\n"

    with pytest.raises(DocumentParseError, match="TOML"):
        parse_document(content)


def test_parse_document_accepts_empty_metadata():
    """空元数据由 Parser 解析，留给 Validator 判断."""
    content = "+++\n+++\n正文\n"

    result = parse_document(content)

    assert result.metadata == {}
    assert result.body == "正文\n"


def test_parse_document_accepts_empty_body():
    """空正文由 Parser 保留，留给 Validator 判断."""
    content = '+++\nsummary = "测试。"\n+++\n'

    result = parse_document(content)

    assert result.metadata == {"summary": "测试。"}
    assert result.body == ""


def test_parse_document_rejects_empty_content():
    """空文件不符合 Front Matter 结构."""
    with pytest.raises(DocumentParseError, match="必须以"):
        parse_document("")
