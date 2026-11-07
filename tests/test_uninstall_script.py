from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "uninstall.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    os.name != "posix" or BASH is None,
    reason="Linux Bash integration tests run on POSIX systems with bash.",
)


def _create_installation(home: Path) -> dict[str, Path]:
    data_dir = home / ".local" / "share" / "lcmd"
    app_dir = data_dir / "app"
    knowledge_dir = data_dir / "knowledge"
    config_dir = home / ".config" / "lcmd"
    bin_dir = home / ".local" / "bin"

    app_dir.mkdir(parents=True)
    knowledge_dir.mkdir()
    config_dir.mkdir(parents=True)
    bin_dir.mkdir(parents=True)

    (app_dir / "lcmd").write_text("test executable", encoding="utf-8")
    (knowledge_dir / "manifest.json").write_text("{}", encoding="utf-8")
    uninstall_file = data_dir / "uninstall.sh"
    uninstall_file.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    marker = {
        "product": "WenZoo.LCMD",
        "marker_version": 1,
        "main_version": "0.1.0",
        "app_dir": str(app_dir),
        "knowledge_dir": str(knowledge_dir),
        "uninstall_file": str(uninstall_file),
        "install_state": "complete",
    }
    (data_dir / ".lcmd-install.json").write_text(
        json.dumps(marker),
        encoding="utf-8",
    )

    (bin_dir / "lcmd").symlink_to(app_dir / "lcmd")
    (bin_dir / "lcmd-uninstall").symlink_to(uninstall_file)

    profile = home / ".profile"
    profile.write_text(
        "export KEEP_BEFORE=1\n"
        "# >>> LCMD PATH >>>\n"
        'case ":$PATH:" in\n'
        '    *":$HOME/.local/bin:"*) ;;\n'
        '    *) PATH="$HOME/.local/bin:$PATH" ;;\n'
        "esac\n"
        "export PATH\n"
        "# <<< LCMD PATH <<<\n"
        "export KEEP_AFTER=1\n",
        encoding="utf-8",
    )

    return {
        "data": data_dir,
        "config": config_dir,
        "bin": bin_dir,
        "profile": profile,
        "app": app_dir,
        "uninstall": uninstall_file,
    }


def _run_uninstaller(home: Path, answer: str = "y\n") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        [str(BASH), str(SCRIPT)],
        input=answer,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_uninstall_removes_only_lcmd_managed_content(tmp_path: Path) -> None:
    paths = _create_installation(tmp_path)
    unrelated = paths["bin"] / "my-command"
    unrelated.write_text("keep", encoding="utf-8")

    result = _run_uninstaller(tmp_path)

    assert result.returncode == 0, result.stderr
    assert not paths["data"].exists()
    assert not paths["config"].exists()
    assert not (paths["bin"] / "lcmd").exists()
    assert not (paths["bin"] / "lcmd-uninstall").exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert paths["profile"].read_text(encoding="utf-8") == (
        "export KEEP_BEFORE=1\nexport KEEP_AFTER=1\n"
    )


def test_uninstall_rejects_invalid_install_marker(tmp_path: Path) -> None:
    paths = _create_installation(tmp_path)
    marker_file = paths["data"] / ".lcmd-install.json"
    marker = json.loads(marker_file.read_text(encoding="utf-8"))
    marker["product"] = "Other.Product"
    marker_file.write_text(json.dumps(marker), encoding="utf-8")

    result = _run_uninstaller(tmp_path)

    assert result.returncode == 1
    assert paths["data"].is_dir()
    assert paths["config"].is_dir()
    assert "安装标记产品标识不匹配" in result.stderr


def test_uninstall_rejects_malformed_profile_before_deleting(
    tmp_path: Path,
) -> None:
    paths = _create_installation(tmp_path)
    paths["profile"].write_text(
        "export KEEP=1\n# >>> LCMD PATH >>>\n",
        encoding="utf-8",
    )

    result = _run_uninstaller(tmp_path)

    assert result.returncode == 1
    assert paths["data"].is_dir()
    assert paths["config"].is_dir()
    assert "PATH 配置块异常" in result.stderr


def test_uninstall_cancel_keeps_installation_unchanged(tmp_path: Path) -> None:
    paths = _create_installation(tmp_path)
    original_profile = paths["profile"].read_text(encoding="utf-8")

    result = _run_uninstaller(tmp_path, answer="n\n")

    assert result.returncode == 0
    assert paths["data"].is_dir()
    assert paths["config"].is_dir()
    assert (paths["bin"] / "lcmd").is_symlink()
    assert paths["profile"].read_text(encoding="utf-8") == original_profile
    assert "已取消卸载" in result.stdout
