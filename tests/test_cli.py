from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

import lcmd.cli.app as cli_app
from lcmd.cli.app import create_app
from lcmd.core.config import AppConfig
from lcmd.knowledge.loader import KnowledgeLoadError

runner = CliRunner()


@pytest.fixture
def cli_mocks(monkeypatch):
    """为 CLI 测试提供隔离的初始化状态和模块调用。"""
    catalog = Mock()
    catalog.platforms = (
        SimpleNamespace(
            name="windows",
            languages=("en-US", "zh-CN"),
        ),
        SimpleNamespace(
            name="linux",
            languages=("en-US", "zh-CN"),
        ),
    )
    catalog.version = "0.1.0"

    state = cli_app.AppState(
        config=AppConfig(
            knowledge_path=None,
            platform="windows",
            language="zh-CN",
        ),
        catalog=catalog,
        knowledge=Mock(),
    )

    initialize = Mock(return_value=state)
    query = Mock(return_value=Mock(name="query_result"))
    render_query = Mock()
    search = Mock(return_value=(Mock(name="search_result"),))
    render_search = Mock()

    monkeypatch.setattr(cli_app, "initialize_state", initialize)
    monkeypatch.setattr(cli_app, "query_document", query)
    monkeypatch.setattr(cli_app, "render_query_result", render_query)
    monkeypatch.setattr(cli_app, "search_knowledge", search)
    monkeypatch.setattr(cli_app, "render_search_results", render_search)

    return {
        "state": state,
        "initialize": initialize,
        "query": query,
        "render_query": render_query,
        "search": search,
        "render_search": render_search,
    }


def test_help_is_available():
    result = runner.invoke(create_app(), ["--help"])

    assert result.exit_code == 0
    assert "search" in result.output
    assert "platform" in result.output
    assert "language" in result.output


def test_version_is_available(cli_mocks, monkeypatch):
    catalog = Mock()
    catalog.version = "0.1.0"

    monkeypatch.setattr(
        cli_app, "get_config_file", Mock(return_value=Mock(is_file=Mock(return_value=False)))
    )
    monkeypatch.setattr(cli_app, "get_default_knowledge_path", Mock(return_value=Mock()))
    monkeypatch.setattr(cli_app, "discover_catalog", Mock(return_value=catalog))

    result = runner.invoke(create_app(), ["--version"])

    assert result.exit_code == 0
    assert "LCMD：" in result.output
    assert "知识库：0.1.0" in result.output
    cli_mocks["initialize"].assert_not_called()


def test_version_shows_unavailable_knowledge_base(monkeypatch):
    monkeypatch.setattr(
        cli_app,
        "get_config_file",
        Mock(return_value=Mock(is_file=Mock(return_value=False))),
    )
    monkeypatch.setattr(
        cli_app,
        "get_default_knowledge_path",
        Mock(return_value=Mock()),
    )
    monkeypatch.setattr(
        cli_app,
        "discover_catalog",
        Mock(side_effect=KnowledgeLoadError("知识库不可用")),
    )

    result = runner.invoke(create_app(), ["--version"])

    assert result.exit_code == 0
    assert "LCMD：" in result.output
    assert "知识库：不可用" in result.output


def test_dynamic_single_argument_is_queried(cli_mocks):
    result = runner.invoke(create_app(), ["ls"])

    assert result.exit_code == 0
    cli_mocks["query"].assert_called_once_with(
        cli_mocks["state"].knowledge,
        ["ls"],
    )
    cli_mocks["render_query"].assert_called_once()


def test_dynamic_multi_argument_is_queried(cli_mocks):
    result = runner.invoke(create_app(), ["git", "init"])

    assert result.exit_code == 0
    cli_mocks["query"].assert_called_once_with(
        cli_mocks["state"].knowledge,
        ["git", "init"],
    )


def test_dynamic_nested_arguments_are_queried(cli_mocks):
    result = runner.invoke(create_app(), ["docker", "compose", "up"])

    assert result.exit_code == 0
    cli_mocks["query"].assert_called_once_with(
        cli_mocks["state"].knowledge,
        ["docker", "compose", "up"],
    )


def test_dynamic_query_fails_when_knowledge_unavailable(cli_mocks):
    unavailable_state = cli_app.AppState(
        config=cli_mocks["state"].config,
        catalog=None,
        knowledge=None,
    )
    cli_mocks["initialize"].return_value = unavailable_state

    result = runner.invoke(create_app(), ["ls"])

    assert result.exit_code == 1
    assert "知识库不可用" in result.output
    cli_mocks["query"].assert_not_called()


def test_search_accepts_keyword(cli_mocks):
    result = runner.invoke(create_app(), ["search", "文件"])

    assert result.exit_code == 0
    cli_mocks["search"].assert_called_once_with(
        cli_mocks["state"].knowledge,
        "文件",
        full=False,
    )
    cli_mocks["render_search"].assert_called_once()


def test_search_accepts_multiple_keyword_words(cli_mocks):
    result = runner.invoke(create_app(), ["search", "文件", "目录"])

    assert result.exit_code == 0
    cli_mocks["search"].assert_called_once_with(
        cli_mocks["state"].knowledge,
        "文件 目录",
        full=False,
    )


