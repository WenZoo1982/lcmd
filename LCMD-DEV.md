# LCMD 项目开发总控文档

> 本文档是 LCMD 项目的唯一开发总控入口，统一记录项目要求、最终架构、程序逻辑、目录与文件职责、开发阶段和实际进度。
> 每次开始新对话先阅读本文档，再核对实际代码、测试和 Git 状态。计划不代表已实现；只有代码和测试验证支持的内容才能标记完成。

- 主程序仓库：WenZoo1982/lcmd
- 知识库仓库：WenZoo1982/lcmd-kb（已创建；知识库清单和正式内容尚未落地）
- 当前阶段：P2 知识库解析与管理（P1.1—P1.4、P2.1—P2.4 已完成并通过验收；P2.2—P2.4 代码已提交并推送至 GitHub）

---

## 1. 项目定位与开发要求

LCMD 是面向命令行用户的简体中文命令速查与学习工具。核心理念：少记忆，易理解；需要时快速查找。新手看得懂、理解得了、知道怎么用；有经验的用户查得快、找得准、用得上。LCMD 只提供知识查询，不执行系统命令。

### 内容原则

- 简洁、准确、容易理解、实用。
- 用途说明首先解释命令真正做什么，不为搜索堆砌词语。
- 参数精选；示例真实、可复制，并说明效果。
- 覆盖、删除、权限等操作提供必要风险提示。
- 每条命令只维护一份经过筛选的中文速查资料，重点是用途、基本语法、常用参数、常用示例及必要注意事项；这就是 LCMD 的核心内容，不另行编写或复制官方完整文档。
- 需要深入资料时提供对应官方文档入口；`--full`（如保留）只用于打开或提供官方资料，不代表 LCMD 维护第二套完整文档。
- 文档章节按命令特点组织，不强制机械模板。

### 搜索原则

知识内容优先，搜索是辅助。搜索应适应知识文档，不要求文档迎合搜索算法。

- 检索命令正式名称、用途说明和 Markdown 正文。
- 检索任务指南名称、用途说明和正文。
- 不设置 keywords、aliases 元数据字段。
- 知识库精确查询未命中时，使用当前操作系统的命令发现机制辅助判断该命令是否存在；该过程只查询系统命令信息，不执行用户输入的目标命令。
- 系统能够识别但知识库未收录时，明确告知“系统存在该命令，但 LCMD 知识库尚未收录”。系统也无法识别时，提示用户检查拼写或确认相关软件是否已安装；检测失败则明确说明无法判断，不把检测失败误报为命令不存在。
- 不自动改写用户输入、不自动执行命令，也不把知识库未收录等同于系统不存在。
- 不为提高匹配率扩写或重复用途说明，不承诺所有表达都能匹配。
- 命令名称查询不区分大小写；不改变操作系统命令本身的规则。

### 开发原则

- 一套主程序核心代码，按操作系统构建对应安装包。
- 主程序与知识库完全解耦、独立维护、独立发布和更新。
- 新增或修改知识文档，原则上不需要修改 Python 程序。
- 模块职责清楚，功能逐步实现并通过测试验收。
- 不增加没有实际价值的复杂功能。
- 开发状态以实际代码、测试结果和 Git 状态为准。

---

## 2. 最终产品架构与知识库

### 主程序和知识库关系

主程序负责 CLI、配置、知识库加载、解析、校验、查询、搜索、任务关联、终端输出和更新。知识库保存命令说明和任务指南，使用 Markdown + TOML Front Matter，维护者不需要懂 Python。

主程序和知识库独立发布，通过兼容协议和发布清单连接；命令资料不硬编码在主程序中。

### 知识库目录结构

```text
knowledge/
├── commands/
│   ├── linux/
│   │   ├── zh-CN/
│   │   └── en/
│   ├── windows/
│   │   ├── zh-CN/
│   │   └── en/
│   └── macos/
│       ├── zh-CN/
│       └── en/
└── tasks/
    ├── linux/
    │   ├── zh-CN/
    │   └── en/
    ├── windows/
    │   ├── zh-CN/
    │   └── en/
    └── macos/
        ├── zh-CN/
        └── en/
```

规则：

- 按平台、语言分目录；commands 和 tasks 分开。
- 一条命令一个 Markdown 文件，文件名就是正式命令名，例如 cp.md。
- 同名命令的不同实现可在同一文档中分别说明。
- 不设置别名映射；真实存在的命令按正式命令独立收录。
- Shell keywords、functions、aliases 不作为普通命令收录。
- 首发支持 PC Linux 常见 GNU 命令及 Bash 内建命令，不专门支持 BusyBox。
- 首发只有 zh-CN。中文知识库稳定后，在同一知识库仓库、同一 Release 中增加英文内容。
- 中英文文档属于同一命令/任务身份的不同语言内容。
- 任务指南按平台、语言分别编写，是人工维护的独立知识，不是自动生成的命令列表。
- 任务指南引用命令文档，不复制整篇命令说明；引用失效必须能被检查发现。
- 新增普通命令不要求自动修改任务指南。

### 命令文档内容

