from __future__ import annotations

import hashlib
import hmac
import os
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from lcmd.core.update import ReleaseAsset

_DEFAULT_TIMEOUT = 30.0
_CHUNK_SIZE = 1024 * 1024

_ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
}

_ALLOWED_REDIRECT_HOSTS = {
    "github.com",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
}


class AssetDownloadError(RuntimeError):
    """发行资产下载或完整性验证失败。"""


def _validate_asset(asset: ReleaseAsset) -> str:
    """验证发行资产元数据，并返回标准化 SHA-256。"""
    if not isinstance(asset, ReleaseAsset):
        raise AssetDownloadError("发行资产类型无效。")

    if not isinstance(asset.name, str) or not asset.name.strip():
        raise AssetDownloadError("发行资产文件名无效。")

    if isinstance(asset.size, bool) or not isinstance(asset.size, int) or asset.size <= 0:
        raise AssetDownloadError("发行资产大小必须是正整数。")

    if not isinstance(asset.digest, str):
        raise AssetDownloadError("发行资产缺少 SHA-256，拒绝下载。")

    prefix = "sha256:"
    if not asset.digest.lower().startswith(prefix):
        raise AssetDownloadError("发行资产 SHA-256 格式无效。")

    expected_digest = asset.digest[len(prefix) :].lower()

    if len(expected_digest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_digest
    ):
        raise AssetDownloadError("发行资产 SHA-256 格式无效。")

    try:
        parsed = urlsplit(asset.download_url)
    except ValueError as exc:
        raise AssetDownloadError("发行资产下载地址无效。") from exc

    if (
        parsed.scheme != "https"
        or parsed.hostname not in _ALLOWED_DOWNLOAD_HOSTS
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise AssetDownloadError("发行资产下载地址不是受信任的 GitHub HTTPS 地址。")

    return expected_digest


def _validate_response_url(response: object) -> None:
    """验证 HTTP 重定向后的最终地址。"""
    final_url = response.geturl()

    try:
        parsed = urlsplit(final_url)
    except ValueError as exc:
        raise AssetDownloadError("下载重定向地址无效。") from exc

    if (
        parsed.scheme != "https"
        or parsed.hostname not in _ALLOWED_REDIRECT_HOSTS
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise AssetDownloadError("下载被重定向到不受信任的地址，已拒绝。")


def _verify_zip(path: Path) -> None:
    """验证 ZIP 结构及所有成员的 CRC。"""
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if not archive.infolist():
                raise AssetDownloadError("发行资产 ZIP 文件为空。")

            bad_file = archive.testzip()

            if bad_file is not None:
                raise AssetDownloadError(f"发行资产 ZIP CRC 校验失败：{bad_file}")

    except AssetDownloadError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise AssetDownloadError("发行资产不是有效的 ZIP 文件，或 ZIP 内容损坏。") from exc


def download_release_asset(
    asset: ReleaseAsset,
    destination: str | os.PathLike[str],
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> Path:
    """下载并验证 GitHub Release ZIP 资产。

    下载先写入目标目录中的临时文件。

    只有文件大小、SHA-256 和 ZIP CRC 全部通过后，
    才使用 os.replace 原子替换正式目标文件。

    失败时保留原目标文件，并清理本次临时文件。
    """
    expected_digest = _validate_asset(asset)

    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise AssetDownloadError("下载超时时间必须是正数。")

    target = Path(destination)

    if not target.name:
        raise AssetDownloadError("下载目标文件路径无效。")

    parent = target.parent

    if not parent.is_dir():
        raise AssetDownloadError("下载目标目录不存在。")

    if target.exists() and not target.is_file():
        raise AssetDownloadError("下载目标已经存在，但不是普通文件。")

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=parent,
            prefix=f".{target.name}.",
            suffix=".download",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            request = Request(
                asset.download_url,
                headers={
                    "User-Agent": "LCMD",
                    "Accept": "application/octet-stream",
                },
                method="GET",
            )

            digest = hashlib.sha256()
            downloaded_size = 0

            with urlopen(request, timeout=timeout) as response:
                status_code = getattr(response, "status", 200)

                if status_code != 200:
                    raise AssetDownloadError(f"发行资产下载失败：HTTP {status_code}。")

                _validate_response_url(response)

                while True:
                    chunk = response.read(_CHUNK_SIZE)

                    if not chunk:
                        break

                    downloaded_size += len(chunk)

                    if downloaded_size > asset.size:
                        raise AssetDownloadError("下载文件超过 Release 记录的文件大小。")

                    digest.update(chunk)
                    temporary_file.write(chunk)

            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if downloaded_size != asset.size:
            raise AssetDownloadError(
                f"下载文件大小不匹配：预期 {asset.size} 字节，实际 {downloaded_size} 字节。"
            )

        actual_digest = digest.hexdigest()

        if not hmac.compare_digest(actual_digest, expected_digest):
            raise AssetDownloadError("发行资产 SHA-256 校验失败。")

        _verify_zip(temporary_path)

        os.replace(temporary_path, target)
        temporary_path = None

        return target

    except AssetDownloadError:
        raise
    except HTTPError as exc:
        raise AssetDownloadError(f"发行资产下载失败：HTTP {exc.code}。") from exc
    except URLError as exc:
        raise AssetDownloadError(f"无法连接 GitHub 下载服务器：{exc.reason}") from exc
    except TimeoutError as exc:
        raise AssetDownloadError("发行资产下载超时。") from exc
    except OSError as exc:
        raise AssetDownloadError(f"发行资产下载或保存失败：{exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
