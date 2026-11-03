from lcmd.knowledge.models import KnowledgeBase, KnowledgeDocument
from lcmd.knowledge.search import search_knowledge


def make_document(
    document_id,
    category="platforms",
    platform="windows",
    tool=None,
    summary="测试摘要。",
    body="## 用途\n\n测试用途。",
):
    return KnowledgeDocument(
        id=document_id,
        category=category,
        platform=platform,
        tool=tool,
        language="zh-CN",
        summary=summary,
        body=body,
    )


def make_knowledge(*documents):
    return KnowledgeBase(
        platform="windows",
        language="zh-CN",
        documents=tuple(documents),
    )


def result_ids(results):
    return tuple(item.document.id for item in results)


def test_search_returns_empty_for_empty_keyword():
    knowledge = make_knowledge(make_document("platforms/windows/zh-CN/dir.md"))

    assert search_knowledge(knowledge, "") == ()
    assert search_knowledge(knowledge, "   ") == ()


def test_search_returns_empty_when_no_query_units():
    knowledge = make_knowledge(make_document("platforms/windows/zh-CN/dir.md"))

    assert search_knowledge(knowledge, "!!!") == ()


def test_search_matches_platform_command_name():
    document = make_document("platforms/windows/zh-CN/dir.md")
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "dir")

    assert result_ids(results) == (document.id,)


def test_search_matches_tool_name():
    document = make_document(
        "tools/git/zh-CN/git.md",
        category="tools",
        platform=None,
        tool="git",
    )
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "git")

    assert result_ids(results) == (document.id,)


def test_search_matches_nested_tool_command_path():
    document = make_document(
        "tools/docker/zh-CN/compose/up.md",
        category="tools",
        platform=None,
        tool="docker",
    )
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "compose")

    assert result_ids(results) == (document.id,)


def test_search_matches_english_case_insensitively():
    document = make_document("platforms/windows/zh-CN/dir.md")
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "DIR")

    assert result_ids(results) == (document.id,)


def test_search_uses_english_word_boundaries():
    document = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="Listing directory contents.",
        body="## 用途\n\nListing directory contents.",
    )
    knowledge = make_knowledge(document)

    assert search_knowledge(knowledge, "list") == ()
    assert result_ids(search_knowledge(knowledge, "listing")) == (document.id,)


def test_search_matches_chinese_two_character_fragments():
    document = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="管理文件和目录。",
    )
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "文件")

    assert result_ids(results) == (document.id,)


def test_search_matches_single_chinese_character():
    document = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="管理文件和目录。",
    )
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "文")

    assert result_ids(results) == (document.id,)


def test_search_matches_usage_section():
    document = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="目录操作。",
        body="## 用途\n\n显示当前目录中的文件。\n\n## 基本语法\n\n其他内容。",
    )
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "当前目录")

    assert result_ids(results) == (document.id,)


def test_search_does_not_search_other_body_sections_by_default():
    document = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="目录操作。",
        body="## 用途\n\n查看目录。\n\n## 常用示例\n\n搜索特殊内容。",
    )
    knowledge = make_knowledge(document)

    assert search_knowledge(knowledge, "特殊内容") == ()


def test_search_full_includes_other_body_sections():
    document = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="目录操作。",
        body="## 用途\n\n查看目录。\n\n## 常用示例\n\n搜索特殊内容。",
    )
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "特殊内容", full=True)

    assert result_ids(results) == (document.id,)


def test_search_uses_or_for_multiple_keywords():
    first = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="查看目录内容。",
    )
    second = make_document(
        "platforms/windows/zh-CN/copy.md",
        summary="复制文件。",
    )
    knowledge = make_knowledge(first, second)

    results = search_knowledge(knowledge, "目录 文件")

    assert set(result_ids(results)) == {first.id, second.id}


def test_search_prioritizes_name_over_summary():
    name_match = make_document(
        "platforms/windows/zh-CN/copy.md",
        summary="复制文件。",
    )
    summary_match = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="使用 copy 功能。",
    )
    knowledge = make_knowledge(summary_match, name_match)

    results = search_knowledge(knowledge, "copy")

    assert result_ids(results)[0] == name_match.id


def test_search_returns_results_in_stable_order_for_equal_scores():
    second = make_document(
        "platforms/windows/zh-CN/second.md",
        summary="相同摘要。",
    )
    first = make_document(
        "platforms/windows/zh-CN/first.md",
        summary="相同摘要。",
    )
    knowledge = make_knowledge(second, first)

    results = search_knowledge(knowledge, "相同摘要")

    assert result_ids(results) == (first.id, second.id)


def test_search_results_have_positive_scores():
    document = make_document(
        "platforms/windows/zh-CN/dir.md",
        summary="查看目录。",
    )
    knowledge = make_knowledge(document)

    results = search_knowledge(knowledge, "目录")

    assert len(results) == 1
    assert results[0].score > 0
