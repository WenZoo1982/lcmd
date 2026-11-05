from __future__ import annotations

import json
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

import lcmd.core.update as update_module
from lcmd.core.update import (
    ReleaseCheckError,
    UpdateStatus,
    check_for_update,
    fetch_latest_release,
)


def make_release(
    *,
    tag_name: str = "v0.2.0",
    draft: bool = False,
    prerelease: bool = False,
    assets: list[dict] | None = None,
) -> dict:
    """生成 GitHub Release API 测试数据。"""
    if assets is None:
        assets = [
            {
                "name": "lcmd-0.2.0.zip",
                "browser_download_url": (
                    "https://github.com/WenZoo1982/lcmd/releases/download/v0.2.0/lcmd-0.2.0.zip"
                ),
                "size": 1024,
                "digest": "sha256:" + "a" * 64,
            }
        ]

    return {
        "tag_name": tag_name,
        "draft": draft,
        "prerelease": prerelease,
        "html_url": "https://github.com/WenZoo1982/lcmd/releases/tag/v0.2.0",
        "published_at": "2026-11-05T14:00:00Z",
        "assets": assets,
    }


class FakeResponse:
    """模拟 urllib 响应对象。"""

    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self.content = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.content


def mock_github_response(monkeypatch, payload: dict):
    """安装模拟 GitHub HTTP 响应。"""
    response = FakeResponse(payload)
    mocked_urlopen = Mock(return_value=response)

    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    return mocked_urlopen


def test_newer_release_is_update_available(monkeypatch):
    mock_github_response(monkeypatch, make_release())

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.UPDATE_AVAILABLE
    assert result.current_version == "0.1.0"
    assert result.latest_version == "0.2.0"
    assert result.release is not None
    assert result.release.tag_name == "v0.2.0"
    assert result.error is None


def test_same_release_is_up_to_date(monkeypatch):
    mock_github_response(
        monkeypatch,
        make_release(tag_name="v0.1.0"),
    )

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.UP_TO_DATE
    assert result.current_version == "0.1.0"
    assert result.latest_version == "0.1.0"
    assert result.error is None


def test_lower_remote_release_does_not_trigger_downgrade(monkeypatch):
    mock_github_response(
        monkeypatch,
        make_release(tag_name="v0.1.0"),
    )

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.2.0",
    )

    assert result.status is UpdateStatus.UP_TO_DATE
    assert result.current_version == "0.2.0"
    assert result.latest_version == "0.1.0"


@pytest.mark.parametrize(
    ("tag_name", "expected"),
    [
        ("v0.1.1", UpdateStatus.UPDATE_AVAILABLE),
        ("v0.2.0", UpdateStatus.UPDATE_AVAILABLE),
        ("v1.0.0", UpdateStatus.UPDATE_AVAILABLE),
        ("v0.1.0", UpdateStatus.UP_TO_DATE),
    ],
)
def test_version_comparison_uses_numeric_segments(
    monkeypatch,
    tag_name,
    expected,
):
    mock_github_response(
        monkeypatch,
        make_release(tag_name=tag_name),
    )

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("draft", True),
        ("draft", None),
        ("draft", "false"),
        ("prerelease", True),
        ("prerelease", None),
        ("prerelease", "false"),
    ],
)
def test_invalid_release_status_is_rejected(
    monkeypatch,
    field,
    value,
):
    payload = make_release()
    payload[field] = value

    mock_github_response(monkeypatch, payload)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    assert result.release is None
    assert result.error


@pytest.mark.parametrize(
    "tag_name",
    [
        "0.2.0",
        "v0.2",
        "v0.2.0-beta.1",
        "latest",
        "",
        None,
    ],
)
def test_invalid_release_tag_is_rejected(monkeypatch, tag_name):
    payload = make_release(tag_name=tag_name)

    mock_github_response(monkeypatch, payload)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    assert result.error


@pytest.mark.parametrize(
    "field",
    [
        "draft",
        "prerelease",
        "tag_name",
        "html_url",
        "assets",
    ],
)
def test_missing_required_release_field_is_rejected(monkeypatch, field):
    payload = make_release()
    del payload[field]

    mock_github_response(monkeypatch, payload)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    assert result.error


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/example",
        "https://",
        "https://user:password@github.com/example",
        "not-a-url",
    ],
)
def test_invalid_release_url_is_rejected(monkeypatch, url):
    payload = make_release()
    payload["html_url"] = url

    mock_github_response(monkeypatch, payload)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.error


