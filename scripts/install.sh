#!/usr/bin/env bash

# LCMD Linux 统一安装程序
# 支持：Linux Mint 22.x、Ubuntu 24.04 LTS
# 架构：x86_64
# 安装方式：当前用户级，无需 sudo

set -Eeuo pipefail

PRODUCT_ID="WenZoo.LCMD"
MARKER_VERSION="1"

PACKAGE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

DATA_DIR="${HOME}/.local/share/lcmd"
APP_DIR="${DATA_DIR}/app"
KNOWLEDGE_DIR="${DATA_DIR}/knowledge"
MARKER_FILE="${DATA_DIR}/.lcmd-install.json"
MARKER_TEMP_FILE="${MARKER_FILE}.tmp"
UNINSTALL_FILE="${DATA_DIR}/uninstall.sh"

CONFIG_DIR="${HOME}/.config/lcmd"
CONFIG_FILE="${CONFIG_DIR}/config.toml"

BIN_DIR="${HOME}/.local/bin"
COMMAND_LINK="${BIN_DIR}/lcmd"
UNINSTALL_LINK="${BIN_DIR}/lcmd-uninstall"

PROFILE_FILE="${HOME}/.profile"
PATH_BEGIN="# >>> LCMD PATH >>>"
PATH_END="# <<< LCMD PATH <<<"

APP_SOURCE="${PACKAGE_ROOT}/app"
KNOWLEDGE_SOURCE="${PACKAGE_ROOT}/knowledge"
INTEGRITY_FILE="${PACKAGE_ROOT}/knowledge-integrity.json"
UNINSTALL_SOURCE="${PACKAGE_ROOT}/uninstall.sh"

fail() {
    printf '\nLCMD 安装失败：%s\n' "$1" >&2
    printf 'INSTALL_RESULT=ERROR\n' >&2
    printf '本版本不提供自动回滚；修正问题后重新运行 ./install.sh 即可。\n' >&2
    exit 1
}

section() {
    printf '\n========== %s ==========\n' "$1"
}

require_directory_not_symlink() {
    local path="$1"

    if [[ -L "$path" ]]; then
        fail "路径不能是符号链接：$path"
    fi
}

require_file_not_symlink() {
    local path="$1"

    if [[ -L "$path" ]]; then
        fail "文件不能是符号链接：$path"
    fi
}

check_platform() {
    section "1/7 系统环境检查"

    [[ -r /etc/os-release ]] || fail "无法读取 /etc/os-release。"

    # shellcheck disable=SC1091
    source /etc/os-release

    local architecture
    architecture="$(uname -m)"

    [[ "$architecture" == "x86_64" ]] ||
        fail "当前仅支持 x86_64 架构，检测到：$architecture"

    case "${ID:-}" in
        linuxmint)
            [[ "${VERSION_ID:-}" =~ ^22(\.|$) ]] ||
                fail "仅支持 Linux Mint 22.x，检测到：${VERSION_ID:-未知}"
            ;;
        ubuntu)
            [[ "${VERSION_ID:-}" == "24.04" ]] ||
                fail "仅支持 Ubuntu 24.04 LTS，检测到：${VERSION_ID:-未知}"
            ;;
        *)
            fail "不支持当前 Linux 发行版：${PRETTY_NAME:-未知}"
            ;;
    esac

    printf '操作系统：%s\n' "${PRETTY_NAME:-未知}"
    printf 'CPU 架构：%s\n' "$architecture"
    printf '安装用户：%s\n' "$USER"
}

