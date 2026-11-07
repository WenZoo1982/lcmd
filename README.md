# LCMD

**LCMD（多平台命令速查与学习工具）** 是一个离线命令参考工具，帮助用户快速查找命令用途、常用参数和实际示例。

> **少记忆，易理解；需要时快速查找。**
>
> LCMD 只查询和展示知识库内容，不会替用户执行系统命令。

## 项目仓库

- **主程序仓库**：<https://github.com/WenZoo1982/lcmd>
- **官方知识库仓库**：<https://github.com/WenZoo1982/lcmd-kb>
- **发行包与版本**：<https://github.com/WenZoo1982/lcmd/releases>

主程序与知识库分开维护：主程序负责命令行交互、知识库加载和搜索；知识库仓库负责维护命令参考文档。用户也可以按知识库格式添加自己的命令文档，无需修改主程序源码。

## 项目状态

项目目前处于 **Beta 测试阶段**。Windows 和 Linux 发行包以 GitHub Releases 页面实际发布的版本为准。测试版欢迎体验和反馈，暂不作为长期稳定版本承诺。

## 功能

- 离线读取本地 Markdown 知识库，不依赖在线查询服务。
- 支持 Windows 和 Linux 平台命令参考。
- 收录 Git、Docker、SSH 等常用命令行工具文档。
- 提供简体中文（`zh-CN`）和英文（`en-US`）知识库内容。
- 支持按命令路径直接查询，也支持关键词搜索。
- 支持使用符合目录结构和文档格式要求的自定义知识库。
- 只展示命令说明，不执行命令，也不修改系统状态。

## 知识库规模

当前官方知识库版本为 `0.1.0`，共包含 **300 个命令参考条目、600 篇 Markdown 文档**：

| 分类 | 条目数 | 中文文档 | 英文文档 |
|---|---:|---:|---:|
| Linux 平台命令 | 47 | 47 | 47 |
| Windows 平台命令 | 123 | 123 | 123 |
| Docker | 59 | 59 | 59 |
| Git | 62 | 62 | 62 |
| SSH | 9 | 9 | 9 |
| **合计** | **300** | **300** | **300** |

“条目数”按命令参考主题统计；每个条目各有一篇中文文档和一篇英文文档，不代表命令的所有参数组合或全部调用形式。详细目录与格式约束见[官方知识库 README](https://github.com/WenZoo1982/lcmd-kb#readme)。

## 系统要求

| 平台 | 当前发行包 |
|---|---|
| Windows | Windows x64 |
| Linux | Linux x86_64；已在 Linux Mint 22.3 环境完成安装验收 |

发行包包含可运行的主程序和官方知识库，普通用户无需预先安装 Python。Linux 安装为当前用户级安装，不需要 `sudo`。

## 下载与安装

从 [GitHub Releases](https://github.com/WenZoo1982/lcmd/releases) 下载与你的系统和架构匹配的发行包。下载后先解压，再运行发行包根目录中的安装脚本。

### Windows

1. 下载 Windows x64 发行包并解压。
2. 在解压后的发行包目录打开 PowerShell。
3. 执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

安装器会将主程序固定安装到 `%LOCALAPPDATA%\Programs\LCMD`，将官方知识库和配置放在 `%LOCALAPPDATA%\lcmd` 下，并配置当前用户的 PATH。无需管理员权限。

### Linux

1. 下载 Linux x86_64 发行包并解压。
2. 在终端进入解压后的发行包目录。
3. 执行：

```bash
./install.sh
```

安装器会将 LCMD 安装到当前用户目录，不需要 `sudo`。安装完成后，重新打开终端；如果当前终端尚未识别命令，可执行：

```bash
source ~/.profile
```

### 验证安装

在新终端运行：

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

使用 `search` 按关键词搜索知识库：

```bash
lcmd search 文件
lcmd search 网络
```

查看主帮助和搜索子命令帮助：

```bash
lcmd --help
lcmd search --help
```

查询结果来自本地知识库。LCMD 不会执行文档或示例中的命令；是否执行以及如何执行，均由用户自行判断。

## 安装位置与配置

| 内容 | Windows | Linux |
|---|---|---|
| 主程序 | `%LOCALAPPDATA%\Programs\LCMD` | `~/.local/share/lcmd/app` |
| 官方知识库 | `%LOCALAPPDATA%\lcmd\knowledge` | `~/.local/share/lcmd/knowledge` |
| 配置文件 | `%LOCALAPPDATA%\lcmd\config.toml` | `~/.config/lcmd/config.toml` |
| 命令入口 | 用户 PATH | `~/.local/bin/lcmd` |

安装器根据发行包目标平台初始化 `platform`，并根据系统语言初始化 `language`。CLI 帮助界面语言与知识库查询语言相互独立。

### 升级说明

重新运行新版发行包中的安装脚本即可升级。安装器以当前发行包为准重新部署主程序和官方知识库，并按当前安装包和系统重新生成默认配置；此前的配置修改不会自动保留。升级前请记录需要保留的自定义设置。

## 卸载

卸载会删除 LCMD 安装器管理的主程序、官方知识库、配置和命令入口，并移除安装器添加的 PATH 配置。放在 LCMD 管理目录以外的自定义知识库不会被主动删除。

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

按照提示输入 `y` 确认卸载。卸载器不需要 `sudo`，会删除 `~/.local/share/lcmd/`、`~/.config/lcmd/`、LCMD 的命令入口，并移除安装器自行添加到 `~/.profile` 的 PATH 配置块。

## 自定义知识库

你可以复制官方知识库作为自己的知识库，在规定目录中添加 Markdown 文档，并让 LCMD 使用该知识库。新增文档无需修改主程序源码，但目录层级、语言目录、文件命名和 TOML Front Matter 格式必须符合要求。

- **知识库仓库与扩展指南**：<https://github.com/WenZoo1982/lcmd-kb>
- **知识库 README（目录结构、文档格式与添加示例）**：<https://github.com/WenZoo1982/lcmd-kb#readme>

## 反馈与问题

欢迎通过主程序仓库的 [Issues](https://github.com/WenZoo1982/lcmd/issues) 反馈安装问题、查询问题、功能建议或主程序缺陷。提交问题时，请尽量附上操作系统、LCMD 版本、执行的查询命令和完整错误信息。

知识库内容问题请前往[知识库仓库](https://github.com/WenZoo1982/lcmd-kb)反馈。

## 开发环境

主程序要求 Python 3.11 或更高版本。创建并激活虚拟环境后，在仓库根目录安装开发依赖：

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

项目架构、开发阶段和实施进度统一记录在 `LCMD-DEV.md`。