def test_search_accepts_full_option(cli_mocks):
    result = runner.invoke(create_app(), ["search", "文件", "--full"])

    assert result.exit_code == 0
    cli_mocks["search"].assert_called_once_with(
        cli_mocks["state"].knowledge,
        "文件",
        full=True,
    )


def test_search_requires_keyword(cli_mocks):
    result = runner.invoke(create_app(), ["search"])

    assert result.exit_code != 0
    assert "Missing argument" in result.output
    cli_mocks["search"].assert_not_called()
    cli_mocks["query"].assert_not_called()


def test_search_fails_when_knowledge_unavailable(cli_mocks):
    cli_mocks["initialize"].return_value = cli_app.AppState(
        config=cli_mocks["state"].config,
        catalog=None,
        knowledge=None,
    )

    result = runner.invoke(create_app(), ["search", "文件"])

    assert result.exit_code == 1
    assert "知识库不可用" in result.output
    cli_mocks["search"].assert_not_called()


def test_platform_command_is_recognized(cli_mocks):
    result = runner.invoke(create_app(), ["platform"])

    assert result.exit_code == 0
    assert "当前平台：windows" in result.output
    assert "windows" in result.output
    cli_mocks["query"].assert_not_called()


def test_language_command_is_recognized(cli_mocks):
    result = runner.invoke(create_app(), ["language"])

    assert result.exit_code == 0
    assert "当前语言：zh-CN" in result.output
    assert "zh-CN" in result.output
    cli_mocks["query"].assert_not_called()


def test_platform_is_displayed_when_knowledge_unavailable(cli_mocks):
    cli_mocks["initialize"].return_value = cli_app.AppState(
        config=cli_mocks["state"].config,
        catalog=None,
        knowledge=None,
    )

    result = runner.invoke(create_app(), ["platform"])

    assert result.exit_code == 0
    assert "当前平台：windows" in result.output
    assert "知识库不可用" in result.output


def test_language_is_displayed_when_knowledge_unavailable(cli_mocks):
    cli_mocks["initialize"].return_value = cli_app.AppState(
        config=cli_mocks["state"].config,
        catalog=None,
        knowledge=None,
    )

    result = runner.invoke(create_app(), ["language"])

    assert result.exit_code == 0
    assert "当前语言：zh-CN" in result.output
    assert "知识库不可用" in result.output


def test_platform_rejects_extra_arguments(cli_mocks):
    result = runner.invoke(create_app(), ["platform", "linux", "windows"])

    assert result.exit_code != 0
    assert "Got unexpected extra argument" in result.output
    cli_mocks["query"].assert_not_called()


def test_language_rejects_extra_arguments(cli_mocks):
    result = runner.invoke(create_app(), ["language", "en-US", "zh-CN"])

    assert result.exit_code != 0
    assert "Got unexpected extra argument" in result.output
    cli_mocks["query"].assert_not_called()


def test_platform_switch_fails_when_knowledge_unavailable(cli_mocks, monkeypatch):
    cli_mocks["initialize"].return_value = cli_app.AppState(
        config=cli_mocks["state"].config,
        catalog=None,
        knowledge=None,
    )
    save = Mock()
    monkeypatch.setattr(cli_app, "save_config", save)

    result = runner.invoke(create_app(), ["platform", "linux"])

    assert result.exit_code == 1
    assert "平台切换失败" in result.output
    save.assert_not_called()


def test_language_switch_fails_when_knowledge_unavailable(cli_mocks, monkeypatch):
    cli_mocks["initialize"].return_value = cli_app.AppState(
        config=cli_mocks["state"].config,
        catalog=None,
        knowledge=None,
    )
    save = Mock()
    monkeypatch.setattr(cli_app, "save_config", save)

    result = runner.invoke(create_app(), ["language", "en-US"])

    assert result.exit_code == 1
    assert "语言切换失败" in result.output
    save.assert_not_called()


def test_initialize_state_saves_first_valid_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    knowledge_path = tmp_path / "knowledge"
    catalog = Mock()
    catalog.version = "0.1.0"
    knowledge = Mock()

    discover = Mock(return_value=catalog)
    load = Mock(return_value=knowledge)
    save = Mock()

    monkeypatch.setattr(cli_app, "discover_catalog", discover)
    monkeypatch.setattr(cli_app, "load_knowledge", load)
    monkeypatch.setattr(cli_app, "save_config", save)

    state = cli_app.initialize_state(config_file, knowledge_path)

    assert state.config.knowledge_path == knowledge_path
    assert state.config.platform == "windows"
    assert state.config.language == "zh-CN"
    assert state.catalog is catalog
    assert state.knowledge is knowledge
    discover.assert_called_once_with(knowledge_path)
    load.assert_called_once_with(catalog, "windows", "zh-CN")
    save.assert_called_once_with(state.config, config_file)