每条命令只维护一份 LCMD 中文速查资料：命令名称、适用平台及实现、用途说明、基本语法、精选常用参数、常用示例和必要注意事项。内容应经过筛选和解释，不能只是截断官方文档，也不写成冗长教程或完整参数百科。需要深入了解时提供对应官方文档入口；官方完整资料由其维护方负责，LCMD 不复制和维护。

### 知识库清单与平台兼容性

第一版 `manifest.json` 只保留一个字段：

```json
{
  "version": "2.0.0"
}
```

- `version`：知识库自身的 SemVer 版本。主程序也有自己的 SemVer 版本；两者只比较 Major 主版本号，Major 相同即兼容，Minor 和 Patch 不参与兼容性判断。
- Major 表示主程序与知识库的兼容基线；新增平台支持时，主程序和知识库同步提升 Major，并发布对应版本的知识库。其他会造成不兼容的知识库格式变化也必须提升 Major。
- Minor 用于增加命令资料或任务指南；Patch 用于修正已有资料。增加命令资料不要求升级主程序。
- 例如主程序 `2.0.0` 可以使用知识库 `2.0.0`、`2.1.0` 或 `2.5.3`；不能使用知识库 `1.9.0` 或 `3.0.0`。
- 知识库 Major 低于主程序 Major：提示必须更新知识库到当前主程序对应的 Major 系列。
- 知识库 Major 高于主程序 Major：提示必须升级主程序，不能让较旧主程序加载面向更新兼容基线的知识库。
- 主程序发布新的 Major 时，必须同步创建并发布相同 Major 的知识库 Release。知识库应建立新主程序支持的平台目录，即使新平台目录暂时为空或只包含部分命令，也可以正常发布。
- 平台能力由主程序自身决定；知识库通过 `commands/<platform>/<language>/` 和 `tasks/<platform>/<language>/` 实际目录组织资料。清单不维护平台列表，也不进行平台集合兼容判断。
- 某个平台目录为空、某条命令尚未收录或某个平台资料尚不完整，都不属于版本兼容错误。知识库版本 Major 匹配时允许正常加载；查询没有对应资料时，明确提示 LCMD 知识库尚未收录，不影响其他查询。
- 不设置 `platforms`、`manifest_version`、`schema_version` 或 `min_lcmd_version` 字段。当前没有实际需求支持这些额外字段。

### 元数据与 Schema

方向已确定为 TOML Front Matter + Markdown 正文。已明确不设置 keywords、aliases。命令名、平台、语言由目录和文件名推导，不重复存储。

#### P2.1 第一版 Schema 设计基线（已确认，验收时允许微调）

本设计作为 P2 实现和测试的起点；在 P2 验收时可根据真实文档和测试结果微调，修改后同步更新本总控文档。

- 命令文档 Front Matter：必填 `summary`，类型为非空字符串。
- 任务文档 Front Matter：必填 `summary`，类型为非空字符串；`commands` 为可选字符串数组，默认按空数组处理。
- `summary` 是一句简短的命令功能/用途说明或任务用途说明，供快速了解和摘要展示；不是关键词列表，也不需要罗列参数。
- Markdown 正文承载完整说明。命令正文按命令特点组织，通常包括基本语法、常用参数、使用示例和必要注意事项；不强制每篇文档使用完全相同的章节模板。
- 任务正文承载场景、操作步骤、示例和注意事项。`commands` 仅声明关联命令的正式名称，不复制命令文档内容。
- 命令名称、平台、语言继续从文件名及目录推导；不在 Front Matter 重复保存。
- 不设置 `keywords`、`aliases` 字段；第一版对未定义字段采用严格校验并报告错误。
- 文件使用 UTF-8 Markdown；第一行必须为独立的 `+++`，其后为 TOML，使用独立的 `+++` 结束 Front Matter，剩余内容作为 Markdown 正文。支持 LF 和 CRLF。
- Front Matter 缺失、TOML 语法错误、元数据不符合 Schema、正文为空或文件无法读取，均视为该文档无效。
- Parser 负责分离和解析 Front Matter / 正文；Validator 负责 Schema 校验；Knowledge Loader 负责发现、加载文档及汇总诊断，三者职责分离。
- 批量加载采用单文档错误隔离：无效文档跳过并记录文件路径和原因，其他有效文档继续加载。知识库根目录、清单或整体 Schema 兼容性等知识库级错误仍应终止加载。
- 当前第一版文档格式由主程序统一解析和校验；不在 `manifest.json` 或每篇 Markdown 中额外维护 `schema_version`。只有实际出现无法通过现有规则兼容的格式变化时，才重新评估兼容方案，不预先增加版本字段。
- 任务 `commands` 引用的存在性、平台/语言匹配及反向关联在 P5 实现；P2.1 先确定字段结构，不提前实现引用解析。

---

## 3. 配置、路径、平台与语言

### 用户配置

配置只保存两个核心值：

```toml
[knowledge]
platform = "windows"
language = "zh-CN"
```

程序根据这两个值推导 commands 和 tasks 目录，不在配置中重复保存路径。

### 默认知识库位置

- Windows：%LOCALAPPDATA%\lcmd\knowledge
- Linux：~/.local/share/lcmd/knowledge
- macOS：~/Library/Application Support/lcmd/knowledge

