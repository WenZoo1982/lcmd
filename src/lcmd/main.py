"""LCMD 命令行程序入口。"""

import json
import re
import stat
import sys
from pathlib import Path

from lcmd.cli.app import create_app
from lcmd.core.config import (
    ConfigError,
    initialize_config,
    load_config,
)
from lcmd.core.knowledge_integrity import (
    KnowledgeIntegrityError,
    verify_knowledge_distribution,
)
from lcmd.core.path_security import PathSecurityError, validate_knowledge_path

_INTERNAL_VALIDATE_CONFIG = "--internal-validate-config"
_INTERNAL_INSPECT_CONFIG = "--internal-inspect-config"
_INTERNAL_VALIDATE_KNOWLEDGE = "--internal-validate-knowledge"
_INTERNAL_INITIALIZE_CONFIG = "--internal-initialize-config"
_INTERNAL_VALIDATE_DISTRIBUTION = "--internal-validate-distribution"
_INTERNAL_VALIDATE_INSTALL_MARKER = "--internal-validate-install-marker"

def _validate_install_marker(marker_file: str, data_directory: str) -> int:
    """严格验证 LCMD 安装身份标记及其管理路径。"""
    data_dir = Path(data_directory)
    marker_path = Path(marker_file)
    expected_marker = data_dir / ".lcmd-install.json"

    try:
        data_dir_stat = data_dir.lstat()
        marker_stat = marker_path.lstat()

        if not stat.S_ISDIR(data_dir_stat.st_mode):
            raise ValueError("LCMD 数据路径不是普通目录。")

        if getattr(data_dir_stat, "st_file_attributes", 0) & 0x0400:
            raise ValueError("LCMD 数据路径不能是符号链接或重解析点。")

        if marker_path != expected_marker:
            raise ValueError("安装标记不位于预期的 LCMD 数据目录。")

        if not stat.S_ISREG(marker_stat.st_mode):
            raise ValueError("安装标记不是普通文件。")

        if getattr(marker_stat, "st_file_attributes", 0) & 0x0400:
            raise ValueError("安装标记不能是符号链接或重解析点。")

        def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"安装标记包含重复字段：{key}")
                result[key] = value
            return result

        data = json.loads(
            marker_path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )

        legacy_fields = {"product", "marker_version", "main_version"}
        current_fields = legacy_fields | {"app_dir", "knowledge_dir", "uninstall_file"}
        state_fields = current_fields | {"install_state"}

        data_fields = frozenset(data) if isinstance(data, dict) else frozenset()
        if data_fields not in {
            frozenset(legacy_fields),
            frozenset(current_fields),
            frozenset(state_fields),
        }:
            raise ValueError("安装标记字段不符合要求。")

        if data["product"] != "WenZoo.LCMD":
            raise ValueError("安装标记产品标识不匹配。")

        marker_version = data["marker_version"]
        if (
            isinstance(marker_version, bool)
            or not isinstance(marker_version, int)
            or marker_version != 1
        ):
            raise ValueError("安装标记版本不受支持。")

        main_version = data["main_version"]
        if (
            not isinstance(main_version, str)
            or re.fullmatch(r"\d+\.\d+\.\d+", main_version) is None
        ):
            raise ValueError("安装标记中的主程序版本无效。")

        if current_fields.issubset(data_fields):
            expected_paths = {
                "app_dir": data_dir / "app",
                "knowledge_dir": data_dir / "knowledge",
                "uninstall_file": data_dir / "uninstall.sh",
            }
            for field, expected_path in expected_paths.items():
                if data[field] != str(expected_path):
                    raise ValueError(f"安装标记中的管理路径不匹配：{field}")

        if "install_state" in data_fields:
            install_state = data["install_state"]
            if not isinstance(install_state, str) or install_state not in {
                "installing",
                "complete",
            }:
                raise ValueError("安装标记状态无效。")

    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(
            f"LCMD_INSTALL_MARKER=ERROR\n安装标记验证失败：{exc}",
            file=sys.stderr,
        )
        return 1

    print("LCMD_INSTALL_MARKER=OK")
    return 0


