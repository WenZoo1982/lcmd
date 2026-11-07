#!/usr/bin/env bash

# LCMD Linux 卸载程序
# 仅删除 LCMD 安装器管理的文件和目录；不需要 sudo。

set -Eeuo pipefail

DATA_DIR="${HOME}/.local/share/lcmd"
APP_DIR="${DATA_DIR}/app"
KNOWLEDGE_DIR="${DATA_DIR}/knowledge"
MARKER_FILE="${DATA_DIR}/.lcmd-install.json"
UNINSTALL_FILE="${DATA_DIR}/uninstall.sh"

CONFIG_DIR="${HOME}/.config/lcmd"
BIN_DIR="${HOME}/.local/bin"
COMMAND_LINK="${BIN_DIR}/lcmd"
UNINSTALL_LINK="${BIN_DIR}/lcmd-uninstall"

PROFILE_FILE="${HOME}/.profile"
PATH_BEGIN="# >>> LCMD PATH >>>"
PATH_END="# <<< LCMD PATH <<<"

fail() {
    printf '\nLCMD 卸载失败：%s\n' "$1" >&2
    printf '未继续执行后续删除操作。\n' >&2
    exit 1
}

section() {
    printf '\n========== %s ==========\n' "$1"
}

require_directory() {
    local path="$1"

    if [[ -L "$path" ]]; then
        fail "目录不能是符号链接：$path"
    fi

    if [[ -e "$path" && ! -d "$path" ]]; then
        fail "预期目录路径不是普通目录：$path"
    fi
}

require_regular_file() {
    local path="$1"

    if [[ -L "$path" ]]; then
        fail "文件不能是符号链接：$path"
    fi

    if [[ -e "$path" && ! -f "$path" ]]; then
        fail "预期文件路径不是普通文件：$path"
    fi
}

check_install_marker() {
    section "1/4 安装身份验证"

    require_regular_file "$MARKER_FILE"
    [[ -f "$MARKER_FILE" ]] ||
        fail "找不到 LCMD 安装身份标记，拒绝删除数据目录。"

    command -v python3 >/dev/null 2>&1 ||
        fail "系统缺少 python3，无法安全验证安装身份标记。"

    python3 - "$MARKER_FILE" "$DATA_DIR" "$APP_DIR" "$KNOWLEDGE_DIR" "$UNINSTALL_FILE" <<'PY'
import json
import os
import re
import stat
import sys

marker_file, data_dir, app_dir, knowledge_dir, uninstall_file = sys.argv[1:]

def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"安装标记包含重复字段：{key}")
        result[key] = value
    return result

try:
    data_stat = os.lstat(data_dir)
    marker_stat = os.lstat(marker_file)

    if not stat.S_ISDIR(data_stat.st_mode):
        raise ValueError("LCMD 数据路径不是普通目录。")
    if not stat.S_ISREG(marker_stat.st_mode):
        raise ValueError("安装标记不是普通文件。")

    with open(marker_file, "r", encoding="utf-8") as stream:
        data = json.load(stream, object_pairs_hook=reject_duplicate_keys)

    required = {
        "product", "marker_version", "main_version",
        "app_dir", "knowledge_dir", "uninstall_file", "install_state",
    }
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("安装标记字段不符合当前 Linux 安装格式。")
    if data["product"] != "WenZoo.LCMD":
        raise ValueError("安装标记产品标识不匹配。")
    version = data["marker_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise ValueError("安装标记版本不受支持。")
    if not isinstance(data["main_version"], str) or re.fullmatch(
        r"\d+\.\d+\.\d+", data["main_version"]
    ) is None:
        raise ValueError("安装标记中的主程序版本无效。")

    expected_paths = {
        "app_dir": app_dir,
        "knowledge_dir": knowledge_dir,
        "uninstall_file": uninstall_file,
    }
    for field, expected in expected_paths.items():
        if data[field] != expected:
            raise ValueError(f"安装标记中的管理路径不匹配：{field}")

    install_state = data["install_state"]
    if not isinstance(install_state, str) or install_state not in {
        "installing", "complete"
    }:
        raise ValueError("安装标记状态无效。")

except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
    print(f"LCMD_INSTALL_MARKER=ERROR\n安装标记验证失败：{exc}", file=sys.stderr)
    raise SystemExit(1)

print("LCMD_INSTALL_MARKER=OK")
PY
}

validate_managed_link() {
    local link="$1"
    local expected_target="$2"

    if [[ -e "$link" || -L "$link" ]]; then
        [[ -L "$link" ]] ||
            fail "命令入口被普通文件占用，拒绝删除：$link"

        local actual_target
        actual_target="$(readlink -- "$link")" ||
            fail "无法读取命令入口：$link"

        [[ "$actual_target" == "$expected_target" ]] ||
            fail "命令入口指向其他位置，拒绝删除：$link"
    fi
}