check_package() {
    section "2/7 发行包检查"

    require_directory_not_symlink "$APP_SOURCE"
    require_directory_not_symlink "$KNOWLEDGE_SOURCE"

    [[ -d "$APP_SOURCE" ]] ||
        fail "发行包缺少 app 目录。"

    [[ -x "$APP_SOURCE/lcmd" ]] ||
        fail "主程序不存在或没有执行权限：app/lcmd"

    [[ -d "$APP_SOURCE/_internal" ]] ||
        fail "主程序缺少 _internal 目录。"

    [[ -d "$KNOWLEDGE_SOURCE" ]] ||
        fail "发行包缺少 knowledge 目录。"

    [[ -s "$KNOWLEDGE_SOURCE/manifest.json" ]] ||
        fail "知识库缺少 manifest.json。"

    require_file_not_symlink "$INTEGRITY_FILE"
    [[ -f "$INTEGRITY_FILE" && -s "$INTEGRITY_FILE" ]] ||
        fail "发行包缺少有效的 knowledge-integrity.json 普通文件。"

    require_file_not_symlink "$UNINSTALL_SOURCE"
    [[ -f "$UNINSTALL_SOURCE" ]] ||
        fail "发行包缺少 uninstall.sh。"

    [[ -x "$UNINSTALL_SOURCE" ]] ||
        fail "uninstall.sh 没有执行权限。"

    # app 目录不在知识库 SHA-256 清单范围内，必须单独拒绝符号链接和特殊文件。
    local unsafe_entry
    unsafe_entry="$(
        find "$APP_SOURCE" -mindepth 1 ! -type d ! -type f -print -quit
    )" || fail "无法检查 app 目录中的文件类型。"

    [[ -z "$unsafe_entry" ]] ||
        fail "app 目录中存在符号链接或特殊文件，拒绝部署：$unsafe_entry"

    local version_output
    version_output="$("$APP_SOURCE/lcmd" --version 2>&1)" ||
        fail "无法执行发行包中的 LCMD 主程序。"

    local main_version
    main_version="$(
        printf '%s\n' "$version_output" |
        sed -nE 's/^LCMD[：:] *([0-9]+\.[0-9]+\.[0-9]+).*$/\1/p' |
        head -n 1
    )"

    [[ -n "$main_version" ]] ||
        fail "无法识别 LCMD 主程序版本。"

    printf '主程序版本：%s\n' "$main_version"

    # 在正式清理旧安装之前，验证知识库文件集合、大小和 SHA-256。
    # 此检查同时验证 knowledge-integrity.json 与知识库 manifest.json。
    local distribution_output
    distribution_output="$(
        "$APP_SOURCE/lcmd" \
            --internal-validate-distribution \
            "$KNOWLEDGE_SOURCE" \
            "$INTEGRITY_FILE" 2>&1
    )" || {
        printf '%s\n' "$distribution_output" >&2
        fail "发行包完整性验证失败。"
    }

    printf '%s\n' "$distribution_output"

    grep -Fxq 'LCMD_INSTALL_DISTRIBUTION=OK' <<< "$distribution_output" ||
        fail "发行包完整性验证未返回成功标记。"

    local integrity_main_version
    integrity_main_version="$(
        printf '%s\n' "$distribution_output" |
        sed -nE 's/^\{"main_version":[[:space:]]*"([0-9]+\.[0-9]+\.[0-9]+)".*$/\1/p' |
        head -n 1
    )"

    [[ -n "$integrity_main_version" ]] ||
        fail "无法从完整性清单中读取主程序版本。"

    [[ "$integrity_main_version" == "$main_version" ]] ||
        fail "主程序版本与发行完整性清单不一致：程序 $main_version，清单 $integrity_main_version。"

    MAIN_VERSION="$main_version"
}

