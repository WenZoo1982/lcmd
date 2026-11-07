# LCMD

**LCMD（多平台命令速查与学习工具）** 是一个离线命令参考工具，帮助用户快速查找命令用途、常用参数和实际示例。

> 核心理念：少记忆，易理解；需要时快速查找。
>
> **LCMD 只查询和展示知识库内容，不会替用户执行系统命令。**

## 项目仓库

- **主程序仓库**：<https://github.com/WenZoo1982/lcmd>
- **官方知识库**：<https://github.com/WenZoo1982/lcmd-kb>
- **版本与安装包**：<https://github.com/WenZoo1982/lcmd/releases>

LCMD 主程序与知识库分开维护。主程序负责命令行交互、知识库加载和搜索；知识库仓库负责维护命令参考文档。用户也可以按知识库格式添加自己的命令文档，无需修改主程序源码。

## 当前状态

项目目前处于 **Beta 测试阶段**。Windows 和 Linux 安装包将在 GitHub Releases 中分别提供。测试版适合体验和反馈，不建议将其视为长期稳定版本。

## 功能概览

- 离线读取本地 Markdown 知识库，不依赖在线查询服务。
- 支持 Windows 和 Linux 平台命令参考。
- 收录 Git、Docker、SSH 等常用命令行工具文档。
- 提供中文（`zh-CN`）和英文（`en-US`）知识库内容。
- 支持按命令路径直接查询，也支持关键词搜索。
- 支持使用符合目录结构和文档格式要求的自定义知识库。
- 只展示命令说明，不执行命令，也不修改系统状态。

## 系统要求

| 平台 | 当前安装包支持范围 |
|---|---|
| Windows | Windows x64；安装脚本要求 Windows PowerShell 5.1 或更高版本 |
| Linux | x86_64；Linux Mint 22.x 或 Ubuntu 24.04 LTS |

发行包已经包含可运行的主程序和官方知识库，普通用户无需预先安装 Python。Linux 安装为当前用户级安装，不需要 `sudo`。

## 下载与安装

从 [GitHub Releases](https://github.com/WenZoo1982/lcmd/releases) 下载与你的系统和架构匹配的发行包。下载后先解压，再运行发行包根目录中的安装脚本。

### Windows

1. 下载 Windows x64 发行包并解压。
2. 在解压后的发行包目录打开 PowerShell。
3. 运行安装脚本：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

安装器会将主程序固定安装到 `%LOCALAPPDATA%\Programs\LCMD`，将官方知识库和配置放在 `%LOCALAPPDATA%\lcmd` 下，并配置当前用户的 PATH。无需管理员权限。

### Linux

当前 Linux 安装包支持 Linux Mint 22.x 和 Ubuntu 24.04 LTS（x86_64）。

1. 下载 Linux 发行包并解压。
2. 在终端进入解压后的发行包目录。
3. 运行安装脚本：

```bash
./install.sh
```

安装器会将 LCMD 安装到当前用户目录，不需要 `sudo`。安装完成后，重新打开终端，或执行：

```bash
source ~/.profile
```

### 验证安装

安装完成后，在新终端运行：

```bash
lcmd --version
lcmd --help
```

## 基本使用

直接输入命令路径即可查询对应文档：

```bash
lcmd git init
lcmd docker compose up
```

使用 `search` 按关键词查找知识库内容：

```bash
lcmd search 文件
lcmd search 网络
```

查看主帮助和搜索子命令帮助：

```bash
lcmd --help
lcmd search --help
```

查询结果来自本地知识库。LCMD 不会执行示例中的命令；是否执行以及如何执行，均由用户自行判断。

## 安装位置与配置

| 内容 | Windows | Linux |
|---|---|---|
| 主程序 | `%LOCALAPPDATA%\Programs\LCMD` | `~/.local/share/lcmd/app` |
| 官方知识库 | `%LOCALAPPDATA%\lcmd\knowledge` | `~/.local/share/lcmd/knowledge` |
| 配置文件 | `%LOCALAPPDATA%\lcmd\config.toml` | `~/.config/lcmd/config.toml` |
| 命令入口 | 用户 PATH | `~/.local/bin/lcmd` |

安装器会根据目标平台初始化 `platform`，并根据系统语言初始化 `language`。CLI 帮助语言与知识库查询语言是独立设置。

**重新运行新版安装脚本即执行升级。** 安装器以当前发行包为准重新部署主程序和官方知识库，并重新生成默认配置；此前的配置修改不会自动保留。升级前请先记录自己需要保留的配置。

## 卸载

卸载会删除 LCMD 安装器管理的主程序、官方知识库、配置和命令入口，并移除安装器添加的 PATH 配置；不会主动删除放在 LCMD 管理目录以外的自定义知识库。

### Windows

在 PowerShell 中运行已安装目录内的卸载脚本：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\LCMD\uninstall.ps1"
```

按照卸载器提示确认。卸载器会检查安装身份后再执行清理，并从当前用户 PATH 中移除 LCMD 安装目录。

### Linux

运行：

```bash
lcmd-uninstall
```

按照提示输入 `y` 确认卸载。卸载器不需要 `sudo`，会删除 `~/.local/share/lcmd/`、`~/.config/lcmd/`、LCMD 的两个命令入口，并移除安装器自行添加到 `~/.profile` 的 PATH 配置块。

## 知识库与自定义扩展

官方知识库当前包含 **300 个命令参考条目、600 篇 Markdown 文档**，中文和英文各 300 篇。覆盖 Linux、Windows、Docker、Git 和 SSH。

你可以复制官方知识库作为自己的知识库，在规定目录中添加 Markdown 文档，并让 LCMD 使用该知识库。目录层级、语言目录、文件命名和 TOML Front Matter 格式必须符合要求。

- **知识库仓库与详细格式说明**：<https://github.com/WenZoo1982/lcmd-kb>
- **知识库 README**：<https://github.com/WenZoo1982/lcmd-kb#readme>

## 反馈与问题

欢迎通过主程序仓库的 [Issues](https://github.com/WenZoo1982/lcmd/issues) 反馈安装问题、查询问题、文档错误或功能建议。提交问题时，请尽量附上操作系统、LCMD 版本、执行的查询命令和完整错误信息。

## 开发环境

- Python 3.11 或更高版本
- Git

在仓库根目录创建虚拟环境并安装开发依赖：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
```

项目架构、开发阶段和实际进度统一记录在 `LCMD-DEV.md`。