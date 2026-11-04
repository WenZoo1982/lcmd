
from unittest.mock import ANY, Mock

import pytest
from typer.testing import CliRunner

import lcmd.cli.app as cli_app
from lcmd.core.config import AppConfig
from lcmd.core.installer import (
    InstallerError,
    KnowledgeDestinationState,
)

runner = CliRunner()


@pytest.fixture
def installer_mocks(monkeypatch, tmp_path):
    """隔离安装器 CLI 调用。"""
    knowledge_path = tmp_path / "knowledge"

    inspect = Mock(return_value=KnowledgeDestinationState.MISSING)
    deploy = Mock(return_value=knowledge_path)
    initialize = Mock(
        return_value=AppConfig(
            knowledge_path=knowledge_path,
            platform="windows",
            language="zh-CN",
        )
    )

    monkeypatch.setattr(
        cli_app,
        "check_installer_destination",
        inspect,
    )
    monkeypatch.setattr(
        cli_app,
        "deploy_installer_knowledge",
        deploy,
    )
    monkeypatch.setattr(
        cli_app,
        "initialize_installer_config",
        initialize,
    )

    return {
        "knowledge_path": knowledge_path,
        "inspect": inspect,
        "deploy": deploy,
        "initialize": initialize,
    }


@pytest.mark.parametrize(
    ("state", "expected_exit_code", "expected_message"),
    [
        (
            KnowledgeDestinationState.MISSING,
            0,
            "可以直接部署",
        ),
        (
            KnowledgeDestinationState.EMPTY,
            0,
            "可以直接部署",
        ),
        (
            KnowledgeDestinationState.VALID,
            10,
            "需要确认替换",
        ),
        (
            KnowledgeDestinationState.INVALID,
            11,
            "需要确认替换",
        ),
    ],
)
def test_installer_check_destination_states(
    installer_mocks,
    monkeypatch,
    state,
    expected_exit_code,
    expected_message,
):
    installer_mocks["inspect"].return_value = state

    result = runner.invoke(
        cli_app.create_app(),
        ["--installer-check"],
    )

    assert result.exit_code == expected_exit_code
    assert expected_message in result.output
    installer_mocks["inspect"].assert_called_once_with()
    installer_mocks["deploy"].assert_not_called()
    installer_mocks["initialize"].assert_not_called()


def test_installer_check_handles_inspection_error(installer_mocks):
    installer_mocks["inspect"].side_effect = InstallerError("目标目录不可访问")

    result = runner.invoke(
        cli_app.create_app(),
        ["--installer-check"],
    )

    assert result.exit_code == 1
    assert "知识库目录检查失败" in result.output
    installer_mocks["deploy"].assert_not_called()
    installer_mocks["initialize"].assert_not_called()


def test_installer_deploy_success(installer_mocks):
    result = runner.invoke(
        cli_app.create_app(),
        [
            "--installer-deploy",
            "--installer-source",
            "D:/staging/knowledge",
            "--installer-integrity",
            "D:/staging/knowledge-integrity.json",
        ],
    )

    assert result.exit_code == 0
    assert "知识库部署及配置初始化成功" in result.output

    installer_mocks["deploy"].assert_called_once_with(
        "D:/staging/knowledge",
        "D:/staging/knowledge-integrity.json",
        replace_existing=False,
        progress_callback=ANY,
    )

    installer_mocks["initialize"].assert_called_once_with(
        str(installer_mocks["knowledge_path"]),
    )


def test_installer_deploy_with_replace_authorization(installer_mocks):
    result = runner.invoke(
        cli_app.create_app(),
        [
            "--installer-deploy",
            "--installer-source",
            "D:/staging/knowledge",
            "--installer-integrity",
            "D:/staging/knowledge-integrity.json",
            "--installer-replace",
        ],
    )

    assert result.exit_code == 0

    installer_mocks["deploy"].assert_called_once_with(
        "D:/staging/knowledge",
        "D:/staging/knowledge-integrity.json",
        replace_existing=True,
        progress_callback=ANY,
    )

    installer_mocks["initialize"].assert_called_once_with(
        str(installer_mocks["knowledge_path"]),
    )


def test_installer_deploy_failure_does_not_initialize_config(
    installer_mocks,
):
    installer_mocks["deploy"].side_effect = InstallerError("知识库完整性验证失败")

    result = runner.invoke(
        cli_app.create_app(),
        [
            "--installer-deploy",
            "--installer-source",
            "D:/staging/knowledge",
            "--installer-integrity",
            "D:/staging/knowledge-integrity.json",
        ],
    )

    assert result.exit_code == 1
    assert "知识库部署失败" in result.output
    installer_mocks["initialize"].assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--installer-check", "--installer-deploy"],
        ["--installer-replace"],
        ["--installer-deploy"],
        [
            "--installer-deploy",
            "--installer-source",
            "D:/staging/knowledge",
        ],
        [
            "--installer-deploy",
            "--installer-source",
            "D:/staging/knowledge",
            "--installer-integrity",
            "D:/staging/integrity.json",
            "--installer-check",
        ],
        [
            "--installer-check",
            "--version",
        ],
        [
            "--installer-deploy",
            "--installer-source",
            "D:/staging/knowledge",
            "--installer-integrity",
            "D:/staging/integrity.json",
            "--config",
        ],
    ],
)
def test_installer_rejects_invalid_argument_combinations(
    installer_mocks,
    arguments,
):
    result = runner.invoke(
        cli_app.create_app(),
        arguments,
    )

    assert result.exit_code == 2
    assert "安装器参数组合无效" in result.output
    installer_mocks["inspect"].assert_not_called()
    installer_mocks["deploy"].assert_not_called()
    installer_mocks["initialize"].assert_not_called()
