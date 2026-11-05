"""LCMD 命令行程序入口。"""

import sys
from pathlib import Path

from lcmd.cli.app import create_app
from lcmd.core.config import ConfigError, load_config
from lcmd.core.path_security import PathSecurityError, validate_knowledge_path

_INTERNAL_VALIDATE_CONFIG = "--internal-validate-config"


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


def main() -> None:
    """启动 LCMD 命令行应用。"""
    arguments = sys.argv[1:]

    if arguments and arguments[0] == _INTERNAL_VALIDATE_CONFIG:
        if len(arguments) != 2 or not arguments[1].strip():
            print(
                "用法：lcmd.exe --internal-validate-config <配置文件完整路径>",
                file=sys.stderr,
            )
            raise SystemExit(2)

        raise SystemExit(_validate_install_config(arguments[1]))

    app = create_app()
    app()


if __name__ == "__main__":
    main()
