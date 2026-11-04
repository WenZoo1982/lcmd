import warnings
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

import lcmd.cli.app as cli_app
from lcmd.cli.app import create_app
from lcmd.core.config import AppConfig
from lcmd.core.migration import (
    MigrationCleanupWarning,
    MigrationConfirmationRequired,
    MigrationError,
)
from lcmd.knowledge.loader import KnowledgeLoadError

runner = CliRunner()


@pytest.fixture
def cli_mocks(monkeypatch, tmp_path):
    """为 CLI 测试提供隔离的初始化状态和模块调用。"""
    catalog = Mock()
    catalog.platforms = (
        SimpleNamespace(name="windows", languages=("en-US", "zh-CN")),
        SimpleNamespace(name="linux", languages=("en-US", "zh-CN")),
    )
    catalog.version = "0.1.0"

    state = cli_app.AppState(
        config=AppConfig(
            knowledge_path=tmp_path / "knowledge",
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
    save = Mock()
    load = Mock(return_value=Mock(name="loaded_knowledge"))

    migrate = Mock(
        return_value=AppConfig(
            knowledge_path=tmp_path / "new-knowledge",
            platform="windows",
            language="zh-CN",
        )
    )

    monkeypatch.setattr(cli_app, "initialize_state", initialize)
    monkeypatch.setattr(cli_app, "query_document", query)
    monkeypatch.setattr(cli_app, "render_query_result", render_query)
    monkeypatch.setattr(cli_app, "search_knowledge", search)
    monkeypatch.setattr(cli_app, "render_search_results", render_search)
    monkeypatch.setattr(
        cli_app,
        "get_config_file",
        Mock(return_value=tmp_path / "config.toml"),
    )
    monkeypatch.setattr(cli_app, "save_config", save)
    monkeypatch.setattr(cli_app, "load_knowledge", load)
    monkeypatch.setattr(cli_app, "migrate_knowledge", migrate)

    return {
        "state": state,
        "initialize": initialize,
        "query": query,
        "render_query": render_query,
        "search": search,
        "render_search": render_search,
        "save": save,
        "load": load,
        "migrate": migrate,
    }


def test_help_only_lists_search_as_fixed_command():
    app = create_app()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "search" in result.output

    command_names = {command.name for command in app.registered_commands}
    assert command_names == {"search"}


def test_version_is_available(cli_mocks, monkeypatch):
    catalog = Mock()
    catalog.version = "0.1.0"

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
        Mock(return_value=catalog),
    )

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


@pytest.mark.parametrize(
    "arguments",
    [
        ["--version", "--config"],
        ["--version", "--path", "D:/KB"],
        ["--version", "--platform", "linux"],
        ["--version", "--language", "en-US"],
        ["--version", "--update"],
    ],
)
def test_version_rejects_other_root_options(arguments, cli_mocks):
    result = runner.invoke(create_app(), arguments)

    assert result.exit_code == 2
    assert "不能与配置或更新参数同时使用" in result.output
    cli_mocks["initialize"].assert_not_called()


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


@pytest.mark.parametrize("command", ["platform", "language"])
def test_platform_and_language_are_dynamic_queries(cli_mocks, command):
    result = runner.invoke(create_app(), [command])

    assert result.exit_code == 0
    cli_mocks["query"].assert_called_once_with(
        cli_mocks["state"].knowledge,
        [command],
    )


def test_dynamic_query_fails_when_knowledge_unavailable(cli_mocks):
    cli_mocks["initialize"].return_value = cli_app.AppState(
        config=cli_mocks["state"].config,
        catalog=None,
        knowledge=None,
    )

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


def test_config_shows_current_configuration(cli_mocks):
    result = runner.invoke(create_app(), ["-c"])

    assert result.exit_code == 0
    assert "知识库路径：" in result.output
    assert "当前平台：windows" in result.output
    assert "当前语言：zh-CN" in result.output
    cli_mocks["save"].assert_not_called()


@pytest.mark.parametrize("option", ["--platform", "-p"])
def test_platform_without_value_shows_available_platforms(cli_mocks, option):
    result = runner.invoke(create_app(), ["-c", option])

    assert result.exit_code == 0
    assert "当前平台：windows" in result.output
    assert "windows" in result.output
    assert "linux" in result.output
    cli_mocks["save"].assert_not_called()


@pytest.mark.parametrize("option", ["--language", "-l"])
def test_language_without_value_shows_available_languages(cli_mocks, option):
    result = runner.invoke(create_app(), ["-c", option])

    assert result.exit_code == 0
    assert "当前语言：zh-CN" in result.output
    assert "en-US" in result.output
    assert "zh-CN" in result.output
    cli_mocks["save"].assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [
        ["-c", "--platform", "linux"],
        ["-c", "-p", "linux"],
    ],
)
def test_platform_value_switches_platform(cli_mocks, arguments):
    result = runner.invoke(create_app(), arguments)

    assert result.exit_code == 0
    assert "已切换平台：linux" in result.output
    cli_mocks["load"].assert_called_once_with(
        cli_mocks["state"].catalog,
        "linux",
        "zh-CN",
    )
    cli_mocks["save"].assert_called_once()