支持环境变量 LCMD_KNOWLEDGE_DIR 覆盖默认知识库根目录，优先级高于默认路径。显式指定路径不存在或缺少有效知识库清单时，明确报错并显示路径，不静默回退。不提供 --knowledge-dir CLI 参数。

### 平台和语言规则

- 安装包决定程序运行平台和初始默认知识平台。
- 安装时检测系统语言并预选；首发只有简体中文，其他语言回退 zh-CN。
- 安装后保存语言配置；启动时读取配置，不重复检测系统语言。
- 用户可手动切换平台和语言；切换前检查目标知识目录和兼容性，成功后保存配置并立即生效。
- 查询严格限定当前平台、语言目录，不跨目录搜索、不自动回退。
- 命令目录可用而任务目录为空时，仍允许命令查询。
- Windows 版可切换查询 Linux/macOS 知识；安装包只决定默认平台，不限制知识平台。
- WSL 用户应在 WSL 内安装 Linux 版 LCMD。
- Git Bash 不是完整 Linux，首发不提供专用安装包；Windows 版可切换查询 Linux 知识，必要时在文档注明差异。

命令建议：
- lcmd platform：查看当前平台
- lcmd platform linux：切换平台
- lcmd language：查看当前语言
- lcmd language en：切换语言

---

## 4. CLI 功能与程序实现逻辑

### 命令入口

| 命令 | 行为 |
|---|---|
| lcmd --help / -h | 显示帮助，不联网 |
| lcmd --version / -v | 显示主程序和当前知识库版本，不联网 |
| lcmd <command> | 精确查询当前平台、语言的命令 |
| lcmd <command> --full | 查看扩展官方资料 |
| lcmd search <keyword> | 搜索命令和任务知识 |
| lcmd task <task-name> | 查询任务指南 |
| lcmd platform [name] | 查看或切换平台 |
| lcmd language [name] | 查看或切换语言 |
| lcmd --update | 统一检查并更新主程序、知识库 |

普通查询不联网；更新使用 GitHub Releases。

### 启动和查询流程

1. CLI 接收参数并识别操作类型。
2. 读取用户配置，取得 platform 和 language。
3. 定位知识库根目录，读取并校验 `manifest.json` 的 `version`，将知识库 Major 与主程序 Major 比较，判断版本兼容性。
4. 推导当前命令目录、任务目录；目录或具体命令资料缺失时，在查询时明确提示未收录，不作为版本兼容错误。
5. 调用相应知识加载、解析和查询模块。
6. 将结果交给统一输出模块显示。

CLI 每次执行都是独立进程。当前实现仅在实际业务命令触发回调时读取配置、解析知识库根目录并验证根目录；`--help`、`--version` 和无参数帮助不执行该初始化。当前不启动后台服务，不扫描或解析 Markdown。索引是否持久化由实际规模和性能测试决定。

### 命令查询与系统命令发现

`lcmd cp` 根据当前平台、语言目录定位对应命令文档，解析并显示 LCMD 整理的中文速查内容。命令名不区分大小写，不改变操作系统命令本身的规则。

- 优先精确查询 LCMD 知识库；找到文档则直接显示，不需要查询系统命令信息。
- 知识库未找到时，再调用当前平台适用的系统命令发现机制，判断系统是否能够识别该命令；不得执行用户输入的目标命令。
- 系统能够识别：提示该命令在当前系统中存在，但 LCMD 尚未收录。
- 系统无法识别：提示可能是命令名称输入错误，或相关软件尚未安装；不自动修改命令名称、不猜测用户意图。
- 系统查询本身失败或不可用：明确提示无法完成系统识别，不将其当成“命令不存在”。
- Linux、Windows、macOS 分别采用适合各自平台的命令发现机制，并覆盖适用的可执行命令及 Shell 内建命令识别情况。系统发现机制只查询命令信息，不执行目标命令。

LCMD 始终只提供知识查询，不执行用户输入的系统命令。

### 内容搜索

搜索范围：
- 命令：正式命令名称、用途说明、Markdown 正文。
- 任务：任务名称、用途说明、Markdown 正文。

既定排序方向：
1. 命令名称完全匹配。
2. 用途说明匹配。
3. 正文匹配。

同等级按名称稳定排序。结果按命令、任务分组并标注平台。默认最多显示 10 条，支持 --limit；超出提示还有更多结果，不做复杂分页。中文检索实现和索引策略在 P4 通过实际测试确定。

### 任务指南与命令关联

任务指南说明场景、推荐命令、使用步骤、示例和注意事项。用户通过 lcmd task 主动查询；lcmd search 可同时返回命令和任务。任务文档引用命令文档，不复制完整内容；引用不存在或平台、语言不匹配时报告；支持从命令反向查询关联任务。不做自动智能推荐。

### 更新系统

