from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

import lcmd.core.update_download as download_module
from lcmd.core.update import ReleaseAsset
from lcmd.core.update_download import (
    AssetDownloadError,
    download_release_asset,
)


def make_zip() -> bytes:
    """生成有效的测试 ZIP。"""
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("app/readme.txt", "LCMD test")

    return buffer.getvalue()


class FakeResponse:
    """模拟 HTTP 下载响应。"""

    def __init__(
        self,
        content: bytes,
        *,
        status: int = 200,
        url: str = "https://release-assets.githubusercontent.com/file.zip",
    ):
        self.content = io.BytesIO(content)
        self.status = status
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.content.read(size)

    def geturl(self) -> str:
        return self.url


def make_asset(content: bytes | None = None) -> tuple[ReleaseAsset, bytes]:
    if content is None:
        content = make_zip()

    asset = ReleaseAsset(
        name="lcmd-0.2.0.zip",
        download_url=("https://github.com/WenZoo1982/lcmd/releases/download/v0.2.0/lcmd-0.2.0.zip"),
        size=len(content),
        digest="sha256:" + hashlib.sha256(content).hexdigest(),
    )

    return asset, content


def install_response(monkeypatch, response):
    mocked = Mock(return_value=response)
    monkeypatch.setattr(download_module, "urlopen", mocked)
    return mocked


def test_download_valid_asset(tmp_path, monkeypatch):
    asset, content = make_asset()

    install_response(monkeypatch, FakeResponse(content))

    destination = tmp_path / "lcmd.zip"

    result = download_release_asset(asset, destination)

    assert result == destination
    assert destination.read_bytes() == content
    assert zipfile.is_zipfile(destination)


def test_download_returns_target_path(tmp_path, monkeypatch):
    asset, content = make_asset()

    install_response(monkeypatch, FakeResponse(content))

    result = download_release_asset(
        asset,
        tmp_path / "release.zip",
    )

    assert isinstance(result, Path)
    assert result.name == "release.zip"


def test_download_sends_expected_request(tmp_path, monkeypatch):
    asset, content = make_asset()

    mocked = install_response(
        monkeypatch,
        FakeResponse(content),
    )

    download_release_asset(asset, tmp_path / "release.zip")

    request = mocked.call_args.args[0]

    assert request.full_url == asset.download_url
    assert request.get_method() == "GET"
    assert request.get_header("User-agent") == "LCMD"
    assert request.get_header("Accept") == "application/octet-stream"


def test_download_uses_given_timeout(tmp_path, monkeypatch):
    asset, content = make_asset()

    mocked = install_response(
        monkeypatch,
        FakeResponse(content),
    )

    download_release_asset(
        asset,
        tmp_path / "release.zip",
        timeout=12.0,
    )

    assert mocked.call_args.kwargs["timeout"] == 12.0


@pytest.mark.parametrize(
    "digest",
    [
        None,
        "",
        "md5:" + "a" * 32,
        "sha256:invalid",
        "sha256:" + "g" * 64,
    ],
)
def test_invalid_digest_is_rejected(tmp_path, monkeypatch, digest):
    asset, _ = make_asset()
    asset = ReleaseAsset(
        name=asset.name,
        download_url=asset.download_url,
        size=asset.size,
        digest=digest,
    )

    mocked = Mock()
    monkeypatch.setattr(download_module, "urlopen", mocked)

    with pytest.raises(AssetDownloadError):
        download_release_asset(asset, tmp_path / "release.zip")

    mocked.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/file.zip",
        "https://example.com/file.zip",
        "https://user:password@github.com/file.zip",
        "not-a-url",
    ],
)
def test_untrusted_download_url_is_rejected(tmp_path, monkeypatch, url):
    asset, _ = make_asset()
    asset = ReleaseAsset(
        name=asset.name,
        download_url=url,
        size=asset.size,
        digest=asset.digest,
    )

    mocked = Mock()
    monkeypatch.setattr(download_module, "urlopen", mocked)

    with pytest.raises(AssetDownloadError):
        download_release_asset(asset, tmp_path / "release.zip")

    mocked.assert_not_called()


@pytest.mark.parametrize("size", [0, -1, True, "100"])
def test_invalid_asset_size_is_rejected(tmp_path, monkeypatch, size):
    asset, _ = make_asset()
    asset = ReleaseAsset(
        name=asset.name,
        download_url=asset.download_url,
        size=size,
        digest=asset.digest,
    )

    mocked = Mock()
    monkeypatch.setattr(download_module, "urlopen", mocked)

    with pytest.raises(AssetDownloadError):
        download_release_asset(asset, tmp_path / "release.zip")

    mocked.assert_not_called()


def test_download_rejects_invalid_timeout(tmp_path, monkeypatch):
    asset, _ = make_asset()

    mocked = Mock()
    monkeypatch.setattr(download_module, "urlopen", mocked)

    with pytest.raises(AssetDownloadError, match="超时时间"):
        download_release_asset(
            asset,
            tmp_path / "release.zip",
            timeout=0,
        )

    mocked.assert_not_called()


def test_download_rejects_missing_destination_directory(tmp_path, monkeypatch):
    asset, _ = make_asset()

    mocked = Mock()
    monkeypatch.setattr(download_module, "urlopen", mocked)

    destination = tmp_path / "missing" / "release.zip"

    with pytest.raises(AssetDownloadError, match="目录不存在"):
        download_release_asset(asset, destination)

    mocked.assert_not_called()


def test_download_rejects_untrusted_redirect(tmp_path, monkeypatch):
    asset, content = make_asset()

    install_response(
        monkeypatch,
        FakeResponse(
            content,
            url="https://example.com/redirected.zip",
        ),
    )

    with pytest.raises(AssetDownloadError, match="重定向"):
        download_release_asset(asset, tmp_path / "release.zip")

    assert not (tmp_path / "release.zip").exists()