@pytest.mark.parametrize(
    "arguments",
    [
        ["-c", "--language", "en-US"],
        ["-c", "-l", "en-US"],
    ],
)
def test_language_value_switches_language(cli_mocks, arguments):
    result = runner.invoke(create_app(), arguments)

    assert result.exit_code == 0
    assert "已切换语言：en-US" in result.output
    cli_mocks["load"].assert_called_once_with(
        cli_mocks["state"].catalog,
        "windows",
        "en-US",
    )
    cli_mocks["save"].assert_called_once()


def test_platform_and_language_can_be_switched_together(cli_mocks):
    result = runner.invoke(
        create_app(),
        ["-c", "-p", "linux", "-l", "en-US"],
    )

    assert result.exit_code == 0
    assert "已切换平台：linux" in result.output
    assert "已切换语言：en-US" in result.output
    cli_mocks["load"].assert_called_once_with(
        cli_mocks["state"].catalog,
        "linux",
        "en-US",
    )
    cli_mocks["save"].assert_called_once()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--path", "D:/KB"],
        ["--platform", "linux"],
        ["--language", "en-US"],
    ],
)
def test_configuration_options_require_config_entry(arguments, cli_mocks):
    result = runner.invoke(create_app(), arguments)

    assert result.exit_code == 2
    assert "必须配合 --config/-c" in result.output
    cli_mocks["initialize"].assert_not_called()


def test_path_migration_succeeds(cli_mocks, tmp_path):
    target_path = "D:/KB"
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        create_app(),
        ["-c", "--path", target_path],
    )

    assert result.exit_code == 0
    assert "迁移成功" in result.output

    expected_path = str(tmp_path / "new-knowledge")
    normalized_output = "".join(result.output.split())
    normalized_path = "".join(expected_path.split())

    assert normalized_path in normalized_output

    cli_mocks["migrate"].assert_called_once()
    call_args = cli_mocks["migrate"].call_args

    assert call_args.args == (config_file, target_path)
    assert callable(call_args.kwargs["progress_callback"])


