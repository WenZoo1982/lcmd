from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

from lcmd.core.paths import get_config_file


class PathSecurityError(ValueError):
    """知识库路径不符合安全要求。"""


# Windows FILE_ATTRIBUTE_REPARSE_POINT。
# 用于识别符号链接、目录联接等重解析点。
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def _get_install_dir() -> Path:
    """获取 LCMD 程序安装目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    module_path = Path(__file__).resolve()

    # 开发环境：通过 pyproject.toml 定位项目根目录。
    for parent in module_path.parents:
        if (parent / "pyproject.toml").is_file():
            return parent

    # 普通 Python 安装环境：使用包所在目录。
    return module_path.parent.parent


def _get_protected_paths() -> tuple[Path, ...]:
    """获取禁止用作知识库位置的系统和程序目录。"""
    protected = [
        get_config_file(),
        _get_install_dir(),
    ]

    if os.name == "nt":
        windows_dir = os.environ.get("WINDIR")
        program_files = os.environ.get("ProgramFiles")
        program_files_x86 = os.environ.get("ProgramFiles(x86)")
        program_data = os.environ.get("ProgramData")

        for value in (
            windows_dir,
            program_files,
            program_files_x86,
            program_data,
        ):
            if value:
                protected.append(Path(value))

    return tuple(protected)


def normalize_path(path: str | os.PathLike[str]) -> Path:
    """展开并规范化用户输入路径，返回绝对路径。"""
    try:
        raw_path = os.fspath(path)

        if not isinstance(raw_path, str) or not raw_path.strip():
            raise PathSecurityError("路径不能为空。")

        if "\x00" in raw_path:
            raise PathSecurityError("路径包含无效字符。")

        normalized = Path(raw_path).expanduser()

        if not normalized.is_absolute():
            normalized = Path.cwd() / normalized

        return normalized.resolve(strict=False)

    except PathSecurityError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise PathSecurityError("路径无法解析或访问。") from exc


def _is_filesystem_root(path: Path) -> bool:
    """检查路径是否为文件系统根目录。"""
    return bool(path.anchor) and path == Path(path.anchor)


def _is_within(path: Path, parent: Path) -> bool:
    """检查 path 是否等于 parent 或位于 parent 内部。"""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _paths_overlap(first: Path, second: Path) -> bool:
    """检查两个路径是否相同，或其中一个包含另一个。"""
    return _is_within(first, second) or _is_within(second, first)


def _check_reparse_points(path: Path) -> None:
    """检查路径现有各级组件，拒绝符号链接和重解析点。"""
    components = [*reversed(path.parents), path]

    for component in components:
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PathSecurityError("路径无法访问或读取。") from exc

        attributes = getattr(metadata, "st_file_attributes", 0)

        if component.is_symlink() or attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise PathSecurityError(f"路径中不允许存在符号链接或目录联接：{component}")


def _validate_protected_path(
    path: Path,
    protected_paths: Iterable[str | os.PathLike[str]] | None = None,
) -> None:
    """拒绝与系统目录、配置目录或程序安装目录重叠的路径。"""
    protected = (
        _get_protected_paths()
        if protected_paths is None
        else tuple(Path(item) for item in protected_paths)
    )

    for item in protected:
        try:
            protected_path = normalize_path(item)
        except PathSecurityError as exc:
            raise PathSecurityError("无法确定受保护目录，已拒绝使用该路径。") from exc

        if _paths_overlap(path, protected_path):
            raise PathSecurityError(f"路径与受保护目录重叠，不能用作知识库位置：{protected_path}")


def _validate_directory_path(
    path: str | os.PathLike[str],
    *,
    must_exist: bool,
    protected_paths: Iterable[str | os.PathLike[str]] | None = None,
) -> Path:
    """执行通用知识库目录路径安全检查。"""
    try:
        raw_path = os.fspath(path)

        if not isinstance(raw_path, str) or not raw_path.strip():
            raise PathSecurityError("路径不能为空。")

        if "\x00" in raw_path:
            raise PathSecurityError("路径包含无效字符。")

        # 先展开用户目录并转换为绝对路径。
        # abspath 只进行词法规范化，不解析符号链接。
        original = Path(raw_path).expanduser()

        if not original.is_absolute():
            original = Path.cwd() / original

        original = Path(os.path.abspath(original))

        # 必须在 resolve 之前检查原始路径。
        # 否则符号链接和 Junction 会被解析为真实路径，
        # 导致无法识别原始路径中的重解析点。
        _check_reparse_points(original)

        # 原始路径检查通过后，才进行最终规范化。
        normalized = original.resolve(strict=False)

        if _is_filesystem_root(normalized):
            raise PathSecurityError("不能将磁盘根目录用作知识库目录。")

        _validate_protected_path(normalized, protected_paths)

        if must_exist:
            if not normalized.exists():
                raise PathSecurityError("指定的知识库目录不存在。")

            if not normalized.is_dir():
                raise PathSecurityError("指定的知识库路径不是目录。")
        else:
            if normalized.exists() and not normalized.is_dir():
                raise PathSecurityError("迁移目标已存在，但不是目录。")

            if not normalized.parent.exists():
                raise PathSecurityError("迁移目标的父目录不存在。")

            if not normalized.parent.is_dir():
                raise PathSecurityError("迁移目标的父路径不是目录。")

        return normalized

    except PathSecurityError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise PathSecurityError("路径安全检查失败。") from exc

def validate_knowledge_destination(
    path: str | os.PathLike[str],
    *,
    protected_paths: Iterable[str | os.PathLike[str]] | None = None,
) -> Path:
    """验证知识库部署目标路径，不创建、删除或修改任何文件。"""
    return _validate_directory_path(
        path,
        must_exist=False,
        protected_paths=protected_paths,
    )

def validate_knowledge_path(
    path: str | os.PathLike[str],
    *,
    protected_paths: Iterable[str | os.PathLike[str]] | None = None,
) -> Path:
    """验证当前知识库根目录及其基本结构。"""
    normalized = _validate_directory_path(
        path,
        must_exist=True,
        protected_paths=protected_paths,
    )

    # 使用现有知识库加载器验证 Manifest 和目录结构。
    # 延迟导入，避免模块初始化时产生循环依赖。
    from lcmd.knowledge.loader import KnowledgeLoadError, discover_catalog

    try:
        discover_catalog(normalized)
    except KnowledgeLoadError as exc:
        raise PathSecurityError(f"知识库结构无效：{exc}") from exc

    return normalized


def validate_migration_target(
    target_path: str | os.PathLike[str],
    source_path: str | os.PathLike[str],
    *,
    protected_paths: Iterable[str | os.PathLike[str]] | None = None,
) -> Path:
    """验证迁移目标路径，不创建、删除或修改任何文件。"""
    source = _validate_directory_path(
        source_path,
        must_exist=True,
        protected_paths=protected_paths,
    )

    target = _validate_directory_path(
        target_path,
        must_exist=False,
        protected_paths=protected_paths,
    )

    if _paths_overlap(target, source):
        raise PathSecurityError(
            "迁移目标不能与当前知识库相同，也不能位于当前知识库内部或其父目录。"
        )

    return target