def test_download_rejects_wrong_size(tmp_path, monkeypatch):
    asset, content = make_asset()
    asset = ReleaseAsset(
        name=asset.name,
        download_url=asset.download_url,
        size=asset.size + 1,
        digest=asset.digest,
    )

    install_response(monkeypatch, FakeResponse(content))

    with pytest.raises(AssetDownloadError, match="大小不匹配"):
        download_release_asset(asset, tmp_path / "release.zip")

    assert not (tmp_path / "release.zip").exists()


def test_download_rejects_oversized_response(tmp_path, monkeypatch):
    asset, content = make_asset()
    asset = ReleaseAsset(
        name=asset.name,
        download_url=asset.download_url,
        size=len(content) - 1,
        digest=asset.digest,
    )

    install_response(monkeypatch, FakeResponse(content))

    with pytest.raises(AssetDownloadError, match="超过"):
        download_release_asset(asset, tmp_path / "release.zip")

    assert not (tmp_path / "release.zip").exists()


def test_download_rejects_wrong_digest(tmp_path, monkeypatch):
    asset, content = make_asset()
    asset = ReleaseAsset(
        name=asset.name,
        download_url=asset.download_url,
        size=asset.size,
        digest="sha256:" + "0" * 64,
    )

    install_response(monkeypatch, FakeResponse(content))

    with pytest.raises(AssetDownloadError, match="SHA-256"):
        download_release_asset(asset, tmp_path / "release.zip")

    assert not (tmp_path / "release.zip").exists()


def test_download_rejects_invalid_zip(tmp_path, monkeypatch):
    content = b"this is not a zip file"

    asset = ReleaseAsset(
        name="lcmd.zip",
        download_url="https://github.com/example/lcmd.zip",
        size=len(content),
        digest="sha256:" + hashlib.sha256(content).hexdigest(),
    )

    install_response(monkeypatch, FakeResponse(content))

    with pytest.raises(AssetDownloadError, match="ZIP"):
        download_release_asset(asset, tmp_path / "release.zip")

    assert not (tmp_path / "release.zip").exists()


def test_download_preserves_existing_target_on_digest_failure(
    tmp_path,
    monkeypatch,
):
    asset, content = make_asset()
    asset = ReleaseAsset(
        name=asset.name,
        download_url=asset.download_url,
        size=asset.size,
        digest="sha256:" + "0" * 64,
    )

    destination = tmp_path / "release.zip"
    destination.write_bytes(b"original content")

    install_response(monkeypatch, FakeResponse(content))

    with pytest.raises(AssetDownloadError):
        download_release_asset(asset, destination)

    assert destination.read_bytes() == b"original content"


def test_download_preserves_existing_target_on_network_error(
    tmp_path,
    monkeypatch,
):
    asset, _ = make_asset()

    destination = tmp_path / "release.zip"
    destination.write_bytes(b"original content")

    monkeypatch.setattr(
        download_module,
        "urlopen",
        Mock(side_effect=URLError("network unavailable")),
    )

    with pytest.raises(AssetDownloadError, match="无法连接"):
        download_release_asset(asset, destination)

    assert destination.read_bytes() == b"original content"


def test_download_preserves_existing_target_on_http_error(
    tmp_path,
    monkeypatch,
):
    asset, _ = make_asset()

    destination = tmp_path / "release.zip"
    destination.write_bytes(b"original content")

    monkeypatch.setattr(
        download_module,
        "urlopen",
        Mock(
            side_effect=HTTPError(
                asset.download_url,
                404,
                "Not Found",
                None,
                None,
            )
        ),
    )

    with pytest.raises(AssetDownloadError, match="HTTP 404"):
        download_release_asset(asset, destination)

    assert destination.read_bytes() == b"original content"


def test_download_cleans_temporary_file_on_failure(tmp_path, monkeypatch):
    asset, content = make_asset()
    asset = ReleaseAsset(
        name=asset.name,
        download_url=asset.download_url,
        size=asset.size,
        digest="sha256:" + "0" * 64,
    )

    install_response(monkeypatch, FakeResponse(content))

    with pytest.raises(AssetDownloadError):
        download_release_asset(asset, tmp_path / "release.zip")

    assert list(tmp_path.iterdir()) == []


def test_download_replaces_existing_file_after_success(tmp_path, monkeypatch):
    asset, content = make_asset()

    destination = tmp_path / "release.zip"
    destination.write_bytes(b"old content")

    install_response(monkeypatch, FakeResponse(content))

    download_release_asset(asset, destination)

    assert destination.read_bytes() == content


def test_download_rejects_non_file_target(tmp_path, monkeypatch):
    asset, _ = make_asset()

    destination = tmp_path / "release.zip"
    destination.mkdir()

    mocked = Mock()
    monkeypatch.setattr(download_module, "urlopen", mocked)

    with pytest.raises(AssetDownloadError, match="不是普通文件"):
        download_release_asset(asset, destination)

    mocked.assert_not_called()


def test_download_rejects_empty_zip(tmp_path, monkeypatch):
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w"):
        pass

    content = buffer.getvalue()

    asset = ReleaseAsset(
        name="empty.zip",
        download_url="https://github.com/example/empty.zip",
        size=len(content),
        digest="sha256:" + hashlib.sha256(content).hexdigest(),
    )

    install_response(monkeypatch, FakeResponse(content))

    with pytest.raises(AssetDownloadError, match="为空"):
        download_release_asset(asset, tmp_path / "empty.zip")

    assert not (tmp_path / "empty.zip").exists()