check_existing_installation() {
    section "3/7 原有安装检查"

    # 检查所有可能参与删除或写入的目录层级，避免父目录符号链接重定向操作。
    for directory in \
        "$HOME" \
        "$HOME/.local" \
        "$HOME/.local/share" \
        "$DATA_DIR" \
        "$HOME/.config" \
        "$CONFIG_DIR" \
        "$BIN_DIR"; do
        require_directory_not_symlink "$directory"
        if [[ -e "$directory" ]]; then
            [[ -d "$directory" ]] ||
                fail "预期目录路径实际不是目录：$directory"
        fi
    done

    if [[ -e "$DATA_DIR" ]]; then
        [[ -d "$DATA_DIR" ]] ||
            fail "LCMD 数据路径存在，但不是目录。"

        if [[ -e "$MARKER_FILE" || -L "$MARKER_FILE" ]]; then
            "$APP_SOURCE/lcmd" \
                --internal-validate-install-marker \
                "$MARKER_FILE" \
                "$DATA_DIR" ||
                fail "原有 LCMD 安装身份标记验证失败。"

            printf '检测到有效 LCMD 安装标记。\n'
        fi

        # 原子写入标记时若上次中断，允许清理唯一的临时标记文件后重试。
        if [[ -e "$MARKER_TEMP_FILE" || -L "$MARKER_TEMP_FILE" ]]; then
            require_file_not_symlink "$MARKER_TEMP_FILE"
            [[ -f "$MARKER_TEMP_FILE" ]] ||
                fail "安装标记临时路径不是普通文件。"
            rm -f -- "$MARKER_TEMP_FILE" ||
                fail "无法清理上次安装遗留的临时标记。"
        fi

        if [[ ! -e "$MARKER_FILE" ]]; then
            if [[ -n "$(find "$DATA_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
                fail "LCMD 数据目录存在非安装器临时文件，但缺少有效安装标记，拒绝删除。"
            fi
        fi

        # 检查旧安装中由 LCMD 管理的目标路径，拒绝符号链接或类型异常。
        for directory in "$APP_DIR" "$KNOWLEDGE_DIR"; do
            require_directory_not_symlink "$directory"
            if [[ -e "$directory" ]]; then
                [[ -d "$directory" ]] ||
                    fail "LCMD 管理目录不是普通目录：$directory"
            fi
        done

        if [[ -e "$UNINSTALL_FILE" || -L "$UNINSTALL_FILE" ]]; then
            require_file_not_symlink "$UNINSTALL_FILE"
            [[ -f "$UNINSTALL_FILE" ]] ||
                fail "LCMD 卸载脚本路径不是普通文件。"
        fi
    else
        printf '未检测到原有 LCMD 数据目录。\n'
    fi

    # 命令入口如果是普通文件或指向其他位置的符号链接，不覆盖。
    for link in "$COMMAND_LINK" "$UNINSTALL_LINK"; do
        if [[ -e "$link" || -L "$link" ]]; then
            [[ -L "$link" ]] ||
                fail "命令入口已被非符号链接文件占用：$link"

            local target
            target="$(readlink "$link")"

            case "$link" in
                "$COMMAND_LINK")
                    [[ "$target" == "$APP_DIR/lcmd" ]] ||
                        fail "lcmd 命令入口指向其他位置，拒绝覆盖。"
                    ;;
                "$UNINSTALL_LINK")
                    [[ "$target" == "$UNINSTALL_FILE" ]] ||
                        fail "lcmd-uninstall 命令入口指向其他位置，拒绝覆盖。"
                    ;;
            esac
        fi
    done

    if [[ -e "$PROFILE_FILE" ]]; then
        require_file_not_symlink "$PROFILE_FILE"
        [[ -f "$PROFILE_FILE" ]] ||
            fail "~/.profile 不是普通文件。"
    fi
}

detect_language() {
    local system_language
    system_language="${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}"

    case "${system_language,,}" in
        zh|zh_*|zh-*|zh.*)
            DETECTED_LANGUAGE="zh-CN"
            ;;
        *)
            DETECTED_LANGUAGE="en-US"
            ;;
    esac

    printf '检测到系统语言：%s\n' "$DETECTED_LANGUAGE"
}

deploy_files() {
    section "4/7 主程序和知识库部署"

    mkdir -p "$DATA_DIR" ||
        fail "无法创建 LCMD 数据目录。"

    # 先写入 installing 标记，再清理和部署受管理目录。
    # 即使部署中断，重新运行安装器也能识别这是一次未完成的 LCMD 安装。
    write_install_marker "installing"

    for directory in "$APP_DIR" "$KNOWLEDGE_DIR"; do
        if [[ -e "$directory" ]]; then
            rm -rf -- "$directory" ||
                fail "无法清理原有 LCMD 管理目录：$directory"
        fi
    done

    if [[ -e "$UNINSTALL_FILE" ]]; then
        rm -f -- "$UNINSTALL_FILE" ||
            fail "无法清理原有 LCMD 卸载脚本。"
    fi

    mkdir -p "$APP_DIR" "$KNOWLEDGE_DIR" ||
        fail "无法创建程序或知识库目录。"

    cp -a "$APP_SOURCE/." "$APP_DIR/" ||
        fail "主程序复制失败。"

    cp -a "$KNOWLEDGE_SOURCE/." "$KNOWLEDGE_DIR/" ||
        fail "知识库复制失败。"

    cp "$UNINSTALL_SOURCE" "$UNINSTALL_FILE" ||
        fail "卸载脚本复制失败。"

    chmod +x "$APP_DIR/lcmd" "$UNINSTALL_FILE" ||
        fail "设置程序执行权限失败。"

    printf '主程序部署完成。\n'
    printf '官方知识库部署完成。\n'
    printf '卸载脚本部署完成。\n'

    "$APP_DIR/lcmd" \
        --internal-validate-knowledge "$KNOWLEDGE_DIR" ||
        fail "部署后的知识库验证失败。"

    printf '知识库结构验证通过。\n'
}

