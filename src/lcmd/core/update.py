from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAIN_REPOSITORY = "WenZoo1982/lcmd"
KNOWLEDGE_REPOSITORY = "WenZoo1982/lcmd-kb"

_GITHUB_API_VERSION = "2022-11-28"
_DEFAULT_TIMEOUT = 10.0

_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_RELEASE_TAG_PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_SHA256_PATTERN = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


class ReleaseCheckError(RuntimeError):
    """GitHub Release 查询或元数据验证失败。"""


class UpdateStatus(str, Enum):
    """在线更新检查结果状态。"""

    UPDATE_AVAILABLE = "update_available"
    UP_TO_DATE = "up_to_date"
    CHECK_FAILED = "check_failed"


@dataclass(frozen=True)
class ReleaseAsset:
    """GitHub Release 中的发行资产。"""

    name: str
    download_url: str
    size: int
    digest: str | None


@dataclass(frozen=True)
class ReleaseInfo:
    """经过验证的 GitHub 稳定 Release 信息。"""

    version: str
    tag_name: str
    html_url: str
    published_at: str | None
    assets: tuple[ReleaseAsset, ...]


@dataclass(frozen=True)
class UpdateCheckResult:
    """在线更新检查结果。"""

    status: UpdateStatus
    current_version: str
    latest_version: str | None = None
    release: ReleaseInfo | None = None
    error: str | None = None


def _parse_version(value: str) -> tuple[int, int, int]:
    """解析本地三段式版本号。"""
    if not isinstance(value, str):
        raise ValueError("版本号必须是字符串。")

    match = _VERSION_PATTERN.fullmatch(value)

    if match is None:
        raise ValueError(f"版本号格式无效：{value!r}")

    return tuple(int(part) for part in match.groups())


def _parse_release_tag(tag_name: Any) -> str:
    """验证 Release 标签，并返回不带 v 前缀的版本号。"""
    if not isinstance(tag_name, str):
        raise ReleaseCheckError("Release 缺少有效的 tag_name。")

    match = _RELEASE_TAG_PATTERN.fullmatch(tag_name)

    if match is None:
        raise ReleaseCheckError(f"Release 标签格式无效：{tag_name!r}，要求格式为 vX.Y.Z。")

    return ".".join(match.groups())


def _validate_https_url(value: Any, field_name: str) -> str:
    """验证 GitHub 返回的 HTTPS URL。"""
    if not isinstance(value, str) or not value:
        raise ReleaseCheckError(f"Release 字段 {field_name} 缺失或无效。")

    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ReleaseCheckError(f"Release 字段 {field_name} 不是有效 URL。") from exc

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ReleaseCheckError(f"Release 字段 {field_name} 不是有效的 HTTPS URL。")

    return value


def _validate_asset(data: Any) -> ReleaseAsset:
    """验证单个 Release 资产。"""
    if not isinstance(data, dict):
        raise ReleaseCheckError("Release 资产记录格式无效。")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ReleaseCheckError("Release 资产缺少有效的文件名。")

    download_url = _validate_https_url(
        data.get("browser_download_url"),
        "browser_download_url",
    )

    size = data.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ReleaseCheckError(f"Release 资产大小无效：{name}")

    digest = data.get("digest")

    if digest is not None:
        if not isinstance(digest, str) or not _SHA256_PATTERN.fullmatch(digest):
            raise ReleaseCheckError(f"Release 资产 SHA-256 格式无效：{name}")

        digest = digest.lower()

    return ReleaseAsset(
        name=name,
        download_url=download_url,
        size=size,
        digest=digest,
    )


def _parse_release(data: Any) -> ReleaseInfo:
    """验证 GitHub Releases API 返回的最新稳定 Release。"""
    if not isinstance(data, dict):
        raise ReleaseCheckError("GitHub API 返回的 Release 数据不是 JSON 对象。")

    if data.get("draft") is not False:
        raise ReleaseCheckError("GitHub Release 不是已发布的正式版本（draft）。")

    if data.get("prerelease") is not False:
        raise ReleaseCheckError("GitHub Release 是预发布版本，不作为稳定更新。")

    version = _parse_release_tag(data.get("tag_name"))
    tag_name = data["tag_name"]

    html_url = _validate_https_url(data.get("html_url"), "html_url")

    published_at = data.get("published_at")
    if published_at is not None and (not isinstance(published_at, str) or not published_at):
        raise ReleaseCheckError("Release 字段 published_at 格式无效。")

    raw_assets = data.get("assets")
    if not isinstance(raw_assets, list):
        raise ReleaseCheckError("Release 缺少有效的 assets 数组。")

    assets = tuple(_validate_asset(asset) for asset in raw_assets)

    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        html_url=html_url,
        published_at=published_at,
        assets=assets,
    )


def fetch_latest_release(
    repository: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    user_agent: str = "LCMD",
) -> ReleaseInfo:
    """查询指定公开仓库的最新稳定 Release。

    该函数只查询 Release 元数据，不下载资产、不修改本地文件。
    """
    if not isinstance(repository, str) or not _REPOSITORY_PATTERN.fullmatch(repository):
        raise ReleaseCheckError(f"GitHub 仓库名称格式无效：{repository!r}")

    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ReleaseCheckError("网络请求超时时间必须是正数。")

    if not isinstance(user_agent, str) or not user_agent.strip():
        raise ReleaseCheckError("User-Agent 不能为空。")

    api_url = f"https://api.github.com/repos/{repository}/releases/latest"

    request = Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": user_agent,
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)

            if status_code != 200:
                raise ReleaseCheckError(f"GitHub API 返回 HTTP {status_code}。")

            raw_content = response.read()

    except HTTPError as exc:
        raise ReleaseCheckError(f"GitHub API 请求失败：HTTP {exc.code}。") from exc
    except URLError as exc:
        raise ReleaseCheckError(f"无法连接 GitHub：{exc.reason}") from exc
    except TimeoutError as exc:
        raise ReleaseCheckError("连接 GitHub 超时。") from exc
    except OSError as exc:
        raise ReleaseCheckError(f"读取 GitHub 响应失败：{exc}") from exc

    try:
        if not isinstance(raw_content, bytes):
            raise TypeError("HTTP 响应内容不是字节数据。")

        payload = json.loads(raw_content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ReleaseCheckError("GitHub API 返回了无效的 JSON 数据。") from exc

    return _parse_release(payload)


def check_for_update(
    repository: str,
    current_version: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> UpdateCheckResult:
    """比较本地版本与 GitHub 最新稳定 Release。

    远程版本高于本地版本时返回 UPDATE_AVAILABLE。
    远程版本等于或低于本地版本时返回 UP_TO_DATE。
    网络、元数据或版本检查失败时返回 CHECK_FAILED。
    不提供降级操作。
    """
    try:
        current_version_parts = _parse_version(current_version)
    except ValueError as exc:
        return UpdateCheckResult(
            status=UpdateStatus.CHECK_FAILED,
            current_version=current_version,
            error=str(exc),
        )

    try:
        release = fetch_latest_release(
            repository,
            timeout=timeout,
            user_agent=f"LCMD/{current_version}",
        )
    except ReleaseCheckError as exc:
        return UpdateCheckResult(
            status=UpdateStatus.CHECK_FAILED,
            current_version=current_version,
            error=str(exc),
        )

    latest_version_parts = _parse_version(release.version)

    if latest_version_parts > current_version_parts:
        status = UpdateStatus.UPDATE_AVAILABLE
    else:
        status = UpdateStatus.UP_TO_DATE

    return UpdateCheckResult(
        status=status,
        current_version=current_version,
        latest_version=release.version,
        release=release,
    )