- 主程序仓库：WenZoo1982/lcmd。
- 知识库仓库：WenZoo1982/lcmd-kb。
- 两者独立版本、独立 Release；统一通过 lcmd --update 检查。
- 使用 SemVer 2.0.0；主程序和知识库独立版本。
- 知识库 `manifest.json` 只记录 `version`。主程序版本和知识库版本均采用 SemVer，只比较 Major：Major 相同即可使用，Minor/Patch 更新知识库内容时不要求升级主程序；知识库 Major 低于主程序时必须更新知识库，高于主程序时必须升级主程序。主程序发布新 Major 时必须同步发布相同 Major 的知识库 Release。
- 知识库 Release 提供完整 ZIP、`manifest.json`、`SHA256SUMS.txt`；`manifest.json` 只包含知识库 `version`，不记录平台列表；哈希由实际发布文件计算。
- 发布清单使用私钥签名，客户端内置公钥验证；私钥不上传 GitHub。
- 更新前显示更新日志、覆盖警告、磁盘空间需求和可用空间；不足则取消，不清理用户文件。
- 下载、校验、构建、验证完成后再切换；失败组件保留旧版本并回滚。
- 两组件分别更新，不做跨组件事务；一个成功不要求另一个也成功。
- 知识库更新为完整覆盖，不合并用户文件；更新前提醒自定义内容会丢失并建议备份。
- 不支持断点续传；下载失败或中断后清理不完整文件，下次手动更新重新下载。
- 更新失败显示具体原因，不自动重试，不影响普通查询。
- 忽略版本分别记录；自动检查忽略版本时不提示，主动执行 --update 仍重新检查并询问。
- 只有成功后更新版本记录。记录两组件版本、上次更新时间、最近更新结果和忽略版本。
- 更新源固定 GitHub Releases，不提供普通用户自定义服务器。

---

## 5. 主程序目标目录与文件职责

以下是目标结构，不是当前仓库现状。实际开发可在不改变模块职责和外部行为的前提下调整文件拆分；调整后同步更新本文档。

```text
lcmd/
├── LCMD-DEV.md
├── pyproject.toml
├── README.md
├── src/
│   └── lcmd/
│       ├── __init__.py
│       ├── main.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── commands.py
│       │   ├── search.py
│       │   ├── tasks.py
│       │   ├── settings.py
│       │   └── update.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── paths.py
│       │   ├── knowledge.py
│       │   ├── parser.py
│       │   ├── validator.py
│       │   ├── search_engine.py
│       │   ├── task_resolver.py
│       │   └── index.py
│       ├── updater/
│       │   ├── __init__.py
│       │   ├── checker.py
│       │   ├── downloader.py
│       │   ├── verifier.py
│       │   ├── installer.py
│       │   └── rollback.py
│       └── output/
│           ├── __init__.py
│           └── renderer.py
└── tests/
    ├── test_cli.py
    ├── test_config.py
    ├── test_paths.py
    ├── test_parser.py
    ├── test_validator.py
    ├── test_commands.py
    ├── test_search.py
    ├── test_tasks.py
    └── updater/
```

### 文件职责

| 文件/目录 | 职责 |
|---|---|
| main.py | 程序启动入口 |
| cli/app.py | 创建 Typer 应用、注册 CLI 命令 |
| cli/commands.py | 命令查询入口和参数 |
| cli/search.py | 搜索命令入口 |
| cli/tasks.py | 任务指南查询入口 |
| cli/settings.py | 平台、语言查看与切换入口 |
| cli/update.py | 更新命令入口 |
| core/config.py | 用户配置读取、校验和保存 |
| core/paths.py | 计算配置、知识库根目录及当前平台语言目录 |
| knowledge/loader.py | 清单读取、主程序与知识库 Major 版本兼容检查、知识文档发现、解析、校验和加载诊断汇总 |
| core/parser.py | TOML Front Matter 和 Markdown 解析 |
| core/validator.py | Schema、元数据、文件名、引用、URL 校验 |
| core/search_engine.py | 命令与任务内容检索、排序 |
| core/task_resolver.py | 任务引用解析、有效性检查和反向关联 |
| core/index.py | 搜索索引接口和实现；持久化与否待性能测试 |
| updater/checker.py | Release、版本和兼容性检查 |
| updater/downloader.py | 下载更新包及临时文件管理 |
| updater/verifier.py | SHA256、签名和清单验证 |
| updater/installer.py | 更新安装、切换和版本记录 |
| updater/rollback.py | 更新失败回滚 |
| output/renderer.py | 统一终端输出样式和布局 |
| tests/ | 各模块自动化测试 |

CLI 只接收输入、分发业务并展示结果；核心模块负责业务逻辑，模块之间不重复实现职责。

---

## 6. P1 基础技术方案

以下方案已在 2026-10-31 确认，作为 P1 实施依据。具体依赖版本在创建项目时结合 Python 3.14 的兼容性核对后确定，不在规划阶段盲目固定版本。

### 开发环境基线

- 开发系统：Windows 11，PowerShell 5.1。
- 当前开发 Python：3.14.10。
- 本机另有 Python 3.10，但不作为新项目基准。
- 项目最低支持 Python：3.11。
- pip：26.2.2。
- Git：2.56.0.windows.2。
- 正式项目虚拟环境：`D:\Project_DEV\lcmd\.venv`，使用 Python 3.14.10；已验证可用。

### 技术选型

