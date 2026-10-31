# LCMD 项目开发总控文档

> 本文档是 LCMD 项目的唯一开发总控入口，统一记录项目要求、最终架构、程序逻辑、目录与文件职责、开发阶段和实际进度。
> 每次开始新对话先阅读本文档，再核对实际代码、测试和 Git 状态。计划不代表已实现；只有代码和测试验证支持的内容才能标记完成。

- 主程序仓库：WenZoo1982/lcmd
- 知识库仓库：WenZoo1982/lcmd-kb（规划中，尚未创建）
- 当前阶段：P1 主程序基础框架（P1.1、P1.2、P1.3 已完成，下一步 P1.4 CLI 与整体验收）

---

## 1. 项目定位与开发要求

LCMD 是面向命令行用户的简体中文命令速查与学习工具。核心理念：少记忆，易理解；需要时快速查找。新手看得懂、理解得了、知道怎么用；有经验的用户查得快、找得准、用得上。LCMD 只提供知识查询，不执行系统命令。

### 内容原则

- 简洁、准确、容易理解、实用。
- 用途说明首先解释命令真正做什么，不为搜索堆砌词语。
- 参数精选；示例真实、可复制，并说明效果。
- 覆盖、删除、权限等操作提供必要风险提示。
- 默认速查内容与官方完整资料分开；--full 用于查看扩展官方资料。
- 文档章节按命令特点组织，不强制机械模板。

### 搜索原则

知识内容优先，搜索是辅助。搜索应适应知识文档，不要求文档迎合搜索算法。

- 检索命令正式名称、用途说明和 Markdown 正文。
- 检索任务指南名称、用途说明和正文。
- 不设置 keywords、aliases 元数据字段。
- 不做拼写纠错、相似命令推荐或自动猜测用户意图。
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

通用内容：命令名称、适用平台及实现、用途说明、基本语法、常用参数、常用示例、注意事项（按需）、关联命令（按需）、扩展资料（按需）。正文按命令特点组织。

### 元数据与 Schema

方向已确定为 TOML Front Matter + Markdown 正文。已明确不设置 keywords、aliases。命令名、平台、语言由目录和文件名推导，不重复存储。其余字段的最终必填性、格式和 Schema 版本规则在 P2 确定；早期示例不是最终 Schema。

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
3. 定位知识库根目录，检查清单和兼容性。
4. 推导当前命令目录、任务目录。
5. 调用相应知识加载、解析和查询模块。
6. 将结果交给统一输出模块显示。

CLI 每次执行都是独立进程，不应每次启动都无条件全量扫描、解析所有 Markdown。索引是否持久化由实际规模和性能测试决定。

### 命令精确查询

lcmd cp 根据当前平台、语言目录定位 cp.md，解析并显示文档。命令名不区分大小写。找不到时明确提示，不做拼写纠错或相似命令推荐。LCMD 不执行系统命令。

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
- 知识库声明最低兼容主程序版本；主程序声明支持的知识库 Schema 范围。
- 知识库 Release 提供完整 ZIP、manifest.json、SHA256SUMS.txt；清单包含版本、兼容性和文件信息，哈希由实际文件计算。
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
| core/knowledge.py | 清单读取、知识文档发现和加载协调 |
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

P1 的目标结构按阶段逐步建立。以下列出截至 P1.3 已实际创建并纳入 Git 的文件。

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
| tests/test_cli.py、test_config.py | CLI 与配置模块自动化测试 |

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
4. P1.4 CLI 与验收：帮助、版本、错误处理和自动化测试。

每个子阶段完成后检查代码、测试结果和 Git 状态，再继续下一阶段。

---

## 7. 开发阶段与验收标准

