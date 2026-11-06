
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

import lcmd.cli.help as help_module
from lcmd.cli.app import create_app

runner = CliRunner()


@pytest.mark.parametrize(
    ("language_id", "expected"),
    [
        (0x0804, "zh"),
        (0x0409, "en"),
        (0x0000, "en"),
    ],
)
def test_get_help_language_on_windows(
    monkeypatch,
    language_id,
    expected,
):
    monkeypatch.setattr(help_module.sys, "platform", "win32")
    monkeypatch.setattr(
        help_module.ctypes,
        "windll",
        SimpleNamespace(
            kernel32=SimpleNamespace(
                GetUserDefaultUILanguage=lambda: language_id,
            )
        ),
        raising=False,
    )

    getlocale = Mock(return_value=("en_US", None))
    monkeypatch.setattr(help_module.locale, "getlocale", getlocale)

    assert help_module.get_help_language() == expected

    if language_id:
        getlocale.assert_not_called()


def test_get_help_language_falls_back_to_locale_on_windows(
    monkeypatch,
):
    monkeypatch.setattr(help_module.sys, "platform", "win32")
    monkeypatch.setattr(
        help_module.ctypes,
        "windll",
        SimpleNamespace(
            kernel32=SimpleNamespace(
                GetUserDefaultUILanguage=Mock(side_effect=OSError)
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(
        help_module.locale,
        "getlocale",
        lambda category: ("zh_CN", None),
    )

    assert help_module.get_help_language() == "zh"


@pytest.mark.parametrize(
    ("locale_name", "expected"),
    [
        ("zh_CN", "zh"),
        ("zh-TW", "zh"),
        ("Chinese_China", "zh"),
        ("en_US", "en"),
        ("fr_FR", "en"),
    ],
)
def test_get_help_language_from_locale(
    monkeypatch,
    locale_name,
    expected,
):
    monkeypatch.setattr(help_module.sys, "platform", "linux")
    monkeypatch.setattr(
        help_module.locale,
        "getlocale",
        lambda category: (locale_name, None),
    )

    assert help_module.get_help_language() == expected


def test_get_help_language_defaults_to_english_when_locale_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(help_module.sys, "platform", "linux")
    monkeypatch.setattr(
        help_module.locale,
        "getlocale",
        lambda category: (None, None),
    )

    assert help_module.get_help_language() == "en"


def test_get_help_language_continues_after_locale_error(
    monkeypatch,
):
    monkeypatch.setattr(help_module.sys, "platform", "linux")

    messages_category = getattr(
        help_module.locale,
        "LC_MESSAGES",
        None,
    )

    def getlocale(category):
        if category == messages_category and messages_category is not None:
            raise ValueError("locale unavailable")

        return ("zh_CN", None)

    monkeypatch.setattr(help_module.locale, "getlocale", getlocale)

    assert help_module.get_help_language() == "zh"

@pytest.mark.parametrize(
    ("language", "expected", "unexpected"),
    [
        ("zh", "多平台命令速查与学习工具", "Multi-platform Command Reference"),
        ("en", "Multi-platform Command Reference", "多平台命令速查与学习工具"),
    ],
)
def test_main_help_uses_selected_language(
    monkeypatch,
    language,
    expected,
    unexpected,
):
    monkeypatch.setattr(
        help_module,
        "get_help_language",
        lambda: language,
    )

    result = runner.invoke(create_app(), ["--help"])

    assert result.exit_code == 0
    assert expected in result.output
    assert unexpected not in result.output
    assert "lcmd search --help" in result.output
    assert "--path" in result.output


@pytest.mark.parametrize(
    ("language", "expected", "unexpected"),
    [
        ("zh", "搜索知识库", "Search the Knowledge Base"),
        ("en", "Search the Knowledge Base", "搜索知识库"),
    ],
)
def test_search_help_uses_selected_language(
    monkeypatch,
    language,
    expected,
    unexpected,
):
    monkeypatch.setattr(
        help_module,
        "get_help_language",
        lambda: language,
    )

    result = runner.invoke(
        create_app(),
        ["search", "--help"],
    )

    assert result.exit_code == 0
    assert expected in result.output
    assert unexpected not in result.output
    assert "--full" in result.output
    assert "lcmd search" in result.output


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("zh", "--path 不能与 --platform 或 --language 同时使用。"),
        ("en", "--path cannot be used with --platform or --language."),
    ],
)
def test_main_help_documents_path_exclusivity(
    monkeypatch,
    language,
    expected,
):
    monkeypatch.setattr(
        help_module,
        "get_help_language",
        lambda: language,
    )

    result = runner.invoke(create_app(), ["--help"])

    assert result.exit_code == 0
    assert expected in result.output