| 用途 | 技术 | 说明 |
|---|---|---|
| CLI 框架 | Typer | 组织主命令及后续子命令 |
| 终端显示 | Rich | 统一表格、颜色、错误和排版 |
| 用户目录 | platformdirs | 跨平台配置及数据目录定位 |
| 配置格式 | TOML | 用户配置文件格式 |
| TOML 读取 | tomllib | Python 3.11+ 标准库，无需额外依赖 |
| 构建后端 | setuptools | 配合 src-layout 和标准 Python 包构建 |
| 自动化测试 | pytest | 单元及 CLI 测试 |
| 代码检查与格式化 | Ruff | 统一 lint 和 format |

运行依赖：Typer、Rich、platformdirs。开发依赖：pytest、Ruff。尽量使用标准库；知识库解析、中文分词、网络更新、签名等后续阶段依赖不提前引入。

### P1 实际项目结构

P1 的目标结构按阶段逐步建立。以下列出截至 P1.4 已实际创建并纳入 Git 的文件。

```text
lcmd/
├── LCMD-DEV.md
├── README.md
├── pyproject.toml
├── .gitignore
├── src/
│   └── lcmd/
│       ├── __init__.py
│       ├── __main__.py
│       ├── main.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── app.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   └── paths.py
│       └── output/
│           ├── __init__.py
│           └── renderer.py
└── tests/
    ├── test_cli.py
    ├── test_config.py
    └── test_paths.py
```

| 模块 | 职责 |
|---|---|
| main.py、__main__.py | 程序入口及 python -m lcmd 启动 |
| cli/app.py | Typer 应用创建和 CLI 命令注册 |
| core/config.py | 用户配置读取、校验和保存 |
| core/paths.py | 默认知识库路径、环境变量覆盖、根目录验证及平台语言目录推导 |
| output/renderer.py | Rich 终端输出统一处理 |
| tests/test_cli.py、test_config.py、test_paths.py | CLI、配置和路径模块自动化测试 |

### P1 验收要求

- `lcmd --help` 和 `lcmd --version` 可用，不依赖知识库已安装或联网。
- `python -m lcmd` 可启动。
- 首次运行可创建默认配置；配置格式错误或字段值无效时给出明确错误。
- 正确计算 Windows、Linux、macOS 的默认路径。
- 支持 `LCMD_KNOWLEDGE_DIR` 覆盖知识库根目录，拒绝空值并解析相对路径。
- 验证知识库根目录存在且为目录；按配置推导 commands、tasks 平台语言目录，不自动创建目录。
- 错误提示清楚，不无故输出内部堆栈。
- pytest 全部通过，Ruff lint 和 format 检查通过。

### P1 子阶段

1. P1.1 项目骨架：目录、项目元数据、依赖、入口和开发工具配置。
2. P1.2 配置系统：TOML 读取、默认配置、校验和保存。
3. P1.3 路径系统：跨平台路径和环境变量覆盖。**已完成。**
4. P1.4 CLI 与验收：帮助、版本、错误处理和自动化测试。**已完成。**

每个子阶段完成后检查代码、测试结果和 Git 状态，再继续下一阶段。

---

## 7. 开发阶段与验收标准

| 阶段 | 主要任务 | 完成标准 |
|---|---|---|
| P0 项目规划与架构整理 | 总控文档、架构、模块职责、仓库基线核对 | 规划与实际状态清楚，可执行开发任务 |
| P1 主程序基础框架 | 包结构、CLI、配置、路径、帮助、版本、错误处理 | 程序能运行，正确读取配置并定位知识库 |
| P2 知识库解析与管理 | Schema、TOML/Markdown 解析、加载、校验、错误隔离 | 有效文档可加载，单份错误不拖垮整体 |
| P3 命令查询 | 精确查询、系统命令发现回退、格式化输出、官方资料入口（如保留 `--full`） | 通过真实知识文档查询；未收录时能区分系统可识别、不可识别和检测失败；不执行目标命令 |
| P4 搜索引擎 | 命令和任务搜索、排序、分组、数量限制 | 中英文检索测试通过，性能满足实际使用 |
| P5 任务指南 | 任务查询、命令引用、引用校验、反向关联 | 任务可独立查询，关联可靠 |
| P6 平台与语言管理 | 查看、切换、目录检查、安装初始选择 | 切换后配置正确保存并立即生效 |
| P7 独立更新系统 | Releases、清单、哈希、签名、兼容、空间、回滚 | 两组件独立更新，失败不破坏旧版本 |
| P8 测试、打包与发布 | 多平台打包、安装、升级、离线和异常测试 | 目标系统完整验收并可正式发布 |

每个阶段完成后记录实际完成内容、测试命令和结果、未解决问题、下一阶段入口。未通过验收不得标记完成。

---

## 8. 当前开发状态

### 当前阶段

**P0 — 项目规划与架构整理：已完成。**

**P1 — 主程序基础框架：已完成。** P1.1—P1.4 均已完成并推送至 GitHub。P1.4 完成 CLI 初始化接入、错误处理和自动化测试。

**P2 — 知识库解析与管理：进行中。** P2.1 Schema 设计基线已确认；P2.2 Front Matter Parser、P2.3 Schema Validator、P2.4 Knowledge Loader 均已完成并通过验收，代码已提交并推送至 GitHub `main`。下一步进入 P2 后续集成任务，开始前先核对实际代码与测试。

