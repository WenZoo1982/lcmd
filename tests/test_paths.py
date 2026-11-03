from pathlib import Path

from lcmd.core import paths


def test_get_config_dir_uses_platformdirs(monkeypatch, tmp_path):
    calls = []

    def fake_user_config_path(appname, appauthor):
        calls.append((appname, appauthor))
        return tmp_path / "config"

    monkeypatch.setattr(paths, "user_config_path", fake_user_config_path)

    result = paths.get_config_dir()

    assert result == tmp_path / "config"
    assert isinstance(result, Path)
    assert calls == [("lcmd", False)]


def test_get_config_file_uses_config_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        paths,
        "get_config_dir",
        lambda: tmp_path / "config",
    )

    assert paths.get_config_file() == tmp_path / "config" / "config.toml"


def test_get_data_dir_uses_platformdirs(monkeypatch, tmp_path):
    calls = []

    def fake_user_data_path(appname, appauthor):
        calls.append((appname, appauthor))
        return tmp_path / "data"

    monkeypatch.setattr(paths, "user_data_path", fake_user_data_path)

    result = paths.get_data_dir()

    assert result == tmp_path / "data"
    assert isinstance(result, Path)
    assert calls == [("lcmd", False)]


def test_get_default_knowledge_path_uses_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        paths,
        "get_data_dir",
        lambda: tmp_path / "data",
    )

    assert paths.get_default_knowledge_path() == tmp_path / "data" / "knowledge"


def test_get_default_knowledge_path_does_not_create_directory(
    monkeypatch,
    tmp_path,
):
    knowledge_path = tmp_path / "data" / "knowledge"

    monkeypatch.setattr(
        paths,
        "get_data_dir",
        lambda: tmp_path / "data",
    )

    result = paths.get_default_knowledge_path()

    assert result == knowledge_path
    assert not knowledge_path.exists()


def test_path_functions_return_path_objects(monkeypatch, tmp_path):
    monkeypatch.setattr(
        paths,
        "user_config_path",
        lambda appname, appauthor: tmp_path / "config",
    )
    monkeypatch.setattr(
        paths,
        "user_data_path",
        lambda appname, appauthor: tmp_path / "data",
    )

    assert isinstance(paths.get_config_dir(), Path)
    assert isinstance(paths.get_config_file(), Path)
    assert isinstance(paths.get_data_dir(), Path)
    assert isinstance(paths.get_default_knowledge_path(), Path)