validate_profile() {
    require_regular_file "$PROFILE_FILE"

    [[ -f "$PROFILE_FILE" ]] || return 0

    # 只允许零个或一组完整、顺序正确的 LCMD PATH 标记。
    awk -v begin="$PATH_BEGIN" -v end="$PATH_END" '
        $0 == begin {
            if (inside || seen_begin) invalid=1
            inside=1
            seen_begin=1
            next
        }
        $0 == end {
            if (!inside || seen_end) invalid=1
            inside=0
            seen_end=1
            next
        }
        END {
            if (inside || seen_begin != seen_end || invalid) exit 2
        }
    ' "$PROFILE_FILE" ||
        fail "~/.profile 中的 LCMD PATH 配置块异常，拒绝修改。"
}

check_paths() {
    section "2/4 卸载路径安全检查"

    [[ -n "${HOME:-}" && "$HOME" == /* ]] ||
        fail "HOME 必须是有效的绝对路径。"

    for directory in \
        "$HOME" \
        "$HOME/.local" \
        "$HOME/.local/share" \
        "$DATA_DIR" \
        "$APP_DIR" \
        "$KNOWLEDGE_DIR" \
        "$HOME/.config" \
        "$CONFIG_DIR" \
        "$BIN_DIR"; do
        require_directory "$directory"
    done

    require_regular_file "$MARKER_FILE"
    require_regular_file "$UNINSTALL_FILE"
    require_regular_file "$PROFILE_FILE"

    [[ -d "$DATA_DIR" ]] ||
        fail "未找到 LCMD 数据目录，无法确认安装身份。"

    [[ -f "$MARKER_FILE" ]] ||
        fail "安装身份标记不存在，拒绝删除 LCMD 数据目录。"

    validate_managed_link "$COMMAND_LINK" "$APP_DIR/lcmd"
    validate_managed_link "$UNINSTALL_LINK" "$UNINSTALL_FILE"
    validate_profile

    printf '目录类型和命令入口检查通过。\n'
}

remove_profile_path() {
    section "3/4 清理 PATH 配置"

    [[ -f "$PROFILE_FILE" ]] || {
        printf '~/.profile 不存在，无需修改。\n'
        return
    }

    if ! grep -Fqx -- "$PATH_BEGIN" "$PROFILE_FILE"; then
        printf '未发现 LCMD PATH 配置块，不修改 ~/.profile。\n'
        return
    fi

    local profile_temp
    profile_temp="$(mktemp "${PROFILE_FILE}.lcmd.XXXXXX")" ||
        fail "无法创建 ~/.profile 临时文件。"

    if ! awk -v begin="$PATH_BEGIN" -v end="$PATH_END" '
        $0 == begin {
            inside=1
            next
        }
        $0 == end {
            inside=0
            next
        }
        !inside { print }
    ' "$PROFILE_FILE" > "$profile_temp"; then
        rm -f -- "$profile_temp"
        fail "无法生成清理后的 ~/.profile。"
    fi

    if ! chmod --reference="$PROFILE_FILE" "$profile_temp"; then
        rm -f -- "$profile_temp"
        fail "无法保留 ~/.profile 原有权限。"
    fi

    if ! mv -f -- "$profile_temp" "$PROFILE_FILE"; then
        rm -f -- "$profile_temp"
        fail "无法原子更新 ~/.profile。"
    fi

    printf '已移除 LCMD 自己添加的 PATH 配置块。\n'
}

remove_installation() {
    section "4/4 删除 LCMD 管理内容"

    if [[ -L "$COMMAND_LINK" ]]; then
        rm -f -- "$COMMAND_LINK" ||
            fail "无法删除 lcmd 命令入口。"
        printf '已删除命令入口：%s\n' "$COMMAND_LINK"
    fi

    if [[ -L "$UNINSTALL_LINK" ]]; then
        rm -f -- "$UNINSTALL_LINK" ||
            fail "无法删除 lcmd-uninstall 命令入口。"
        printf '已删除卸载命令入口：%s\n' "$UNINSTALL_LINK"
    fi

    if [[ -d "$CONFIG_DIR" ]]; then
        rm -rf -- "$CONFIG_DIR" ||
            fail "无法删除 LCMD 配置目录。"
        printf '已删除配置目录：%s\n' "$CONFIG_DIR"
    fi

    rm -rf -- "$DATA_DIR" ||
        fail "无法删除 LCMD 数据目录。"
    printf '已删除数据目录：%s\n' "$DATA_DIR"
}

main() {
    if [[ "$#" -ne 0 ]]; then
        fail "此命令不接受参数。"
    fi

    check_paths
    check_install_marker

    printf '\n即将删除以下 LCMD 管理内容：\n'
    printf '  %s\n' "$DATA_DIR"
    printf '  %s\n' "$CONFIG_DIR"
    printf '  %s\n' "$COMMAND_LINK"
    printf '  %s\n' "$UNINSTALL_LINK"
    printf '  ~/.profile 中的 LCMD PATH 配置块（如果存在）\n'

    local answer
    if ! read -r -p $'确认卸载 LCMD？[y/N] ' answer; then
        printf '\n无法读取确认输入，已取消卸载。\n'
        exit 0
    fi

    case "$answer" in
        y|Y|yes|YES|Yes)
            ;;
        *)
            printf '已取消卸载。\n'
            exit 0
            ;;
    esac

    remove_profile_path
    remove_installation

    printf '\n========================================\n'
    printf 'LCMD 已成功卸载。\n'
    printf '========================================\n'
}

main "$@"
