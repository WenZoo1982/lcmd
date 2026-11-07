from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "uninstall.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")

pytestmark = pytest.mark.skipif(
    os.name != "nt" or POWERSHELL is None,
    reason="Windows PowerShell integration tests require Windows PowerShell 5.1.",
)


def _create_installation(root: Path) -> dict[str, Path]:
    local_app_data = root / "LocalAppData"
    install_dir = local_app_data / "Programs" / "LCMD"
    data_dir = local_app_data / "lcmd"
    internal_dir = install_dir / "_internal"
    knowledge_dir = data_dir / "knowledge"

    internal_dir.mkdir(parents=True)
    knowledge_dir.mkdir(parents=True)
    (install_dir / "lcmd.exe").write_text("test executable", encoding="utf-8")
    (internal_dir / "payload.dat").write_text("test payload", encoding="utf-8")
    shutil.copy2(SCRIPT, install_dir / "uninstall.ps1")
    (knowledge_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (data_dir / "config.toml").write_text("test config", encoding="utf-8")

    marker = {
        "product": "WenZoo.LCMD",
        "marker_version": 1,
        "main_version": "0.1.0",
        "install_dir": str(install_dir),
    }
    (install_dir / ".lcmd-install.json").write_text(
        json.dumps(marker),
        encoding="utf-8",
    )

    return {
        "local_app_data": local_app_data,
        "install": install_dir,
        "data": data_dir,
        "knowledge": knowledge_dir,
        "config": data_dir / "config.toml",
    }


def _run_uninstaller(
    root: Path,
    answer: str,
    *,
    what_if: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(root / "LocalAppData")
    env["TEMP"] = str(root)

    command = [
        str(POWERSHELL),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "LocalAppData" / "Programs" / "LCMD" / "uninstall.ps1"),
    ]
    if what_if:
        command.append("-WhatIf")

    return subprocess.run(
        command,
        input=f"{answer}\n",
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=30,
        check=False,
    )


def test_uninstall_whatif_keeps_all_files_unchanged(tmp_path: Path) -> None:
    paths = _create_installation(tmp_path)

    result = _run_uninstaller(tmp_path, "Y", what_if=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert paths["install"].is_dir()
    assert paths["knowledge"].is_dir()
    assert paths["config"].is_file()
    assert "What if:" in result.stdout


def test_uninstall_cancel_keeps_installation_unchanged(tmp_path: Path) -> None:
    paths = _create_installation(tmp_path)

    result = _run_uninstaller(tmp_path, "N")

    assert result.returncode == 0, result.stdout + result.stderr
    assert paths["install"].is_dir()
    assert paths["knowledge"].is_dir()
    assert paths["config"].is_file()
    assert "INSTALL_RESULT=ERROR" not in result.stdout


def test_uninstall_rejects_invalid_marker_before_deleting(tmp_path: Path) -> None:
    paths = _create_installation(tmp_path)
    marker_file = paths["install"] / ".lcmd-install.json"
    marker = json.loads(marker_file.read_text(encoding="utf-8"))
    marker["product"] = "Other.Product"
    marker_file.write_text(json.dumps(marker), encoding="utf-8")

    result = _run_uninstaller(tmp_path, "Y")

    assert result.returncode == 1
    assert paths["install"].is_dir()
    assert paths["knowledge"].is_dir()
    assert paths["config"].is_file()
    assert "UNINSTALL_RESULT=ERROR" in result.stdout


def test_uninstall_removes_only_lcmd_managed_directories(tmp_path: Path) -> None:
    paths = _create_installation(tmp_path)
    unrelated_data = paths["data"] / "keep-me.txt"
    unrelated_data.write_text("keep", encoding="utf-8")
    custom_knowledge = tmp_path / "custom-knowledge"
    custom_knowledge.mkdir()
    (custom_knowledge / "user.md").write_text("keep", encoding="utf-8")

    result = _run_uninstaller(tmp_path, "Y")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not paths["install"].exists()
    assert not paths["knowledge"].exists()
    assert not paths["config"].exists()
    assert unrelated_data.read_text(encoding="utf-8") == "keep"
    assert (custom_knowledge / "user.md").read_text(encoding="utf-8") == "keep"
    assert paths["data"].is_dir()
