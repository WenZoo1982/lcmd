"""LCMD 命令行程序入口。"""

import json
import sys
from pathlib import Path

from lcmd.cli.app import create_app
from lcmd.core.config import ConfigError, load_config
from lcmd.core.path_security import PathSecurityError, validate_knowledge_path

_INTERNAL_VALIDATE_CONFIG = "--internal-validate-config"
_INTERNAL_INSPECT_CONFIG = "--internal-inspect-config"
_INTERNAL_VALIDATE_KNOWLEDGE = "--internal-validate-knowledge"


def _validate_install_config(config_file: str) -> int:
    """只读验证安装配置及其知识库路径。"""
    try:
        config = load_config(Path(config_file))
        validate_knowledge_path(config.knowledge_path)
    except (ConfigError, PathSecurityError, OSError) as exc:
        print(
            f"LCMD_INSTALL_VALIDATION=ERROR\n验证失败：{exc}",
            file=sys.stderr,
        )
        return 1

    print("LCMD_INSTALL_VALIDATION=OK")
    return 0


def _inspect_install_config(config_file: str) -> int:
    """只读读取并输出安装配置中的知识库路径。"""
    try:
        config = load_config(Path(config_file))
        knowledge_path = Path(config.knowledge_path).resolve()
    except (ConfigError, OSError, RuntimeError) as exc:
        print(
            f"LCMD_INSTALL_CONFIG=ERROR\n配置读取失败：{exc}",
            file=sys.stderr,
        )
        return 1

    result = {
        "status": "OK",
        "knowledge_path": str(knowledge_path),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _validate_install_knowledge(knowledge_path: str) -> int:
    """只读验证指定知识库目录。"""
    try:
        validate_knowledge_path(Path(knowledge_path))
    except (PathSecurityError, OSError) as exc:
        print(
            f"LCMD_INSTALL_VALIDATION=ERROR\n验证失败：{exc}",
            file=sys.stderr,
        )
        return 1

    print("LCMD_INSTALL_VALIDATION=OK")
    return 0


def main() -> None:
    """启动 LCMD 命令行应用。"""
    arguments = sys.argv[1:]

    internal_commands = {
        _INTERNAL_VALIDATE_CONFIG,
        _INTERNAL_INSPECT_CONFIG,
        _INTERNAL_VALIDATE_KNOWLEDGE,
    }

    if arguments and arguments[0] in internal_commands:
        command = arguments[0]

        if len(arguments) != 2 or not arguments[1].strip():
            if command == _INTERNAL_VALIDATE_KNOWLEDGE:
                usage = "用法：lcmd.exe --internal-validate-knowledge <知识库目录完整路径>"
            elif command == _INTERNAL_INSPECT_CONFIG:
                usage = "用法：lcmd.exe --internal-inspect-config <配置文件完整路径>"
            else:
                usage = "用法：lcmd.exe --internal-validate-config <配置文件完整路径>"

            print(usage, file=sys.stderr)
            raise SystemExit(2)

        if command == _INTERNAL_VALIDATE_CONFIG:
            raise SystemExit(_validate_install_config(arguments[1]))

        if command == _INTERNAL_INSPECT_CONFIG:
            raise SystemExit(_inspect_install_config(arguments[1]))

        raise SystemExit(_validate_install_knowledge(arguments[1]))

    app = create_app()
    app()


if __name__ == "__main__":
    main()