**正式项目重置：已完成。** 本地与 GitHub `main` 已同步到全新根提交 `538a922`（`chore: initialize clean LCMD project`），该提交只包含 `LCMD-DEV.md`。本地工作区干净；旧演示工程、虚拟环境、缓存和旧 Git 历史已从本地及新的 `main` 历史中清除。

P0 已完成产品定位、架构与模块职责规划、开发阶段划分、总控文档建立，以及原始仓库基线核对。原始演示代码和测试仅用于验证开发环境，不属于正式产品实现。

### 已确认的设计决策

- [x] 产品定位及简洁、易懂、实用的内容原则。
- [x] 主程序与知识库独立维护、独立更新。
- [x] 知识库按平台和语言组织，命令与任务分目录。
- [x] 配置只保存 platform、language，目录由程序推导。
- [x] 不设置 keywords、aliases 元数据字段。
- [x] 不自动改写命令名称或猜测用户意图；知识库未命中后，通过系统命令发现机制辅助判断，不执行目标命令。
- [x] 确定命令查询、内容搜索、任务指南、平台语言切换和统一更新入口。
- [x] 确定命令知识内容边界：每条命令只维护 LCMD 精简中文速查资料；完整资料指向官方文档，不复制维护官方完整文档。
- [x] 确定命令查询未命中策略：先查 LCMD 知识库，再通过当前操作系统命令发现机制判断；不执行用户输入的目标命令，并区分系统识别成功、未识别和检测失败。
- [x] 确定第一版 `manifest.json` 仅包含 `version`；主程序和知识库采用 SemVer，只比较 Major 主版本号判断兼容性，Minor/Patch 用于独立更新知识内容；新增平台支持时主程序与知识库同步提升 Major 并发布对应知识库。知识库平台目录可以为空或资料不完整，查询未收录内容时提示未收录，不作为兼容错误。
- [x] 确定单一总控文档作为项目开发上下文入口。
- [x] 决定清除原始演示工程，以最终产品架构为基础重新建立项目。
- [x] 决定保留 GitHub 仓库和本总控文档，但重新初始化 Git 提交历史。
- [x] 确认 P1 技术方案：Python 最低支持 3.11，当前使用 3.14.10；Typer、Rich、platformdirs；标准库 tomllib；setuptools；pytest、Ruff。
- [x] 确认 P1 最小项目结构和 P1.1—P1.4 子阶段。
- [x] 明确 P1.2 配置系统设计：使用 platformdirs 定位配置文件；TOML 保存 platform、language；首次运行创建默认配置；非法配置明确报错；保存采用同目录临时文件和原子替换。
- [x] 明确 P1.3 路径系统设计：默认数据目录、`LCMD_KNOWLEDGE_DIR` 覆盖、空值报错、相对路径解析、根目录验证，以及 commands/tasks 平台语言路径推导。
- [x] 明确 P1.4 CLI 初始化规则：实际业务命令触发时读取配置、解析并验证知识库根目录；帮助、版本和无参数帮助不依赖知识库。

### 原始仓库基线（2026-10-31，重置前）

原始仓库只有初始 Python/Typer 演示骨架：pyproject.toml、src/lcmd/cli.py、src/lcmd/__init__.py、tests/test_cli.py、.gitignore、.gitattributes。CLI 只有 hello 示例；三个 pytest 测试通过，Ruff 检查和格式检查通过。该代码不包含正式 LCMD 业务功能，已决定全部清除，不作为后续架构或实现依据。

### 正式项目重置结果（历史记录）

- 项目曾以仅包含 `LCMD-DEV.md` 的根提交 `538a922` 重新初始化，作为正式开发起点。
- P1.1 项目骨架提交 `a62d1ca` 已推送到 GitHub `main`。
- P1.2 配置系统提交 `4d046aa` 已推送到 GitHub `main`。
- P1.3 代码提交 `43adf36` 已推送至 GitHub `main`；总控文档更新提交 `05c9da3` 已验证。
- P1.4 代码提交 `3b5457b`（`feat: initialize CLI configuration and knowledge paths`）已推送至 GitHub `main`。
- GitHub 仓库本身保留，未删除或重建；知识库仓库 `WenZoo1982/lcmd-kb` 仍未创建。

### 当前执行状态