initialize_config() {
    section "5/7 配置初始化"

    # 只删除 LCMD 自己的配置文件，不递归删除配置目录中的其他用户文件。
    if [[ -e "$CONFIG_FILE" || -L "$CONFIG_FILE" ]]; then
        require_file_not_symlink "$CONFIG_FILE"
        [[ -f "$CONFIG_FILE" ]] ||
            fail "原有配置路径不是普通文件。"
        rm -f -- "$CONFIG_FILE" ||
            fail "无法清理原有 LCMD 配置文件。"
    fi

    mkdir -p "$CONFIG_DIR" ||
        fail "无法创建配置目录。"

    "$APP_DIR/lcmd" \
        --internal-initialize-config \
        "$KNOWLEDGE_DIR" \
        "linux" \
        "$DETECTED_LANGUAGE" \
        "$CONFIG_FILE" ||
        fail "LCMD 配置初始化失败。"

    "$APP_DIR/lcmd" \
        --internal-validate-config "$CONFIG_FILE" ||
        fail "LCMD 配置验证失败。"

    printf '配置初始化成功。\n'
    printf '配置文件：%s\n' "$CONFIG_FILE"
    printf '平台：linux\n'
    printf '语言：%s\n' "$DETECTED_LANGUAGE"
}

configure_path() {
    section "6/7 PATH 环境变量配置"

    mkdir -p "$BIN_DIR" ||
        fail "无法创建 ~/.local/bin。"

    require_directory_not_symlink "$BIN_DIR"

    # 仅当当前 PATH 尚未包含 ~/.local/bin 时，才修改 ~/.profile。
    # 使用受管理配置块，并通过临时文件原子替换，避免重复追加或写入半截。
    case ":${PATH:-}:" in
        *":$BIN_DIR:"*)
            printf '当前 PATH 已包含 ~/.local/bin，无需修改 ~/.profile。\n'
            ;;
        *)
            local profile_temp="${PROFILE_FILE}.lcmd-tmp"

            if [[ -e "$profile_temp" || -L "$profile_temp" ]]; then
                require_file_not_symlink "$profile_temp"
                [[ -f "$profile_temp" ]] ||
                    fail "~/.profile 临时路径不是普通文件。"
                rm -f -- "$profile_temp" ||
                    fail "无法清理上次遗留的 PATH 临时文件。"
            fi

            if [[ -e "$PROFILE_FILE" ]]; then
                if grep -Fq "$PATH_BEGIN" "$PROFILE_FILE" ||
                    grep -Fq "$PATH_END" "$PROFILE_FILE"; then
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
                        !inside { print }
                        END {
                            if (inside || seen_begin != seen_end || invalid) exit 2
                        }
                    ' "$PROFILE_FILE" > "$profile_temp" ||
                        fail "~/.profile 中的 LCMD PATH 配置块结构异常，拒绝修改。"
                else
                    cp -p -- "$PROFILE_FILE" "$profile_temp" ||
                        fail "无法准备 ~/.profile 临时文件。"
                fi
                chmod --reference="$PROFILE_FILE" "$profile_temp" ||
                    fail "无法保留 ~/.profile 原有权限。"
            else
                : > "$profile_temp" ||
                    fail "无法创建 ~/.profile 临时文件。"
                chmod 600 "$profile_temp" ||
                    fail "无法设置 ~/.profile 临时文件权限。"
            fi

            if ! cat >> "$profile_temp" <<'EOF'