| 阶段 | 主要任务 | 完成标准 |
|---|---|---|
| P0 项目规划与架构整理 | 总控文档、架构、模块职责、仓库基线核对 | 规划与实际状态清楚，可执行开发任务 |
| P1 主程序基础框架 | 包结构、CLI、配置、路径、帮助、版本、错误处理 | 程序能运行，正确读取配置并定位知识库 |
| P2 知识库解析与管理 | Schema、TOML/Markdown 解析、加载、校验、错误隔离 | 有效文档可加载，单份错误不拖垮整体 |
| P3 命令查询 | 精确查询、格式化输出、--full | 通过真实知识文档查询，无硬编码命令资料 |
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

**P1 — 主程序基础框架：进行中。** P1.1 项目骨架、P1.2 配置系统和 P1.3 路径系统均已完成并推送至 GitHub；下一步为 P1.4 CLI 与整体验收。

**正式项目重置：已完成。** 本地与 GitHub `main` 已同步到全新根提交 `538a922`（`chore: initialize clean LCMD project`），该提交只包含 `LCMD-DEV.md`。本地工作区干净；旧演示工程、虚拟环境、缓存和旧 Git 历史已从本地及新的 `main` 历史中清除。

P0 已完成产品定位、架构与模块职责规划、开发阶段划分、总控文档建立，以及原始仓库基线核对。原始演示代码和测试仅用于验证开发环境，不属于正式产品实现。

### 已确认的设计决策

- [x] 产品定位及简洁、易懂、实用的内容原则。
- [x] 主程序与知识库独立维护、独立更新。
- [x] 知识库按平台和语言组织，命令与任务分目录。
- [x] 配置只保存 platform、language，目录由程序推导。
- [x] 不设置 keywords、aliases 元数据字段。
- [x] 不做拼写纠错、相似命令推荐和自动猜测。
- [x] 确定命令查询、内容搜索、任务指南、平台语言切换和统一更新入口。
- [x] 确定单一总控文档作为项目开发上下文入口。
- [x] 决定清除原始演示工程，以最终产品架构为基础重新建立项目。
- [x] 决定保留 GitHub 仓库和本总控文档，但重新初始化 Git 提交历史。
- [x] 确认 P1 技术方案：Python 最低支持 3.11，当前使用 3.14.10；Typer、Rich、platformdirs；标准库 tomllib；setuptools；pytest、Ruff。
- [x] 确认 P1 最小项目结构和 P1.1—P1.4 子阶段。
- [x] 明确 P1.2 配置系统设计：使用 platformdirs 定位配置文件；TOML 保存 platform、language；首次运行创建默认配置；非法配置明确报错；保存采用同目录临时文件和原子替换。
- [x] 明确 P1.3 路径系统设计：默认数据目录、`LCMD_KNOWLEDGE_DIR` 覆盖、空值报错、相对路径解析、根目录验证，以及 commands/tasks 平台语言路径推导。

### 原始仓库基线（2026-10-31，重置前）

原始仓库只有初始 Python/Typer 演示骨架：pyproject.toml、src/lcmd/cli.py、src/lcmd/__init__.py、tests/test_cli.py、.gitignore、.gitattributes。CLI 只有 hello 示例；三个 pytest 测试通过，Ruff 检查和格式检查通过。该代码不包含正式 LCMD 业务功能，已决定全部清除，不作为后续架构或实现依据。

### 正式项目重置结果（历史记录）

- 项目曾以仅包含 `LCMD-DEV.md` 的根提交 `538a922` 重新初始化，作为正式开发起点。
- P1.1 项目骨架提交 `a62d1ca` 已推送到 GitHub `main`。
- P1.2 配置系统提交 `4d046aa` 已推送到 GitHub `main`。
- P1.3 代码提交 `43adf36` 已推送至 GitHub `main`；总控文档更新提交 `05c9da3` 已验证。用户随后需将该文档提交拉取到本地。
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

### 下一步

进入 P1.4：核对 CLI 现有实现与产品规划，完成帮助、版本和错误处理的验收；补齐必要测试，确保 CLI 在配置和知识库不可用等场景下给出清晰提示。仅处理 P1.4 范围，不提前实现知识库解析、查询或更新功能。

### 待确定（在对应阶段解决，不阻塞重置）

- P2：最终 Schema 字段、必填性和错误隔离细节。
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
