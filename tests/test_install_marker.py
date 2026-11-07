from __future__ import annotations

import json
from pathlib import Path

from lcmd.main import _validate_install_marker


def _write_marker(data_dir: Path, data: dict[str, object]) -> Path:
    data_dir.mkdir(parents=True)
    marker = data_dir / ".lcmd-install.json"
    marker.write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )
    return marker


def test_validate_current_install_marker(tmp_path: Path, capsys) -> None:
    data_dir = tmp_path / "lcmd"
    marker = _write_marker(
        data_dir,
        {
            "product": "WenZoo.LCMD",
            "marker_version": 1,
            "main_version": "0.1.0",
            "app_dir": str(data_dir / "app"),
            "knowledge_dir": str(data_dir / "knowledge"),
            "uninstall_file": str(data_dir / "uninstall.sh"),
            "install_state": "installing",
        },
    )

    assert _validate_install_marker(str(marker), str(data_dir)) == 0
    assert "LCMD_INSTALL_MARKER=OK" in capsys.readouterr().out

    data = json.loads(marker.read_text(encoding="utf-8"))
    data["install_state"] = "complete"
    marker.write_text(json.dumps(data), encoding="utf-8")
    assert _validate_install_marker(str(marker), str(data_dir)) == 0


def test_validate_legacy_install_marker(tmp_path: Path) -> None:
    data_dir = tmp_path / "lcmd"
    marker = _write_marker(
        data_dir,
        {
            "product": "WenZoo.LCMD",
            "marker_version": 1,
            "main_version": "0.1.0",
        },
    )

    assert _validate_install_marker(str(marker), str(data_dir)) == 0


def test_validate_install_marker_rejects_wrong_managed_path(
    tmp_path: Path,
    capsys,
) -> None:
    data_dir = tmp_path / "lcmd"
    marker = _write_marker(
        data_dir,
        {
            "product": "WenZoo.LCMD",
            "marker_version": 1,
            "main_version": "0.1.0",
            "app_dir": str(tmp_path / "other-app"),
            "knowledge_dir": str(data_dir / "knowledge"),
            "uninstall_file": str(data_dir / "uninstall.sh"),
        },
    )

    assert _validate_install_marker(str(marker), str(data_dir)) == 1
    assert "管理路径不匹配" in capsys.readouterr().err


def test_validate_install_marker_rejects_duplicate_json_keys(
    tmp_path: Path,
    capsys,
) -> None:
    data_dir = tmp_path / "lcmd"
    data_dir.mkdir()
    marker = data_dir / ".lcmd-install.json"
    marker.write_text(
        '{"product":"WenZoo.LCMD","product":"Other",'
        '"marker_version":1,"main_version":"0.1.0"}',
        encoding="utf-8",
    )

    assert _validate_install_marker(str(marker), str(data_dir)) == 1
    assert "重复字段" in capsys.readouterr().err