# >>> LCMD PATH >>>
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) PATH="$HOME/.local/bin:$PATH" ;;
esac
export PATH
# <<< LCMD PATH <<<
EOF
            then
                fail "无法写入 LCMD PATH 配置。"
            fi

            mv -f -- "$profile_temp" "$PROFILE_FILE" ||
                fail "无法原子更新 ~/.profile。"
            ;;
    esac

    # 重新创建两个由 LCMD 管理的命令入口。
    ln -sfn "$APP_DIR/lcmd" "$COMMAND_LINK" ||
        fail "创建 lcmd 命令入口失败。"

    ln -sfn "$UNINSTALL_FILE" "$UNINSTALL_LINK" ||
        fail "创建 lcmd-uninstall 命令入口失败。"

    printf '~/.local/bin 已配置。\n'
    printf '~/.profile PATH 配置完成。\n'
}

write_install_marker() {
    local install_state="${1:-complete}"

    if [[ -e "$MARKER_TEMP_FILE" || -L "$MARKER_TEMP_FILE" ]]; then
        require_file_not_symlink "$MARKER_TEMP_FILE"
        [[ -f "$MARKER_TEMP_FILE" ]] ||
            fail "安装标记临时路径不是普通文件。"
        rm -f -- "$MARKER_TEMP_FILE" ||
            fail "无法清理旧的安装标记临时文件。"
    fi

    cat > "$MARKER_TEMP_FILE" <<EOF
{
  "product": "$PRODUCT_ID",
  "marker_version": $MARKER_VERSION,
  "main_version": "$MAIN_VERSION",
  "app_dir": "$APP_DIR",
  "knowledge_dir": "$KNOWLEDGE_DIR",
  "uninstall_file": "$UNINSTALL_FILE",
  "install_state": "$install_state"
}
EOF

    [[ -s "$MARKER_TEMP_FILE" ]] ||
        fail "安装身份标记临时文件写入失败。"

    chmod 600 "$MARKER_TEMP_FILE" ||
        fail "设置安装身份标记权限失败。"

    mv -f -- "$MARKER_TEMP_FILE" "$MARKER_FILE" ||
        fail "无法原子写入安装身份标记。"
}

verify_installation() {
    section "7/7 安装结果验证"

    [[ -x "$APP_DIR/lcmd" ]] ||
        fail "安装后的主程序不存在。"

    [[ -d "$APP_DIR/_internal" ]] ||
        fail "安装后的主程序依赖目录不存在。"

    [[ -f "$KNOWLEDGE_DIR/manifest.json" ]] ||
        fail "安装后的知识库不存在。"

    [[ -f "$CONFIG_FILE" ]] ||
        fail "安装后的配置文件不存在。"

    [[ -L "$COMMAND_LINK" ]] ||
        fail "lcmd 命令入口创建失败。"

    [[ -L "$UNINSTALL_LINK" ]] ||
        fail "lcmd-uninstall 命令入口创建失败。"

    "$APP_DIR/lcmd" --internal-validate-knowledge "$KNOWLEDGE_DIR" ||
        fail "最终知识库验证失败。"

    "$APP_DIR/lcmd" --internal-validate-config "$CONFIG_FILE" ||
        fail "最终配置验证失败。"

    "$APP_DIR/lcmd" \
        --internal-validate-install-marker \
        "$MARKER_FILE" \
        "$DATA_DIR" ||
        fail "最终安装身份标记验证失败。"

    "$APP_DIR/lcmd" --version ||
        fail "最终主程序运行验证失败。"

    printf '\n安装目录：%s\n' "$DATA_DIR"
    printf '知识库目录：%s\n' "$KNOWLEDGE_DIR"
    printf '配置文件：%s\n' "$CONFIG_FILE"
    printf '命令入口：%s\n' "$COMMAND_LINK"
    printf '卸载命令：%s\n' "$UNINSTALL_LINK"
}

main() {
    check_platform
    check_package
    check_existing_installation
    detect_language
    deploy_files
    initialize_config
    configure_path
    write_install_marker
    verify_installation

    printf '\n========================================\n'
    printf 'LCMD 安装成功！\n'
    printf '========================================\n'
    printf '请重新打开终端，或执行：\n'
    printf 'source ~/.profile\n\n'
    printf '然后运行：\n'
    printf '  lcmd --help\n'
    printf '  lcmd-uninstall\n'
    printf '\nINSTALL_RESULT=OK\n'
}

main "$@"