def test_path_migration_requires_confirmation_when_target_exists(
    cli_mocks,
    tmp_path,
):
    target_path = "D:/KB"
    config_file = tmp_path / "config.toml"

    cli_mocks["migrate"].side_effect = [
        MigrationConfirmationRequired("目标目录已经存在"),
        AppConfig(
            knowledge_path=tmp_path / "new-knowledge",
            platform="windows",
            language="zh-CN",
        ),
    ]

    result = runner.invoke(
        create_app(),
        ["-c", "--path", target_path],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "目标目录已经存在" in result.output
    assert "迁移成功" in result.output

    assert cli_mocks["migrate"].call_count == 2
    calls = cli_mocks["migrate"].call_args_list

    assert calls[0].args == (config_file, target_path)
    assert callable(calls[0].kwargs["progress_callback"])

    assert calls[1].args == (config_file, target_path)
    assert calls[1].kwargs["overwrite"] is True
    assert callable(calls[1].kwargs["progress_callback"])


def test_path_migration_can_be_cancelled(cli_mocks, tmp_path):
    target_path = "D:/KB"
    config_file = tmp_path / "config.toml"

    cli_mocks["migrate"].side_effect = MigrationConfirmationRequired("目标目录已经存在")

    result = runner.invoke(
        create_app(),
        ["-c", "--path", target_path],
        input="n\n",
    )

    assert result.exit_code == 0
    assert cli_mocks["migrate"].call_count == 1
    call_args = cli_mocks["migrate"].call_args

    assert call_args.args == (config_file, target_path)
    assert callable(call_args.kwargs["progress_callback"])


def test_path_migration_reports_migration_error(cli_mocks):
    cli_mocks["migrate"].side_effect = MigrationError("迁移测试错误")

    result = runner.invoke(
        create_app(),
        ["-c", "--path", "D:/KB"],
    )

    assert result.exit_code == 1
    assert "迁移失败" in result.output
    assert "迁移测试错误" in result.output


def test_path_migration_displays_cleanup_warning(cli_mocks):
    def migrate_with_warning(config_file, target_path, **kwargs):
        warnings.warn(
            "旧知识库目录未能完全清理",
            MigrationCleanupWarning,
            stacklevel=2,
        )
        return AppConfig(
            knowledge_path=cli_mocks["state"].config.knowledge_path,
            platform="windows",
            language="zh-CN",
        )

    cli_mocks["migrate"].side_effect = migrate_with_warning

    result = runner.invoke(
        create_app(),
        ["-c", "--path", "D:/KB"],
    )

    assert result.exit_code == 0
    assert "迁移成功" in result.output
    assert "旧知识库目录未能完全清理" in result.output


def test_path_cannot_be_combined_with_platform_or_language(cli_mocks):
    result = runner.invoke(
        create_app(),
        ["-c", "--path", "D:/KB", "-p", "linux"],
    )

    assert result.exit_code == 2
    assert "--path 不能与 --platform 或 --language 同时使用" in result.output


def test_update_option_reports_not_implemented(cli_mocks):
    result = runner.invoke(create_app(), ["-u"])

    assert result.exit_code == 0
    assert "知识库更新功能尚未实现" in result.output
    cli_mocks["initialize"].assert_not_called()


def test_update_cannot_be_combined_with_configuration(cli_mocks):
    result = runner.invoke(create_app(), ["-u", "-c"])

    assert result.exit_code == 2
    assert "--update 不能与配置参数同时使用" in result.output


def test_platform_switch_fails_when_knowledge_unavailable(cli_mocks):
    cli_mocks["initialize"].return_value = cli_app.AppState(
        config=cli_mocks["state"].config,
        catalog=None,
        knowledge=None,
    )

    result = runner.invoke(create_app(), ["-c", "-p", "linux"])

    assert result.exit_code == 1
    assert "配置修改失败" in result.output
    cli_mocks["save"].assert_not_called()


def test_initialize_state_saves_first_valid_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    knowledge_path = tmp_path / "knowledge"
    catalog = Mock()
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
    monkeypatch.setattr(
        cli_app,
        "discover_catalog",
        Mock(return_value=catalog),
    )
    monkeypatch.setattr(
        cli_app,
        "load_knowledge",
        Mock(return_value=knowledge),
    )
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

    monkeypatch.setattr(
        cli_app,
        "load_config",
        Mock(return_value=config),
    )
    monkeypatch.setattr(
        cli_app,
        "discover_catalog",
        Mock(side_effect=KnowledgeLoadError("知识库不可用")),
    )

    state = cli_app.initialize_state(config_file)

    assert state.config == config
    assert state.catalog is None
    assert state.knowledge is None


def test_initialize_state_does_not_save_when_loading_fails(
    tmp_path,
    monkeypatch,
):
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

    result = cli_app.switch_platform(
        state,
        "linux",
        tmp_path / "config.toml",
    )

    assert result.config.platform == "linux"
    assert result.config.language == "zh-CN"
    assert result.knowledge is new_knowledge
    assert state.config.platform == "windows"
    load.assert_called_once_with(state.catalog, "linux", "zh-CN")
    save.assert_called_once_with(
        result.config,
        tmp_path / "config.toml",
    )


def test_switch_platform_does_not_save_when_loading_fails(
    tmp_path,
    monkeypatch,
):
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
        cli_app.switch_platform(
            state,
            "linux",
            tmp_path / "config.toml",
        )

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

    result = cli_app.switch_language(
        state,
        "en-US",
        tmp_path / "config.toml",
    )

    assert result.config.language == "en-US"
    assert result.config.platform == "windows"
    assert result.knowledge is new_knowledge
    assert state.config.language == "zh-CN"
    load.assert_called_once_with(state.catalog, "windows", "en-US")
    save.assert_called_once_with(
        result.config,
        tmp_path / "config.toml",
    )


def test_switch_language_does_not_save_when_loading_fails(
    tmp_path,
    monkeypatch,
):
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
        cli_app.switch_language(
            state,
            "en-US",
            tmp_path / "config.toml",
        )

    assert state.config.language == "zh-CN"
    save.assert_not_called()


def test_switch_configuration_saves_once_for_combined_change(
    tmp_path,
    monkeypatch,
):
    state = cli_app.AppState(
        config=AppConfig(
            knowledge_path=tmp_path / "kb",
            platform="windows",
            language="zh-CN",
        ),
        catalog=Mock(),
        knowledge=Mock(),
    )
    knowledge = Mock()
    load = Mock(return_value=knowledge)
    save = Mock()

    monkeypatch.setattr(cli_app, "load_knowledge", load)
    monkeypatch.setattr(cli_app, "save_config", save)

    result = cli_app.switch_configuration(
        state,
        tmp_path / "config.toml",
        platform="linux",
        language="en-US",
    )

    assert result.config.platform == "linux"
    assert result.config.language == "en-US"
    assert result.knowledge is knowledge
    load.assert_called_once_with(state.catalog, "linux", "en-US")
    save.assert_called_once_with(
        result.config,
        tmp_path / "config.toml",
    )


def test_switch_configuration_does_not_save_when_final_combination_is_invalid(
    tmp_path,
    monkeypatch,
):
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
        Mock(side_effect=KnowledgeLoadError("组合不可用")),
    )
    monkeypatch.setattr(cli_app, "save_config", save)

    with pytest.raises(KnowledgeLoadError):
        cli_app.switch_configuration(
            state,
            tmp_path / "config.toml",
            platform="linux",
            language="en-US",
        )

    assert state.config.platform == "windows"
    assert state.config.language == "zh-CN"
    save.assert_not_called()


def test_path_migration_progress_callback_is_executed(cli_mocks):
    def migrate_with_progress(
        config_file,
        target_path,
        *,
        progress_callback=None,
        **kwargs,
    ):
        assert callable(progress_callback)

        progress_callback(50, 100)
        progress_callback(100, 100)

        return AppConfig(
            knowledge_path=cli_mocks["state"].config.knowledge_path,
            platform="windows",
            language="zh-CN",
        )

    cli_mocks["migrate"].side_effect = migrate_with_progress

    result = runner.invoke(
        create_app(),
        ["-c", "--path", "D:/KB"],
    )

    assert result.exit_code == 0
    assert "迁移成功" in result.output