def test_initialize_state_reads_existing_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    config_file.touch()

    config = AppConfig(
        knowledge_path=tmp_path / "custom-kb",
        platform="linux",
        language="en-US",
    )
    catalog = Mock()
    knowledge = Mock()

    load_config = Mock(return_value=config)
    save_config = Mock()

    monkeypatch.setattr(cli_app, "load_config", load_config)
    monkeypatch.setattr(cli_app, "discover_catalog", Mock(return_value=catalog))
    monkeypatch.setattr(cli_app, "load_knowledge", Mock(return_value=knowledge))
    monkeypatch.setattr(cli_app, "save_config", save_config)

    state = cli_app.initialize_state(config_file)

    assert state.config == config
    load_config.assert_called_once_with(config_file)
    save_config.assert_not_called()


def test_initialize_state_returns_config_when_knowledge_unavailable(
    tmp_path,
    monkeypatch,
):
    config_file = tmp_path / "config.toml"
    config_file.touch()
    config = AppConfig(
        knowledge_path=tmp_path / "missing-kb",
        platform="linux",
        language="en-US",
    )

    monkeypatch.setattr(cli_app, "load_config", Mock(return_value=config))
    monkeypatch.setattr(
        cli_app,
        "discover_catalog",
        Mock(side_effect=KnowledgeLoadError("知识库不可用")),
    )

    state = cli_app.initialize_state(config_file)

    assert state.config == config
    assert state.catalog is None
    assert state.knowledge is None


def test_initialize_state_does_not_save_when_loading_fails(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    knowledge_path = tmp_path / "missing-kb"

    save_config = Mock()

    monkeypatch.setattr(
        cli_app,
        "discover_catalog",
        Mock(side_effect=KnowledgeLoadError("知识库不可用")),
    )
    monkeypatch.setattr(cli_app, "save_config", save_config)

    state = cli_app.initialize_state(config_file, knowledge_path)

    assert state.catalog is None
    assert state.knowledge is None
    save_config.assert_not_called()


def test_switch_platform_saves_after_success(tmp_path, monkeypatch):
    state = cli_app.AppState(
        config=AppConfig(
            knowledge_path=tmp_path / "kb",
            platform="windows",
            language="zh-CN",
        ),
        catalog=Mock(),
        knowledge=Mock(),
    )
    new_knowledge = Mock()
    load = Mock(return_value=new_knowledge)
    save = Mock()

    monkeypatch.setattr(cli_app, "load_knowledge", load)
    monkeypatch.setattr(cli_app, "save_config", save)

    result = cli_app.switch_platform(state, "linux", tmp_path / "config.toml")

    assert result.config.platform == "linux"
    assert result.config.language == "zh-CN"
    assert result.knowledge is new_knowledge
    assert state.config.platform == "windows"
    load.assert_called_once_with(state.catalog, "linux", "zh-CN")
    save.assert_called_once_with(result.config, tmp_path / "config.toml")


def test_switch_platform_does_not_save_when_loading_fails(tmp_path, monkeypatch):
    state = cli_app.AppState(
        config=AppConfig(
            knowledge_path=tmp_path / "kb",
            platform="windows",
            language="zh-CN",
        ),
        catalog=Mock(),
        knowledge=Mock(),
    )
    save = Mock()

    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        Mock(side_effect=KnowledgeLoadError("平台不可用")),
    )
    monkeypatch.setattr(cli_app, "save_config", save)

    with pytest.raises(KnowledgeLoadError):
        cli_app.switch_platform(state, "linux", tmp_path / "config.toml")

    assert state.config.platform == "windows"
    save.assert_not_called()


def test_switch_language_saves_after_success(tmp_path, monkeypatch):
    state = cli_app.AppState(
        config=AppConfig(
            knowledge_path=tmp_path / "kb",
            platform="windows",
            language="zh-CN",
        ),
        catalog=Mock(),
        knowledge=Mock(),
    )
    new_knowledge = Mock()
    load = Mock(return_value=new_knowledge)
    save = Mock()

    monkeypatch.setattr(cli_app, "load_knowledge", load)
    monkeypatch.setattr(cli_app, "save_config", save)

    result = cli_app.switch_language(state, "en-US", tmp_path / "config.toml")

    assert result.config.language == "en-US"
    assert result.config.platform == "windows"
    assert result.knowledge is new_knowledge
    assert state.config.language == "zh-CN"
    load.assert_called_once_with(state.catalog, "windows", "en-US")
    save.assert_called_once_with(result.config, tmp_path / "config.toml")


def test_switch_language_does_not_save_when_loading_fails(tmp_path, monkeypatch):
    state = cli_app.AppState(
        config=AppConfig(
            knowledge_path=tmp_path / "kb",
            platform="windows",
            language="zh-CN",
        ),
        catalog=Mock(),
        knowledge=Mock(),
    )
    save = Mock()

    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        Mock(side_effect=KnowledgeLoadError("语言不可用")),
    )
    monkeypatch.setattr(cli_app, "save_config", save)

    with pytest.raises(KnowledgeLoadError):
        cli_app.switch_language(state, "en-US", tmp_path / "config.toml")

    assert state.config.language == "zh-CN"
    save.assert_not_called()