- [x] 完成原始仓库、配置、源代码和测试核对。
- [x] 原始 pytest：3 项通过。
- [x] 原始 Ruff 检查通过。
- [x] 原始 Ruff 格式检查通过。
- [x] 确认原始演示工程没有保留价值，决定清理并重新开始。
- [x] 清理本地旧工程文件，仅保留 `LCMD-DEV.md`。
- [x] 重新初始化本地 Git 仓库和 `main` 分支。
- [x] 用新的 `main` 历史覆盖 GitHub 远程 `main`。
- [x] 验证本地与 GitHub 的 `main` 指向同一提交，工作区干净。
- [x] 核对 P1 开发环境：Python 3.14.10、Python 3.10、pip 26.2.2、Git 2.56.0.windows.2；确认项目目录仅有 .git 和 LCMD-DEV.md。
- [x] 确认 P1 技术选型、最低 Python 版本、最小项目结构及验收标准。
- [x] P1.1：创建正式项目骨架、项目元数据、README、CLI 入口、Rich 输出模块及基础测试。
- [x] 创建项目虚拟环境 `.venv`，使用 Python 3.14.10；安装运行和开发依赖。
- [x] 验证 editable 安装成功，CLI `--help`、`--version`、`-v` 和 `python -m lcmd --version` 可用。
- [x] P1.1 pytest：`3 passed`；Ruff lint：`All checks passed!`；Ruff format：`10 files already formatted`。
- [x] P1.1 代码提交 `a62d1ca`（`feat: add LCMD project skeleton and CLI foundation`）已推送。
- [x] P1.2：新增 `src/lcmd/core/config.py` 和 `src/lcmd/core/__init__.py`，实现配置路径定位、平台默认值、TOML 读取、字段校验、首次创建和原子保存。
- [x] 新增 `tests/test_config.py`，覆盖配置路径、Windows/Linux/macOS 默认平台、首次创建、读取、保存、损坏 TOML、缺失字段、错误类型和非法值，以及非法保存保护已有文件。
- [x] P1.2 完整测试：`22 passed`；Ruff lint 全部通过；Ruff format 检查 13 个文件全部通过；`git diff --check` 通过。
- [x] P1.2 代码提交 `4d046aa`（`feat: add user configuration management`）已推送；本地 `main` 与 `origin/main` 同步，工作区干净。
- [x] P1.3：新增 `src/lcmd/core/paths.py`，实现 `get_default_knowledge_dir()`、`get_knowledge_root()`、`validate_knowledge_root()`、`get_knowledge_dirs()`，以及 `PathError`、`KnowledgeDirs`。
- [x] P1.3 测试覆盖默认路径、环境变量覆盖、空值/空白值、相对路径解析、根目录有效性和错误、配置目录推导及不自动创建目录。
- [x] P1.3 全量 pytest：`34 passed`（其中路径模块 12 项）；Ruff lint：`All checks passed!`；Ruff format：`15 files already formatted`；`git diff --check` 通过；两个新增文件均为 UTF-8 无 BOM。
- [x] P1.3 代码提交 `43adf36`（`feat: add knowledge base path management`）已推送至 GitHub `main`。
- [x] P1.4：`src/lcmd/cli/app.py` 接入配置读取、知识库目录推导和根目录验证；捕获 `ConfigError`、`PathError`，通过统一错误输出并以退出码 1 退出。帮助、版本和无参数帮助保持可用，不执行知识库初始化。
- [x] P1.4 自动化测试：CLI 帮助、版本、短版本、初始化成功、配置异常、知识库根目录验证异常；CLI 专项测试 `6 passed`。
- [x] P1.4 全量 pytest：`37 passed`；Ruff lint：`All checks passed!`；Ruff format：`15 files already formatted`。实际 CLI `--help` 和 `--version` 验证通过；`git diff --check` 无空白错误（仅有 Windows Git LF/CRLF 提醒）。
- [x] P1.4 代码提交 `3b5457b`（`feat: initialize CLI configuration and knowledge paths`）已推送至 GitHub `main`。

### P2.2—P2.3 本地实现与验收记录

- P2.2 Parser：新增 `src/lcmd/knowledge/__init__.py`、`src/lcmd/knowledge/parser.py` 和 `tests/test_parser.py`。实现 `ParsedDocument`、`DocumentParseError`、`parse_document()`；支持 LF/CRLF，解析 TOML Front Matter 并原样保留正文；缺失标记或 TOML 语法错误时报错。Parser 不执行 Schema 校验。
- P2.2 验收：Parser 专项测试 12 项通过；当时全量 pytest `49 passed`；Ruff lint、format 和 `git diff --check` 均通过。代码已随 P2 阶段统一提交并推送。
- P2.3 Validator：新增 `src/lcmd/knowledge/validator.py` 和 `tests/test_validator.py`。实现 `DocumentValidationError`、`validate_document()`；分别校验 command/task 文档的允许字段、必填非空字符串 `summary`、非空正文；任务文档 `commands` 可选，缺省返回空数组，存在时要求为字符串数组；拒绝未定义字段。Validator 不扫描目录或解析命令引用。
- P2.3 验收：Validator 专项测试 `20 passed`；全量 pytest `69 passed`；Ruff lint 通过；Ruff format 检查 `20 files already formatted`；`git diff --check` 通过。Validator 文件曾因 BOM/换行组合触发 Ruff 0.17.3 崩溃，统一为 UTF-8 无 BOM、LF 并格式化后已通过全项目检查。
- P2.2—P2.4 代码已在后续统一提交中纳入 Git，详见下方提交记录。

### P2.4 Knowledge Loader 开发基线

P2.4 开始前已核对本地 Parser、Validator、路径管理、配置和主程序版本定义。Loader 按以下规则实现：

