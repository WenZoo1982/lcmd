from lcmd.knowledge.models import KnowledgeBase, KnowledgeDocument
from lcmd.knowledge.query import query_document


def make_platform_document(command):
    return KnowledgeDocument(
        id=f"platforms/windows/zh-CN/{command}.md",
        category="platforms",
        platform="windows",
        tool=None,
        language="zh-CN",
        summary=f"{command} 平台命令。",
        body="测试正文。",
    )


def make_tool_document(tool, path):
    return KnowledgeDocument(
        id=f"tools/{tool}/zh-CN/{path}",
        category="tools",
        platform=None,
        tool=tool,
        language="zh-CN",
        summary=f"{tool} 工具文档。",
        body="测试正文。",
    )


def make_knowledge(*documents):
    return KnowledgeBase(
        platform="windows",
        language="zh-CN",
        documents=tuple(documents),
    )


def test_query_document_returns_empty_result_without_arguments():
    knowledge = make_knowledge(make_platform_document("dir"))

    result = query_document(knowledge, ())

    assert result.documents == ()
    assert result.children == ()


def test_query_document_finds_platform_command():
    document = make_platform_document("dir")
    knowledge = make_knowledge(document)

    result = query_document(knowledge, ("dir",))

    assert result.documents == (document,)
    assert result.children == ()


def test_query_document_matches_command_case_insensitively():
    document = make_platform_document("dir")
    knowledge = make_knowledge(document)

    result = query_document(knowledge, ("DIR",))

    assert result.documents == (document,)


def test_query_document_finds_tool_entry():
    entry = make_tool_document("git", "git.md")
    knowledge = make_knowledge(
        entry,
        make_tool_document("git", "init.md"),
        make_tool_document("git", "remote/add.md"),
    )

    result = query_document(knowledge, ("git",))

    assert result.documents == (entry,)
    assert result.children == ("init", "remote")


def test_query_document_returns_single_document_without_tool_entry():
    document = make_tool_document("git", "init.md")
    knowledge = make_knowledge(document)

    result = query_document(knowledge, ("git",))

    assert result.documents == (document,)
    assert result.children == ()


def test_query_document_lists_all_documents_without_tool_entry():
    first = make_tool_document("git", "init.md")
    second = make_tool_document("git", "status.md")
    third = make_tool_document("git", "remote/add.md")

    knowledge = make_knowledge(second, third, first)

    result = query_document(knowledge, ("git",))

    assert result.documents == (first, third, second)
    assert result.children == ()


def test_query_document_finds_tool_subcommand():
    document = make_tool_document("git", "init.md")
    knowledge = make_knowledge(
        make_tool_document("git", "git.md"),
        document,
    )

    result = query_document(knowledge, ("git", "init"))

    assert result.documents == (document,)
    assert result.children == ()


def test_query_document_finds_nested_tool_subcommand():
    document = make_tool_document("docker", "compose/up.md")
    knowledge = make_knowledge(
        make_tool_document("docker", "docker.md"),
        document,
    )

    result = query_document(knowledge, ("docker", "compose", "up"))

    assert result.documents == (document,)
    assert result.children == ()


def test_query_document_returns_children_when_directory_has_no_entry():
    child = make_tool_document("git", "remote/add.md")
    knowledge = make_knowledge(
        make_tool_document("git", "git.md"),
        child,
    )

    result = query_document(knowledge, ("git", "remote"))

    assert result.documents == ()
    assert result.children == ("add",)


def test_query_document_returns_document_and_children_together():
    document = make_tool_document("git", "remote.md")
    child = make_tool_document("git", "remote/add.md")

    knowledge = make_knowledge(
        make_tool_document("git", "git.md"),
        document,
        child,
    )

    result = query_document(knowledge, ("git", "remote"))

    assert result.documents == (document,)
    assert result.children == ("add",)


def test_query_document_returns_platform_command_and_same_named_tool():
    platform_document = make_platform_document("git")
    tool_document = make_tool_document("git", "git.md")

    knowledge = make_knowledge(
        platform_document,
        tool_document,
    )

    result = query_document(knowledge, ("git",))

    assert result.documents == (
        platform_document,
        tool_document,
    )


def test_query_document_matches_tool_name_case_insensitively():
    document = make_tool_document("git", "init.md")
    knowledge = make_knowledge(document)

    result = query_document(knowledge, ("GIT",))

    assert result.documents == (document,)


def test_query_document_matches_subcommand_case_insensitively():
    document = make_tool_document("docker", "compose/up.md")
    knowledge = make_knowledge(document)

    result = query_document(
        knowledge,
        ("DOCKER", "COMPOSE", "UP"),
    )

    assert result.documents == (document,)


def test_query_document_returns_empty_result_for_unknown_command():
    knowledge = make_knowledge(
        make_platform_document("dir"),
        make_tool_document("git", "git.md"),
    )

    result = query_document(knowledge, ("unknown",))

    assert result.documents == ()
    assert result.children == ()


def test_query_document_returns_empty_result_for_unknown_subcommand():
    knowledge = make_knowledge(
        make_tool_document("git", "git.md"),
        make_tool_document("git", "init.md"),
    )

    result = query_document(knowledge, ("git", "unknown"))

    assert result.documents == ()
    assert result.children == ()