def _validate_install_distribution(
    knowledge_directory: str,
    integrity_file: str,
) -> int:
    """验证安装器使用的完整知识库发行文件。"""
    try:
        result = verify_knowledge_distribution(
            knowledge_directory,
            integrity_file,
        )
    except (KnowledgeIntegrityError, OSError, RuntimeError) as exc:
        print(
            f"LCMD_INSTALL_DISTRIBUTION=ERROR\n发行包验证失败：{exc}",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "main_version": result.main_version,
                "main_prerelease": result.main_prerelease,
                "knowledge_version": result.knowledge_version,
                "file_count": result.file_count,
            },
            ensure_ascii=False,
        )
    )
    print("LCMD_INSTALL_DISTRIBUTION=OK")
    return 0

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


def _initialize_install_config(
    knowledge_path: str,
    platform: str,
    language: str,
    config_file: str,
) -> int:
    """由安装器调用，初始化或更新 LCMD 配置。"""
    try:
        config = initialize_config(
            knowledge_path=knowledge_path,
            config_file=Path(config_file),
            platform=platform,
            language=language,
        )
    except (ConfigError, PathSecurityError, OSError) as exc:
        print(
            f"LCMD_INSTALL_CONFIG=ERROR\n配置初始化失败：{exc}",
            file=sys.stderr,
        )
        return 1

    result = {
        "status": "OK",
        "knowledge_path": str(config.knowledge_path),
        "platform": config.platform,
        "language": config.language,
    }

    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> None:
    """启动 LCMD 命令行应用。"""
    arguments = sys.argv[1:]

    internal_commands = {
        _INTERNAL_VALIDATE_CONFIG,
        _INTERNAL_INSPECT_CONFIG,
        _INTERNAL_VALIDATE_KNOWLEDGE,
        _INTERNAL_INITIALIZE_CONFIG,
        _INTERNAL_VALIDATE_DISTRIBUTION,
        _INTERNAL_VALIDATE_INSTALL_MARKER,
    }

    if arguments and arguments[0] in internal_commands:
        command = arguments[0]

        if command == _INTERNAL_VALIDATE_DISTRIBUTION:
            if (
                len(arguments) != 3
                or any(not argument.strip() for argument in arguments[1:])
            ):
                usage = (
                    "用法：lcmd --internal-validate-distribution "
                    "<知识库目录完整路径> <完整性清单文件路径>"
                )
                print(usage, file=sys.stderr)
                raise SystemExit(2)

            raise SystemExit(
                _validate_install_distribution(
                    arguments[1],
                    arguments[2],
                )
            )

        if command == _INTERNAL_VALIDATE_INSTALL_MARKER:
            if (
                len(arguments) != 3
                or any(not argument.strip() for argument in arguments[1:])
            ):
                usage = (
                    "用法：lcmd --internal-validate-install-marker "
                    "<安装标记文件路径> <LCMD 数据目录路径>"
                )
                print(usage, file=sys.stderr)
                raise SystemExit(2)

            raise SystemExit(
                _validate_install_marker(
                    arguments[1],
                    arguments[2],
                )
            )

        if command == _INTERNAL_INITIALIZE_CONFIG:
            if len(arguments) != 5 or any(not argument.strip() for argument in arguments[1:]):
                usage = (
                    "用法：lcmd.exe --internal-initialize-config "
                    "<知识库路径> <平台> <语言> <配置文件路径>"
                )
                print(usage, file=sys.stderr)
                raise SystemExit(2)

            raise SystemExit(
                _initialize_install_config(
                    arguments[1],
                    arguments[2],
                    arguments[3],
                    arguments[4],
                )
            )

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
    app(prog_name="lcmd")


if __name__ == "__main__":
    main()