def test_invalid_asset_metadata_is_rejected(monkeypatch):
    payload = make_release()
    payload["assets"][0]["size"] = True

    mock_github_response(monkeypatch, payload)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.error


def test_asset_without_digest_is_allowed(monkeypatch):
    payload = make_release()
    payload["assets"][0]["digest"] = None

    mock_github_response(monkeypatch, payload)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.UPDATE_AVAILABLE
    assert result.release is not None
    assert result.release.assets[0].digest is None


def test_invalid_json_is_check_failed(monkeypatch):
    response = Mock()
    response.status = 200
    response.read.return_value = b"{invalid json"

    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    mocked_urlopen = Mock(return_value=response)
    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    assert "JSON" in result.error


def test_http_error_is_check_failed(monkeypatch):
    mocked_urlopen = Mock(
        side_effect=HTTPError(
            url="https://api.github.com/repos/WenZoo1982/lcmd/releases/latest",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
    )
    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    assert "404" in result.error


def test_network_error_is_check_failed(monkeypatch):
    mocked_urlopen = Mock(side_effect=URLError("网络不可用"))
    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    assert "GitHub" in result.error


def test_timeout_is_check_failed(monkeypatch):
    mocked_urlopen = Mock(side_effect=TimeoutError("连接超时"))
    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    assert "超时" in result.error


def test_invalid_repository_is_rejected_without_network(monkeypatch):
    mocked_urlopen = Mock()
    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    result = check_for_update(
        "https://github.com/WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    mocked_urlopen.assert_not_called()


def test_invalid_local_version_is_rejected_without_network(monkeypatch):
    mocked_urlopen = Mock()
    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0-beta.1",
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.latest_version is None
    mocked_urlopen.assert_not_called()


def test_fetch_latest_release_sends_expected_request(monkeypatch):
    mocked_urlopen = mock_github_response(
        monkeypatch,
        make_release(),
    )

    release = fetch_latest_release(
        "WenZoo1982/lcmd",
        timeout=8.0,
        user_agent="LCMD/0.1.0",
    )

    mocked_urlopen.assert_called_once()

    request = mocked_urlopen.call_args.args[0]

    assert isinstance(request, Request)
    assert request.full_url == ("https://api.github.com/repos/WenZoo1982/lcmd/releases/latest")
    assert request.get_method() == "GET"
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert request.get_header("User-agent") == "LCMD/0.1.0"
    assert request.get_header("X-github-api-version") == "2022-11-28"
    assert mocked_urlopen.call_args.kwargs["timeout"] == 8.0

    assert release.version == "0.2.0"
    assert release.tag_name == "v0.2.0"
    assert release.assets[0].name == "lcmd-0.2.0.zip"
    assert release.assets[0].size == 1024
    assert release.assets[0].digest == "sha256:" + "a" * 64


def test_failed_check_never_reports_up_to_date(monkeypatch):
    mocked_urlopen = Mock(side_effect=URLError("连接失败"))
    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    result = check_for_update(
        "WenZoo1982/lcmd",
        "0.1.0",
    )

    assert result.status is not UpdateStatus.UP_TO_DATE
    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.release is None
    assert result.latest_version is None
    assert result.error is not None


def test_fetch_latest_release_rejects_non_object_json(monkeypatch):
    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps(["not", "an", "object"]).encode("utf-8")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    monkeypatch.setattr(
        update_module,
        "urlopen",
        Mock(return_value=response),
    )

    with pytest.raises(ReleaseCheckError, match="不是 JSON 对象"):
        fetch_latest_release("WenZoo1982/lcmd")


def test_invalid_timeout_is_rejected_without_network(monkeypatch):
    mocked_urlopen = Mock()
    monkeypatch.setattr(update_module, "urlopen", mocked_urlopen)

    with pytest.raises(ReleaseCheckError, match="超时时间"):
        fetch_latest_release(
            "WenZoo1982/lcmd",
            timeout=0,
        )

    mocked_urlopen.assert_not_called()
