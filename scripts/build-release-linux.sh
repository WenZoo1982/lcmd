
#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# LCMD Linux Release Builder
# ============================================================

readonly MAIN_VERSION="0.1.0"
readonly MAIN_PRERELEASE="beta.10"
readonly KNOWLEDGE_VERSION="0.1.0"

readonly EXPECTED_ARCHIVE_SHA256="40678b849b388de3c1d251e54238aaa8aacabc6d889bc0f6a05fce6c0995db61"

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

readonly ARCHIVE="$PROJECT_ROOT/releases/lcmd-kb-0.1.0.zip"
readonly OUTPUT_DIR="$PROJECT_ROOT/releases/lcmd-linux-${MAIN_VERSION}-${MAIN_PRERELEASE}"

readonly PYTHON="$PROJECT_ROOT/.venv/bin/python"
readonly SPEC_FILE="$PROJECT_ROOT/lcmd.spec"

BUILD_ROOT=""

cleanup() {
    if [[ -n "$BUILD_ROOT" && -d "$BUILD_ROOT" ]]; then
        rm -rf -- "$BUILD_ROOT"
    fi
}

fail() {
    printf '\n构建失败：%s\n' "$*" >&2
    exit 1
}

trap cleanup EXIT

printf '%s\n' "============================================================"
printf '%s\n' "LCMD Linux Release Builder"
printf '%s\n' "主程序版本：${MAIN_VERSION}-${MAIN_PRERELEASE}"
printf '%s\n' "知识库版本：${KNOWLEDGE_VERSION}"
printf '%s\n' "============================================================"

# ------------------------------------------------------------
# 1. 环境与输入检查
# ------------------------------------------------------------

[[ -d "$PROJECT_ROOT" ]] || fail "项目目录不存在。"
[[ -f "$ARCHIVE" ]] || fail "知识库 ZIP 不存在：$ARCHIVE"
[[ -f "$SPEC_FILE" ]] || fail "PyInstaller spec 文件不存在。"
[[ -x "$PYTHON" ]] || fail "项目虚拟环境 Python 不存在或不可执行。"

[[ -f "$PROJECT_ROOT/scripts/install.sh" ]] ||
    fail "安装脚本不存在。"

[[ -f "$PROJECT_ROOT/scripts/uninstall.sh" ]] ||
    fail "卸载脚本不存在。"

[[ ! -e "$OUTPUT_DIR" && ! -L "$OUTPUT_DIR" ]] ||
    fail "发行包输出目录已经存在，拒绝覆盖：$OUTPUT_DIR"

"$PYTHON" -m PyInstaller --version >/dev/null 2>&1 ||
    fail "项目虚拟环境中没有可用的 PyInstaller。"

# ------------------------------------------------------------
# 2. 知识库 ZIP 完整性检查
# ------------------------------------------------------------

printf '\n[1/6] 检查知识库 ZIP...\n'

ACTUAL_ARCHIVE_SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"

[[ "$ACTUAL_ARCHIVE_SHA256" == "$EXPECTED_ARCHIVE_SHA256" ]] ||
    fail "知识库 ZIP SHA-256 不匹配。"

printf 'SHA-256：%s\n' "$ACTUAL_ARCHIVE_SHA256"
printf '知识库压缩包验证通过。\n'

# ------------------------------------------------------------
# 3. 创建临时构建目录
# ------------------------------------------------------------

BUILD_ROOT="$(mktemp -d "$PROJECT_ROOT/.lcmd-linux-build.XXXXXX")"

readonly STAGE="$BUILD_ROOT/package"
readonly KNOWLEDGE_DIR="$STAGE/knowledge"

mkdir -p "$KNOWLEDGE_DIR"

# ------------------------------------------------------------
# 4. 解压知识库并生成完整性清单
# ------------------------------------------------------------

printf '\n[2/6] 解压知识库并生成完整性清单...\n'

"$PYTHON" - "$ARCHIVE" "$KNOWLEDGE_DIR" \
    "$STAGE/knowledge-integrity.json" \
    "$MAIN_VERSION" "$MAIN_PRERELEASE" \
    "$KNOWLEDGE_VERSION" "$EXPECTED_ARCHIVE_SHA256" <<'PY'
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

(
    archive_path,
    knowledge_dir,
    integrity_path,
    main_version,
    main_prerelease,
    knowledge_version,
    archive_sha256,
) = sys.argv[1:]

archive = Path(archive_path)
root = Path(knowledge_dir)
integrity_file = Path(integrity_path)

def fail(message):
    raise SystemExit(f"知识库处理失败：{message}")

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

if not re.fullmatch(r"\d+\.\d+\.\d+", main_version):
    fail("主程序版本格式错误。")

if not re.fullmatch(r"[a-zA-Z0-9.-]+", main_prerelease):
    fail("预发布版本格式错误。")

if not re.fullmatch(r"\d+\.\d+\.\d+", knowledge_version):
    fail("知识库版本格式错误。")

if not re.fullmatch(r"[0-9a-f]{64}", archive_sha256):
    fail("知识库 ZIP SHA-256 格式错误。")

root.mkdir(parents=True, exist_ok=True)

seen = {}