- 新增 `src/lcmd/knowledge/loader.py`，复用 `parser.py`、`validator.py`、`core/paths.py` 和 `AppConfig`；不重复实现路径计算、Front Matter 解析或文档 Schema 校验。
- 主程序版本直接读取 `lcmd.__version__`（当前项目定义于 `src/lcmd/__init__.py`），不另建版本配置。
- 知识库根目录必须存在且为目录；根目录下必须有可读取、格式正确的 `manifest.json`。
- 第一版清单严格只允许 `version` 一个字段，值必须是有效 SemVer 版本字符串；缺失、未知字段、类型错误或版本格式错误均属于知识库级错误，终止加载。
- 主程序版本与知识库版本只比较 Major 主版本号。Major 相同即兼容，Minor/Patch 不参与兼容性判断；知识库 Major 低于主程序时提示更新知识库，高于主程序时提示升级主程序。
- 只扫描当前 `AppConfig` 指定的平台和语言目录，不扫描其他平台或语言目录。
- 当前平台的命令目录和任务目录允许不存在或为空；这不属于知识库级错误。命令资料缺失时由后续查询明确提示未收录，不阻止知识库加载。
- 单篇 Markdown 文件无法读取、Front Matter 解析失败或 Schema 校验失败时，跳过该文档并记录文件路径和原因；继续加载其他有效文档。
- Loader 返回已加载的命令文档、任务文档和诊断信息。具体数据结构及函数签名以测试先行的实现为准。
- P2.4 只实现清单检查、版本兼容检查、文档发现/加载和诊断汇总；不实现命令查询、搜索、任务引用解析或 CLI 接入。

### P2.4 实际实现与验收结果

- 新增 `src/lcmd/knowledge/loader.py`，实现 `KnowledgeLoadError`、`LoadedDocument`、`LoadDiagnostic`、`KnowledgeLoadResult` 和 `load_knowledge(config)`。
- Loader 复用 `get_knowledge_dirs()`、`validate_knowledge_root()`、Parser 和 Validator；从 `lcmd.__version__` 读取主程序版本。
- 实现 `manifest.json` 读取及严格校验：只允许 `version` 字段，要求有效 SemVer 2.0.0 字符串；清单缺失、读取失败、JSON 格式错误、字段错误和版本格式错误均作为知识库级错误终止加载。
- 实现只比较 Major 的版本兼容检查：知识库 Major 较低时要求更新知识库，较高时要求升级主程序；相同 Major 下 Minor、Patch、预发布和构建元数据不影响兼容判断。
- 只扫描当前配置指定平台和语言目录下的直接子级 `*.md` 文件；命令、任务目录缺失或为空均允许加载，不扫描其他平台或语言。
- 单篇文档读取、UTF-8 解码、Parser 或 Validator 失败时跳过该文档，并记录路径和原因；继续加载其他有效文档。加载结果按文件名稳定排序，分别返回命令、任务和诊断列表。
- P2.4 不包含命令查询、搜索、任务引用解析或 CLI 接入。
- 测试先行：新增 `tests/test_loader.py`，覆盖有效命令/任务文档、多个文档排序、平台和语言隔离、目录缺失/为空、单文档错误隔离、manifest 错误及 Major 版本兼容性，共 31 项测试。
- P2.4 定向测试：`31 passed`。全量 pytest：`100 passed`。Ruff lint：`All checks passed!`。Ruff format：`22 files already formatted`。`git diff --check` 无错误。
- P2.2—P2.4 代码已提交并推送至 GitHub `main`：`5fa687b`（`feat: add knowledge document loading`）。该提交包含 7 个文件、1005 行新增内容：`src/lcmd/knowledge/__init__.py`、`loader.py`、`parser.py`、`validator.py`，以及 `tests/test_loader.py`、`test_parser.py`、`test_validator.py`。
- 推送前本地与远程曾因远程总控文档提交 `63f13ad` 形成分叉；通过 `git pull --rebase origin main` 安全重放本地代码提交后推送成功。最终验证 `main` 与 `origin/main` 均指向 `5fa687b`，`git status -sb` 显示 `## main...origin/main`，工作区干净。

### 下一步

P2.2—P2.4 已统一提交并推送。下一步开始 P2 后续集成前，先检查 CLI 当前实现和 Loader 接口，明确最小集成范围及测试方案；继续采用测试先行，不提前扩展搜索、任务引用解析或更新功能。

### 待确定（在对应阶段解决，不阻塞重置）

- P2：Loader 对缺失平台目录、空目录和无效文档的诊断细节；平台资料不完整不属于知识库版本兼容错误。
- P4：中文检索实现、索引策略及性能基准。
- P5：任务文档引用采用路径还是稳定 ID。
- P7：数字签名算法及具体实现工具。

---

## 9. 开发协作与文档更新规则

- 每次新对话先读本文档当前状态，再检查相关代码和测试。
- 每次开发明确当前阶段和具体任务，不擅自跳阶段。
- 架构确需调整时，说明原因和影响；确认后更新本文档。
- 每项任务完成后更新已完成、正在进行、待解决问题和下一步任务。
- 只有代码和测试验证支持的内容才能标记完成。
- 只保留最终决策、必要理由和当前状态，不记录冗长聊天过程。
- 修改前检查 Git 状态和差异，不覆盖用户未提交的本地修改。
- 本文档是项目开发上下文入口，但不能代替实际代码、测试和 Git 状态核对。
