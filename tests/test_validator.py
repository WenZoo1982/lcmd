import pytest

from lcmd.knowledge.parser import ParsedDocument
from lcmd.knowledge.validator import (
    DocumentValidationError,
    validate_document,
)


def make_document(
    metadata=None,
    body="---\n\n## 用途\n\n测试正文。\n",
):
    if metadata is None:
        metadata = {"summary": "测试文档。"}

    return ParsedDocument(
        metadata=metadata,
        body=body,
    )


def test_validate_document_accepts_valid_document():
    validate_document(make_document())


def test_validate_document_accepts_crlf_body():
    document = make_document(body="---\r\n\r\n## 用途\r\n\r\n测试正文。\r\n")

    validate_document(document)


def test_validate_document_accepts_leading_blank_line():
    document = make_document(body="\n---\n\n## 用途\n\n测试正文。\n")

    validate_document(document)


def test_validate_document_accepts_leading_whitespace_lines():
    document = make_document(body="\n   \n\t\n---\n\n## 用途\n\n测试正文。\n")

    validate_document(document)


def test_validate_document_accepts_leading_blank_line_with_crlf():
    document = make_document(body="\r\n---\r\n\r\n## 用途\r\n\r\n测试正文。\r\n")

    validate_document(document)


def test_validate_document_rejects_missing_summary():
    document = make_document(metadata={})

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_unknown_metadata_field():
    document = make_document(
        metadata={
            "summary": "测试文档。",
            "title": "不允许的字段",
        }
    )

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_empty_summary():
    document = make_document(metadata={"summary": ""})

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_whitespace_summary():
    document = make_document(metadata={"summary": "   "})

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_non_string_summary():
    document = make_document(metadata={"summary": 123})

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_array_summary():
    document = make_document(metadata={"summary": ["测试"]})

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_missing_body_separator():
    document = make_document(body="## 用途\n\n测试正文。\n")

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_non_standalone_separator():
    document = make_document(body="--- 正文\n")

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_separator_with_trailing_spaces():
    document = make_document(body="---   \n\n测试正文。\n")

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_empty_body():
    document = make_document(body="")

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_separator_only():
    document = make_document(body="---\n")

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_whitespace_only_body():
    document = make_document(body="---\n   \n\t\n")

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_rejects_non_dict_metadata():
    document = make_document(metadata=["summary"])

    with pytest.raises(DocumentValidationError):
        validate_document(document)


def test_validate_document_does_not_modify_document():
    document = make_document()
    original_metadata = document.metadata
    original_body = document.body

    validate_document(document)

    assert document.metadata is original_metadata
    assert document.body == original_body