with zipfile.ZipFile(archive, "r") as zf:
    for item in zf.infolist():
        name = item.filename

        if not name or "\\" in name or "\x00" in name:
            fail(f"ZIP 中存在非法路径：{name!r}")

        is_dir = item.is_dir()
        clean_name = name[:-1] if is_dir else name
        relative = PurePosixPath(clean_name)

        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in ("", ".", "..") for part in relative.parts)
        ):
            fail(f"ZIP 中存在不安全路径：{name!r}")

        if relative.as_posix() != clean_name:
            fail(f"ZIP 中存在非规范路径：{name!r}")

        key = clean_name.casefold()

        if key in seen:
            fail(f"ZIP 中存在重复或大小写冲突路径：{name!r}")

        seen[key] = name

        mode = (item.external_attr >> 16) & 0o170000

        if mode == stat.S_IFLNK:
            fail(f"ZIP 中不允许符号链接：{name!r}")

        if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
            fail(f"ZIP 中存在特殊文件：{name!r}")

        destination = root.joinpath(*relative.parts)

        if is_dir:
            destination.mkdir(parents=True, exist_ok=True)
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            fail(f"解压目标已经存在：{name!r}")

        with zf.open(item, "r") as source:
            with destination.open("xb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)

manifest_path = root / "manifest.json"

if not manifest_path.is_file() or manifest_path.is_symlink():
    fail("知识库根目录缺少 manifest.json。")

try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    fail(f"无法读取知识库 manifest.json：{exc}")

if not isinstance(manifest, dict) or manifest.get("version") != knowledge_version:
    fail("知识库 manifest.json 版本不匹配。")

if not (root / "commands" / "platforms").is_dir():
    fail("缺少 commands/platforms 目录。")

files = []

for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
    if path.is_symlink():
        fail(f"知识库中存在符号链接：{path}")

    if path.is_dir():
        continue

    if not path.is_file():
        fail(f"知识库中存在非普通文件：{path}")

    relative = path.relative_to(root).as_posix()

    files.append({
        "path": relative,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    })

if not files:
    fail("知识库中没有文件。")

integrity = {
    "schema_version": 1,
    "main_version": main_version,
    "main_prerelease": main_prerelease,
    "knowledge_version": knowledge_version,
    "knowledge_archive_sha256": archive_sha256,
    "file_count": len(files),
    "files": files,
}

integrity_file.parent.mkdir(parents=True, exist_ok=True)
integrity_file.write_text(
    json.dumps(integrity, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print(f"知识库版本：{knowledge_version}")
print(f"知识库文件数：{len(files)}")
print(f"完整性清单：{integrity_file}")
PY

# ------------------------------------------------------------
# 5. PyInstaller 构建
# ------------------------------------------------------------

printf '\n[3/6] 使用 PyInstaller 构建 Linux 主程序...\n'

cd "$PROJECT_ROOT"

"$PYTHON" -m PyInstaller \
    --clean \
    --noconfirm \
    --distpath "$BUILD_ROOT/dist" \
    --workpath "$BUILD_ROOT/work" \
    "$SPEC_FILE"

APP_SOURCE="$BUILD_ROOT/dist/lcmd"

[[ -d "$APP_SOURCE" ]] ||
    fail "PyInstaller 没有生成预期的 one-dir 输出目录。"

[[ -x "$APP_SOURCE/lcmd" ]] ||
    fail "PyInstaller 输出中缺少可执行的 lcmd 主程序。"

# ------------------------------------------------------------
# 6. 组装并验证发行包
# ------------------------------------------------------------

printf '\n[4/6] 组装发行包...\n'

mkdir -p "$STAGE/app"

cp -a "$APP_SOURCE/." "$STAGE/app/"

cp "$PROJECT_ROOT/scripts/install.sh" "$STAGE/install.sh"
cp "$PROJECT_ROOT/scripts/uninstall.sh" "$STAGE/uninstall.sh"

chmod 755 "$STAGE/install.sh" "$STAGE/uninstall.sh"
chmod 755 "$STAGE/app/lcmd"

[[ -x "$STAGE/install.sh" ]] ||
    fail "发行包安装脚本没有执行权限。"

[[ -x "$STAGE/uninstall.sh" ]] ||
    fail "发行包卸载脚本没有执行权限。"

printf '\n[5/6] 验证发行包...\n'

VERSION_OUTPUT="$("$STAGE/app/lcmd" --version 2>&1)" ||
    fail "发行包主程序无法正常启动。"

printf '%s\n' "$VERSION_OUTPUT"

"$STAGE/app/lcmd" \
    --internal-validate-distribution \
    "$STAGE/knowledge" \
    "$STAGE/knowledge-integrity.json" ||
    fail "发行包知识库及完整性清单验证失败。"

"$STAGE/app/lcmd" \
    --internal-validate-knowledge \
    "$STAGE/knowledge" ||
    fail "发行包知识库结构验证失败。"

# ------------------------------------------------------------
# 7. 发布构建结果
# ------------------------------------------------------------

printf '\n[6/6] 发布构建结果...\n'

[[ ! -e "$OUTPUT_DIR" && ! -L "$OUTPUT_DIR" ]] ||
    fail "最终输出目录已存在，拒绝覆盖。"

mv -T -- "$STAGE" "$OUTPUT_DIR"

printf '\n%s\n' "============================================================"
printf '%s\n' "LCMD Linux 发行包构建成功。"
printf '%s\n' "============================================================"
printf '版本：%s-%s\n' "$MAIN_VERSION" "$MAIN_PRERELEASE"
printf '输出目录：%s\n' "$OUTPUT_DIR"
printf '\n发行包结构：\n'
find "$OUTPUT_DIR" -maxdepth 2 -mindepth 1 -printf '%M %P\n' | sort

printf '\n知识库 ZIP SHA-256：\n%s\n' "$ACTUAL_ARCHIVE_SHA256"
