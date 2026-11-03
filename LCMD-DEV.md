# LCMD 项目开发总控文档

> 本文档是 LCMD 唯一的开发总控入口。记录已确认的产品设计、技术约束、开发阶段和经核验的实际状态。每次继续开发，先阅读本文档，再核对本地代码、测试结果、Git 状态和 GitHub 远程状态。计划不代表已实现；历史测试结果不代表当前代码已通过测试。

- 主程序仓库：https://github.com/WenZoo1982/lcmd
- 知识库仓库：https://github.com/WenZoo1982/lcmd-kb
- 本地项目目录：D:\Project_DEV\lcmd
- 当前开发阶段：P6 主程序重建及 Windows 端验收已完成；待 Linux Mint 22.3 跨平台验收
- 首发目标：Windows x64、Linux AMD64；macOS 和 ARM64 暂不纳入首发。

---

## 1. 产品定位

LCMD 是面向命令行用户的简体中文命令速查与学习工具，核心理念：**少记忆，易理解；需要时快速查找。**

- LCMD 只查询知识库，不执行用户输入的系统命令。
- 不检测系统是否安装某个命令，不做系统命令发现。
- lcmd <command> 只查询知识库：找到文档就显示；未找到就提示“知识库尚未收录”。
- 查询是否命中只取决于知识库文档，不取决于目标命令是否安装。
- 普通查询不联网；只有 lcmd --update 执行联网更新检查。
- 命令文档重点包括用途、基本语法、常用参数、常用示例及必要注意事项，不复制维护官方完整手册。
- 知识库内容建设优先完成 `zh-CN`，并配套 `en-US`；文档应简洁、准确、易懂、可复制，对高风险操作给出必要提醒。

## 2. 平台与发行范围

| 平台 | 首发 | 说明 |
|---|---|---|
| Windows x64（Intel/AMD，AMD64） | 首发支持 | 独立 .exe 安装程序 |
| Linux AMD64（x86_64） | 首发支持 | Debian 系 .deb，首发面向 Linux Mint、Ubuntu、Debian |

首发版本仅支持 Windows x64 与 Linux AMD64。macOS、Windows ARM64、Linux ARM64 均不属于首发范围；未来增加新平台时，必须具备对应平台的构建与实际测试环境。

说明：
- AMD64/x86_64、ARM64/AArch64 是处理器架构，不是操作系统名称。
- Apple Silicon Mac 使用 ARM64，但 ARM64 也用于其他厂商的 Linux 和 Windows 设备。
- macOS 后续可复用 Python 主体代码，但需要 macOS 构建环境、平台适配和实际测试。
- Linux .deb 适用于 Debian 系发行版，不代表所有 Linux 发行版通用。图形化双击安装取决于发行版和桌面环境；终端安装可使用 sudo apt install ./安装包.deb。
- Linux 独立程序仍可能依赖系统共享库；无需预装 Python 不等于完全没有系统依赖。

## 3. 主程序与知识库架构

主程序与知识库是两个独立 GitHub 仓库，独立版本管理、独立 Release、独立更新包：

- 主程序：WenZoo1982/lcmd
- 知识库：WenZoo1982/lcmd-kb

主程序负责 CLI、配置、路径定位、知识库加载、解析、校验、查询、输出和更新。知识库保存 Markdown 文档。新增或修改知识文档原则上不需要修改主程序代码。

### 知识库目录

    lcmd-kb/
    ├── manifest.json
    └── commands/
        ├── platforms/
        │   ├── <platform>/<language>/
        │   └── ...
        └── tools/
            ├── <tool>/<language>/
            └── ...

- `commands/` 采用 `platforms/` 与 `tools/` 两个顶层类别：前者保存操作系统平台命令，后者保存第三方命令行工具知识。
- 平台命令路径为 `platforms/<platform>/<language>/<command>.md`，普通系统命令仍是一条命令一篇文档。
- 第三方工具路径为 `tools/<tool>/<language>/`；复杂工具可采用导航页与子命令详细页，简单工具可采用单篇综合速查。具体规则见第 14 节。
- 平台和语言由知识库目录动态发现，不在主程序中维护固定枚举。当前知识库只需包含首发实际提供的平台和语言；未来增加平台或语言时按规范新增目录。
- 第三方工具知识默认对当前选择的所有平台可见；平台差异须在文档中说明。旧 `common/` 目录不再作为新架构类别，旧内容在 P6 一次性迁移至 `tools/`。
- 搜索只检索当前选择的平台命令与当前语言下的工具文档。普通搜索覆盖命令/工具名称、完整子命令路径、summary 和用途说明；`--full` 在此基础上增加参数、示例及其他正文。搜索规则见第 14.5 节。
- Linux Mint、Ubuntu、Debian 共用 Linux 平台知识目录，不按发行版拆分。
- Linux 首发以 GNU 命令体系为基准，优先覆盖 Ubuntu 22.04 / Debian 12 这一代系统常见 GNU 工具；较新参数在文档中标注版本要求。不专门支持 BusyBox/Toybox。

- 知识库允许逐步收录命令。目录为空或某条命令尚未收录，不代表知识库无效。

### 文档格式

命令文档使用 UTF-8 Markdown + TOML Front Matter：

- 必填 summary：非空字符串。
- 所有 Markdown 文档（包括工具入口文档、平台命令文档、工具子命令文档及简单工具综合文档）均必须提供非空 `summary`。不设置 `keywords`、`aliases`；搜索字段由目录/文件路径推导，并从文档提取 summary 和正文内容。
- 不增加 `type` 等重复描述目录信息的 Front Matter 字段。文档类别及标识由路径推导：`platforms/<platform>/<language>/<command>.md` 表示平台命令；`tools/<tool>/<language>/<tool>.md` 表示工具入口/总览文档；工具语言目录下其他 Markdown 文件按相对路径表示工具综合文档或子命令文档，具体查询语义由目录结构确定。
- Front Matter 首版只要求非空字符串 `summary`，不设置 `type`、`keywords` 或 `aliases`。Parser 负责解析 Front Matter；Validator 校验必填元数据及路径/文档结构约束；Loader 负责发现、加载文档并在内部处理加载问题。
- 单篇文档格式或内容结构无效时，跳过该文档并继续加载其他有效文档；不得因无关文档的问题中断正常查询。Markdown 排版不够规范但仍可解析时，尽可能正常显示，不额外报错。
- 普通用户不查看诊断报告、错误代码、内部文件路径或异常堆栈。具体解析原因和文件路径仅作为开发排查信息，不主动输出、不写入日志文件，也不引入日志框架或额外依赖。

## 4. 配置与路径设计

配置文件由 platformdirs.user_config_path() 定位，内容示意：

    [knowledge]
    platform = "linux"
    language = "zh-CN"

    # 可选。必须是绝对路径；不设置时使用 platformdirs 默认用户数据目录。
    # path = "D:/LCMD/knowledge"

- 配置保存 platform、language，以及可选的知识库根目录 path。
- `path` 始终指向知识库根目录，不随平台或语言切换而改变；必须是绝对路径。
- `platform` 与 `language` 只保存用户当前选择的目录标识，不保存平台/语言子目录路径。
- 可用平台从知识库 `commands/platforms/` 实际目录动态发现；可用语言从所选平台实际存在的语言目录动态发现。主程序不得硬编码平台或语言清单。
- `lcmd platform`、`lcmd language` 显示当前选择和知识库实际提供的可用值；切换前验证目标目录存在且结构有效，成功后只修改相应配置值。
- 如果目标平台不提供当前语言，明确列出该平台可用语言并要求用户选择；不得静默切换语言、平台或知识库路径。
- 未设置 path 时使用 platformdirs.user_data_path() 下的默认知识库目录。
- 缓存和更新临时文件使用 platformdirs.user_cache_path()；配置目录使用 platformdirs.user_config_path()。
- 安装程序首次安装时检测运行平台和系统语言，生成初始配置。主程序运行时读取配置，不反复检测系统语言或擅自更改平台。
- 用户手动切换平台/语言，只修改配置字段，按新配置检索；不要求用户更换实际操作系统。
- 不再支持 LCMD_KNOWLEDGE_DIR 环境变量覆盖。
- 不静默切换到其他路径、平台或语言。

### 用户可见提示

用户交互只围绕实际使用问题提供简洁提示，不展示 Loader、Parser、Validator 等内部实现信息，不设计面向普通用户的诊断报告或错误代码体系。

- 查询的命令或工具不存在：提示“未找到相关命令或工具。”
- 切换到知识库未提供的平台：提示该平台不受支持，并列出当前知识库实际提供的平台。
- 切换到当前平台未提供的语言：提示该语言不受支持，并列出当前平台实际提供的语言。
- 目标平台或语言已经是当前选择：提示无需切换或已经是当前设置。
- 当前查询对应的知识文档确实无法解析或正常显示：提示“知识内容暂时无法正常显示。”不暴露内部异常。
- 知识库路径不可用、manifest 无效或版本不兼容等整体错误：给出简洁、明确且可操作的提示，不伪装成“未找到命令”。

内部文档加载错误应隔离处理：只影响对应文档，其他有效文档继续使用。只有当前操作确实受到影响时，才向用户显示提示；无关文档的问题不得打扰用户。

### 路径错误处理

- 默认知识库目录缺失、损坏或不可访问时，明确显示完整路径和原因，并提供后续修复指引。
- 用户配置了自定义 path，但路径不存在、不是目录、不可访问或缺少有效 manifest.json 时，明确报错。
- 自定义路径无效时不自动创建空知识库、不回退到默认目录、不修改用户配置。
- 知识库更新不需要管理员权限，普通用户即可运行。
- 主程序安装位置可在任意盘符或路径，不依赖当前工作目录，也不写死盘符。

## 5. Manifest 与版本兼容

知识库 manifest.json 第一版只包含一个字段，示例：

    {"version":"2.5.1"}

采用 SemVer Major.Minor.Patch。

- 主程序和知识库 Major 必须一致；Minor、Patch 不要求一致。
- Major 表示主程序与知识库之间的结构/协议兼容基线，不与支持平台数量绑定。按既有目录规范新增平台或语言不应仅因此要求修改主程序或提升 Major；只有目录、元数据协议或兼容契约发生不兼容变化时才提升 Major。
- Minor/Patch 用于主程序功能修正或知识库内容更新，允许独立发布。
- 普通启动/查询只读取本地版本并比较 Major，不联网。
- Major 不一致时阻止使用，要求更新不匹配组件。
- 知识库平台目录为空、命令未收录、资料不完整，不属于版本兼容错误。
- 主程序发布新 Major 时，必须同步发布对应 Major 的知识库 Release，即使知识库只有目录结构和 manifest，也要形成正式版本。

## 6. CLI 行为

| 命令 | 行为 |
|---|---|
| lcmd --help / -h | 显示帮助，不联网 |
| lcmd --version / -v | 显示主程序及本地知识库版本，不联网 |
| lcmd <command> | 查询当前配置平台的系统命令或第三方工具文档 |
| lcmd <tool> <subcommand...> | 查询工具的子命令详细文档，支持规范定义的多级路径 |
| lcmd <command> --full | 扩展资料入口，具体行为待对应阶段实现 |
| `lcmd search <keyword>` | 使用简短关键词搜索当前平台和语言下的命令/工具文档；结果按相关度排序，必要时分页 |
| lcmd platform [name] | 查看或切换知识平台 |
| lcmd language [name] | 查看或切换知识语言 |
| lcmd --update | 统一检查并更新主程序、知识库 |

- 命令名称精确匹配，不区分大小写。
- 平台系统命令从 `platforms/<selected-platform>/<selected-language>/` 查询；第三方工具从 `tools/<tool>/<selected-language>/` 查询。
- 工具导航页与子命令详细页按通用文档类型和路径规则识别，不得按具体工具名称分支判断。
- 不检查系统命令或第三方工具是否安装，不执行用户输入；普通查询不联网。
- `lcmd <command>` 和 `lcmd <tool> <subcommand...>` 是精确文档查询，不进入搜索分页；只有 `lcmd search <keyword>` 的搜索结果超过分页阈值时才可能启动分页。

## 7. 统一更新机制

统一更新入口为 lcmd --update，用户不单独选择更新主程序还是知识库。

- 主程序与知识库独立发布，但统一检查、用户确认、下载、验证和更新。
- 是否更新：分别比较两个组件的完整 SemVer；任一组件有新版本即列入更新。
- 是否兼容：检查更新目标组合的 Major 是否一致。
- 目标组合 Major 不一致，视为发布过程中的临时维护状态，提示“LCMD 更新服务暂时维护中，请稍后重试”；不下载、不安装、不改本地内容。
- 所有待更新组件先下载到临时目录并验证，再进行切换；任一组件失败时保留旧版本并恢复原兼容组合。
- 主程序与知识库安装位置不同，必须设计明确的备份、提交和回滚流程，不能假设跨目录替换天然原子化。
- 更新前列出版本和更新内容，必须由用户确认，不自动更新。
- 更新知识库前提示用户自行备份自定义文档。程序不识别、不区分、不备份、不合并、不恢复用户自定义文档；官方知识库按发布包整体替换，用户自行承担自定义内容被覆盖的风险。
- 下载和校验至少验证文件完整性、SHA256、manifest、目录结构和版本兼容性；签名方案在更新阶段设计并测试。
- 更新失败保留旧版本，显示具体原因；不影响普通查询。
- 更新源固定 GitHub Releases。

## 8. 独立程序安装与发布

用户选择独立程序安装：最终用户不需要预装 Python，下载 LCMD 安装包即可使用。

- 源码继续使用 Python 开发；发布时为各目标平台构建独立程序包，包含所需 Python 运行时。
- Windows 首发提供 x64 .exe 安装程序，采用安装向导。
- Linux 首发提供 AMD64 .deb，面向 Linux Mint、Ubuntu、Debian。
- 主程序与知识库分别发布 GitHub Release；主程序 Release 提供平台安装包，知识库 Release 提供完整知识库 ZIP。
- macOS（Intel、Apple Silicon）和 ARM64 Linux 暂列后续目标。
- Linux 包需声明必要系统共享库/包依赖。具体打包工具和构建流水线尚未选定，须在打包阶段比较后决定。
- 不允许把“Windows 上可运行 Python 源码”误写成“Windows 可以直接构建所有平台安装包”。macOS 构建和测试需要 macOS 环境。

## 9. 当前技术基线

- 开发系统：Windows 11，PowerShell 5.1。
- 本地项目：D:\Project_DEV\lcmd。
- Python：3.14.10；项目声明最低 Python 3.11。
- 虚拟环境：.venv。
- 统一使用：
  - .\.venv\Scripts\python.exe
  - .\.venv\Scripts\ruff.exe
  - .\.venv\Scripts\lcmd.exe
- 已采用：Typer、Rich、platformdirs、tomllib、setuptools、pytest、Ruff。
- 开发采用测试先行；阶段验收包括定向测试、全量 pytest、Ruff lint、Ruff format、必要的真实 CLI 验证和 Git 状态检查。
- 不做无关的广泛诊断；先围绕当前明确目标进行最小范围、证据驱动的检查。

## 10. 开发阶段计划（稳定交付路线）

开发原则：以首发可用为目标，优先完成用户能直接感知的核心能力；避免提前建设复杂架构、重复拆分小阶段或为尚未使用的功能预留过度抽象。

| 阶段 | 交付目标 | 主要工作 | 完成标准 |
|---|---|---|---|
| P3.2 收尾 | 将已验收的配置/路径改动安全并入主分支 | 审查 6 个源码/测试文件；确认测试与差异；独立提交并推送代码 | 已完成；代码提交 `22674fe` 已推送至 `main`；文档独立更新 |
| P3.3 | 补齐现有 CLI 合同 | `--version` 同时显示主程序和本地知识库版本；支持 `en-US` 知识文档；中文帮助提示；验证平台专属优先与 common 回退 | 已完成并推送；129 项测试通过，Ruff 检查/格式通过，真实 CLI 验收通过；代码提交 `7d5ac6239abe0c57ffae65097f0c5306149c172f` |
| P4 | 内容搜索 | 仅搜索 commands；普通搜索匹配文档名称和 summary；`--full` 额外搜索 Markdown 正文；支持多关键词、相关度排序；离线运行 | 已完成并推送；132 项测试通过，Ruff 检查/格式通过，真实 CLI 验收通过；代码提交 `e397732c5930b8edf1bb0be57266fa67b7faa65c` |
| P5 | 平台与语言管理 | 首发仅支持 Windows、Linux；实现 `platform`、`language` 查看和切换；配置持久化与输入校验；管理命令不依赖知识库成功加载 | 已完成实现、验收并推送；27 项配置测试、29 项 CLI 测试、148 项全量测试通过；Ruff lint/format 通过；真实 CLI 验证平台/语言切换、重复设置、非法值保护及知识库路径失效时管理命令仍可用。代码提交 `5ead529` 已推送至 `main` |
| P6 | 知识库驱动的平台/语言与工具扩展架构 | 统一为 `platforms/` + `tools/`；实现平台/语言动态发现、配置切换、工具导航及多级子命令的通用加载/查询/搜索；以 Git、Docker 和新增测试平台验证；迁移旧知识库结构 | 新增平台、语言、工具或子命令只需按规范增加知识库目录/文档；不因新增名称修改主程序；自动化测试、静态检查、真实 CLI 和迁移回归通过 |
| P7 | 统一更新 | GitHub Releases 版本检查、下载、校验、用户确认、替换、失败恢复 | 主程序/知识库分别更新；兼容性与失败场景有测试；普通查询仍离线 |
| P8 | 安装包与跨平台构建 | Windows x64 安装包、Linux AMD64 .deb；安装位置与用户数据分离 | 在目标系统完成干净安装、启动、升级和卸载验证 |
| P9 | 首发验收 | 整理用户文档、版本说明、Release 资产与发布检查清单 | Windows x64、Linux AMD64 首发范围逐项验收通过 |

### 执行顺序与范围控制

1. P3.2、P3.3 已完成并推送；后续按 P4、P5、P6、P7、P8、P9 的顺序推进。
2. P3.3 只修复已经确认的 CLI 合同差异，不借机重构 CLI。
3. P4 已完成；P5 仅支持 Windows、Linux 两个平台，完成平台/语言管理。管理命令只读取和保存配置，不加载知识库；不重构 Loader。
4. P6 先实现知识库驱动的平台/语言发现、配置切换及工具层级查询通用机制，再集中建设真实命令知识库，避免主程序功能和内容编写互相阻塞。
5. P7 更新系统是高风险阶段，先完成流程设计和失败场景测试，再实现替换/回滚。
6. P8 先保证 Windows x64，再完成 Linux AMD64；不为首发加入 macOS、ARM64。
7. 不把缓存、临时目录、备份回滚等更新专用机制提前独立开发；按 P7 的实际更新流程一次性设计。
8. 每个阶段以“可运行、可验证、可交付”为完成标准。测试通过后记录结果并提交；不因文档写了计划就视为实现完成。

### 每阶段固定交付流程

- 开始：读取本总控文档；核对 Git 状态、相关代码和当前阶段依赖。
- 设计：只确认本阶段必要行为和边界；优先用测试固定规则。
- 实现：围绕目标最小改动，不顺手扩展无关功能。
- 验收：定向测试、全量 pytest、Ruff lint/format；涉及 CLI 或路径时做真实运行验证。
- 收尾：检查 diff 与 Git 状态；代码提交和文档提交分开；更新本总控文档并核验远程。

## 11. GitHub 与本地仓库状态核验记录（2026-11-02）

以下记录区分 GitHub 远程核验结果与用户本地执行结果。远程代码内容可核验，但 pytest、Ruff 和真实 CLI 验收由用户在本机执行。

### 主程序仓库 WenZoo1982/lcmd

- 默认分支：main。
- 当前 `main` 最新代码提交：`22674fea7d03343a41bfeb7ef62966bb930647ab`，提交信息 `feat: support configurable knowledge paths and common fallback`。
- P3.2 代码提交包含 6 个文件：3 个源码文件和 3 个测试文件；变更为 313 insertions、74 deletions。
- 远程存在 pyproject.toml、README.md、LCMD-DEV.md、src/lcmd/ 和 tests/。
- 远程源码包含配置、路径、Parser、Validator、Loader、命令精确查询、Rich Markdown 输出等模块。
- 当前主程序版本源码为 0.1.0。
- 当前远程测试文件：test_cli.py、test_config.py、test_loader.py、test_lookup.py、test_parser.py、test_paths.py、test_renderer.py、test_validator.py。
- 远程没有发现 GitHub Release。
- GitHub 文件内容和目录已核验；本次没有在 GitHub 远程执行 pytest 或 Ruff。

### 知识库仓库 WenZoo1982/lcmd-kb

- 默认分支：main。
- 根目录当前只有 README.md。
- 该段为较早的历史快照；当前知识库状态以第 12 节最新核验记录为准。
- 远程没有发现 GitHub Release。

### 远程源码与最终设计的已知差异

1. `--version` 已同时显示主程序版本和本地知识库版本；该行为已由 P3.3 自动化测试及真实 CLI 验证。
2. `--help` 的主要说明为中文，但 Typer 的部分帮助提示（例如 `Show this message and exit.`）仍为英文；完整帮助中文化及分层示例属于后续帮助系统完善事项。
3. `search`、`platform`、`language` 已实现；统一更新、独立打包和安装流程尚未实现。
4. 安装程序生成初始配置的流程尚未实现。
5. 当前查询未命中时提示知识库未收录；不实现系统命令发现。

上述差异需要通过后续测试和实现逐项解决，不能只修改文档后就认为代码已符合设计。

## 12. 当前状态与下一步

### 当前真实状态（2026-11-02）

#### 主程序仓库 WenZoo1982/lcmd

- 默认分支：`main`。
- 当前远程代码最新提交：`7d5ac6239abe0c57ffae65097f0c5306149c172f`。
- 提交信息：`feat: add English knowledge support and version reporting`。
- P3.3 代码提交相对前一代码提交 `273a362ef70d0f723d26d286c2cc51d36666b57c`，修改 6 个源码/测试文件，110 insertions、15 deletions。
- 用户已确认代码推送成功：`main -> main`。
- 本地提交后 `git status --short` 无输出，工作区干净（以用户提交的本地终端输出为准）。

#### P3.3 自动化与静态检查

用户在本地对最终提交内容执行并反馈：

- `pytest -q`：129 passed in 0.99s。
- `ruff check .`：All checks passed!。
- `ruff format --check .`：25 files already formatted。

#### P3.3 真实 CLI 验收

以下项目均由用户在本机实际执行：

- `lcmd --version`：通过，同时显示主程序版本 `0.1.0` 和知识库版本 `0.1.0`。
- `lcmd -v`：通过，输出与长版本参数一致。
- `lcmd --help`：通过，帮助选项提示为中文。
- `lcmd dir`：通过，命中 Windows 英文知识文档并正确显示内容。
- `lcmd git`：通过，Windows 专属文档不存在时回退到 common 英文文档。
- 平台优先级：通过。临时同名测试文档验证 Windows 专属文档优先于 common。
- common 回退：通过。临时移走 Windows 文档后，成功显示 common 文档。
- `lcmd ls`：输出“知识库尚未收录该命令”。检查确认 Windows 和 common 目录均无对应文档，属于预期未收录提示，不是失败。
- 临时测试文档和配置已由测试脚本恢复；当前配置恢复为 `en-US`，知识库路径为用户配置的本地知识库目录。

#### P3.3 结论

P3.3 已完成：代码实现、自动化测试、静态检查、真实 CLI 验收均已通过；代码已推送至 GitHub `main`。主程序与知识库版本显示、英文知识语言支持、平台专属优先/common 回退和帮助提示均已验证。

### P4 当前状态：搜索核心与 CLI 接入已完成并推送

#### 已完成的产品范围调整

- 已确认 `commands/` 是唯一知识文档来源；不再维护独立的 `tasks/` 目录、文档类型或 Schema。
- 用户输入的任务描述只是搜索查询文本，搜索时匹配命令文档的文件名、`summary` 和 Markdown 正文；搜索结果仍然是命令文档。
- 官方 man 手册中的单命令资料也归入 commands，按 LCMD 文档规范筛选常用参数和示例，不照搬完整手册。
- 不实现 `lcmd task` 子命令。

#### 已完成的主程序代码清理

- 用户已在本地完成并推送代码提交：`e27690535a832af024c67430b8f32133f5d01c48`，提交信息 `refactor: remove task document support`。
- 修改范围：8 个源码/测试文件，27 insertions、269 deletions。
- 已从路径模型、知识加载结果、Loader、Validator 和测试中移除 tasks 字段、目录推导、加载/回退逻辑、任务文档 Schema 与任务专属测试。
- 命令文档平台优先、common 回退机制保留；旧任务字段 `commands` 不再是合法命令文档元数据。
- 用户反馈最终验收：`pytest -q` 为 116 passed；`ruff check .` 和 `ruff format --check .` 均通过；`git diff --check` 通过。
- 用户实际运行虚拟环境中的 CLI：`--version`、`--help`、`dir`、`git` 均正常；`dir` 命中 Windows 专属文档，`git` 回退到 common 文档。
- 用户在 `src`、`tests` 中执行 tasks 残留搜索，没有匹配结果。

#### 已完成的知识库结构清理

- `WenZoo1982/lcmd-kb` 的 `tasks/` 路径已从远程仓库删除，远程核验无残留。
- 知识库清理提交：`4a41709f9210617ff982e307d2711ba732d2bcd6`，提交信息 `chore: remove unused tasks knowledge structure`。
- 用户已执行 `git pull --ff-only origin main` 同步主程序总控文档和知识库仓库的远程变更。

#### P4 最终搜索设计（已确认）

- 唯一搜索来源：LCMD 自身 `commands/` 知识库；搜索离线运行，不读取用户系统的 man 手册。
- 普通搜索：匹配命令文档名称和 `summary`。
- `lcmd search <keyword> --full`：在普通搜索基础上，额外匹配 Markdown 正文。
- `--full` 只扩大搜索范围，不显示完整文档、不改变结果格式。
- 搜索结果始终只显示命令名称和摘要；用户选择后使用 `lcmd <command>` 查看完整文档。
- 多关键词采用 OR 匹配；重复关键词去重；命中关键词越多排名越靠前；相关度相同时按命令名称排序。
- 搜索不承诺语义理解，不引入中文分词、同义词库、人工任务映射或在线搜索。
- man 手册仅作为知识库维护者编写、核对命令文档的参考资料，不参与用户运行时搜索。
- 不恢复 `tasks/`，不实现 `lcmd task`；任务描述只是搜索关键词，结果仍为命令文档。

#### P4.1 搜索核心（用户本地完成）

- 新增 `src/lcmd/knowledge/search.py`，实现关键词规范化、普通/全文搜索、OR 匹配和相关度排序。
- 新增 `tests/test_search.py`，12 项测试覆盖命令名称、summary、正文范围、OR 匹配、排序、大小写、重复关键词、空查询和返回类型。

#### P4.2 CLI 接入（用户本地完成）

- 修改 `src/lcmd/cli/app.py`，注册 `lcmd search <keyword>` 和 `--full`；搜索结果只输出命令名称与 summary；无结果时给出重试提示。
- 修改 `tests/test_cli.py`，覆盖搜索输出、`--full` 参数传递、无结果提示和帮助列表。
- 保留原有 `lcmd <command>` 查询行为，并隐藏内部查询命令。

#### P4 本地验收记录（用户反馈）

- 全量 pytest：132 passed。
- `ruff check .`：All checks passed。
- `ruff format --check .`：27 files already formatted。
- 真实 CLI 验收：`lcmd --help` 列出 search 且隐藏内部查询命令；`lcmd dir`、`lcmd git` 正常显示完整文档；`lcmd search "dir"`、`lcmd search "git"` 命中并只显示名称和摘要；普通模式搜索 `Get-ChildItem` 未命中，添加 `--full` 后命中 `dir`，输出格式仍只包含名称和摘要。
- 用户提供的 `git diff --check` 无错误；Git 状态显示 2 个已修改文件和 2 个新增文件。
- 助手已审查 `src/lcmd/cli/app.py`、`tests/test_cli.py`、`src/lcmd/knowledge/search.py`、`tests/test_search.py` 的内容，未发现偏离已确认设计的问题。
- 用户已提交并推送 P4.1/P4.2 代码：`e397732c5930b8edf1bb0be57266fa67b7faa65c`，提交信息 `feat: add offline command search`。
- GitHub 提交记录核验：4 个文件，315 insertions、0 deletions；父提交为总控文档提交 `8fefe992cff6a517972a6aceffee273bfd9d8d87`。
- 用户本地执行顺序：`git commit` 成功；`git pull --rebase origin main` 成功；`git push origin main` 成功，远程 `main` 从 `8fefe99` 更新至 `e397732`。

#### P4 完成结论

P4 已完成：搜索设计、核心实现、CLI 接入、自动化测试、静态检查和真实 CLI 验收均已通过；代码已推送至 GitHub `main`。普通搜索和 `--full` 的实际行为符合已确认设计。P4 不读取系统 man 手册，也不恢复 `tasks/` 或实现 `lcmd task`。

#### P5 完成记录

首发平台范围已收紧为 Windows x64、Linux AMD64。主程序支持平台列表仅包含 `windows`、`linux`；macOS 不受支持，配置中的 `macos` 值会被拒绝。知识库首发目录仅保留 `commands/common/`、`commands/windows/`、`commands/linux/`，远程 macOS 占位目录已删除并由用户本地同步。

已实现并验收：
- `lcmd platform`：查看当前知识平台；`lcmd platform <name>`：切换到 `windows` 或 `linux`。
- `lcmd language`：查看当前知识语言；`lcmd language <name>`：切换到 `zh-CN` 或 `en-US`。
- 成功切换后显示新值；重复设置当前值时提示已经是当前值。
- 非法值明确报错并列出允许值；配置校验在保存前执行，非法值不会覆盖原配置。
- `platform`、`language` 管理命令只读取/保存配置，不加载知识库；知识库路径失效时仍可查看和切换配置。
- 保留既有平台专属优先、common 回退机制；未重构 Loader，也未修改知识库路径逻辑。

本地验收结果（由用户在 Windows 11 环境执行并反馈）：
- `tests/test_config.py -q`：27 passed。
- `tests/test_cli.py -q`：29 passed。
- `pytest -q`：148 passed。
- `ruff check .`：All checks passed。
- `ruff format --check .`：27 files already formatted。
- 真实 CLI 验证 `platform`、`language` 查看/切换/重复设置；最终恢复原配置 `windows` + `en-US`。
- 真实 CLI 验证非法平台 `macos` 和非法语言 `fr-FR` 被拒绝，原配置未受影响。
- 将配置中的知识库路径临时设为不存在的目录后，`platform`、`language` 仍可正常执行；`search` 明确报告知识库根目录不存在。随后通过备份恢复配置，SHA256 与原备份完全一致，并删除临时备份。
- `platform --help`、`language --help`、`search --help` 均能显示用途、参数和支持值；部分 Typer 帮助提示仍为英文。已确认后续采用分层帮助规范：主帮助列出所有已实现公开命令和全局选项；子命令帮助说明用途、参数、可选值并尽可能提供示例；新增功能同步更新帮助；隐藏内部命令不展示；未实现功能不提前展示。帮助系统完整中文化和示例完善作为后续统一改进，不阻塞 P5。

P5 功能、自动化测试、静态检查、真实 CLI 验收及 GitHub 远程交付均已完成。用户本地提交 `5ead529`（`feat: add platform and language management`）已成功推送至 `main`；用户反馈推送后 `HEAD` 与 `origin/main` 均指向 `5ead529`，`git status --short` 无输出。下一阶段为 P6：知识库仓库与首批内容。

### 文档同步状态

- 主程序代码提交 `e27690535a832af024c67430b8f32133f5d01c48` 已推送到远程 `main`。
- 知识库 `tasks/` 删除提交 `4a41709f9210617ff982e307d2711ba732d2bcd6` 已推送到远程 `main`。
- P4 代码提交 `e397732c5930b8edf1bb0be57266fa67b7faa65c` 已推送到远程 `main`。
- 本次 P5 总控文档更新与用户本地 P5 代码提交保持独立；用户需在本地执行 `git pull --ff-only origin main` 同步文档。
- P5 代码提交 `5ead529` 已由用户推送至远程 `main`；推送后本地 `HEAD` 与 `origin/main` 一致，工作区干净（以用户本次终端输出为准）。
- 文档提交与代码提交保持独立。



### P6 当前进展：知识库结构、规范与首批内容计划已确认

#### 知识库仓库远程状态（2026-11-02 核验）

- 仓库：`WenZoo1982/lcmd-kb`，默认分支 `main`。
- 远程最新提交：`6a85ecb`，提交信息 `chore: remove macOS placeholder knowledge directories`。
- `manifest.json` 当前知识库版本为 `0.1.0`；目前没有 GitHub Release。
- 根目录包含 `README.md`、`manifest.json` 和 `commands/`。
- 当前远程目录结构：
  
      commands/
      ├── common/
      │   ├── zh-CN/
      │   └── en-US/
      ├── linux/
      │   ├── zh-CN/
      │   └── en-US/
      └── windows/
          ├── zh-CN/
          └── en-US/

- 当前远程只有 3 篇英文示例文档：`windows/en-US/dir.md`、`common/en-US/dir.md`、`common/en-US/git.md`；尚无正式中文命令文档或 Linux 专属命令文档。
- 用户本地知识库仓库已核验：`HEAD` 与 `origin/main` 均为 `6a85ecb`，无需 pull。工作区有一个未跟踪文件 `commands/windows/zh-CN/lcmd-priority-test.md`，其内容是平台优先级测试标记（`WINDOWS_MARKER`），不是正式命令文档；当前建议保留在本地，不提交到公开知识库。该文件不改变远程状态。

#### 已依据主程序实际代码确认的文档规则

- Loader：只扫描当前平台/语言目录和对应 Common/语言目录的顶层 `*.md`，不递归；按文件名不区分大小写排序。
- 命令标识取 Markdown 文件名（不含扩展名）；文件名即命令正式名称。
- Parser：文件必须以独立的 `+++` 行开始 Front Matter，并以另一独立的 `+++` 行结束；Front Matter 使用 TOML；结束标记之后的正文原样保留。
- Validator：当前只允许一个元数据字段 `summary`；它必须是非空字符串；Markdown 正文必须非空；未知字段会导致该篇文档校验失败。
- 文档使用 UTF-8 Markdown + TOML Front Matter。当前程序不强制正文标题、章节顺序或示例数量；内容建设将另外遵循统一质量规范。
- 单篇文档解析/校验失败会被隔离并记录诊断，不阻断其他有效文档。
- 平台优先级以成功加载的文档名称为准：平台文档成功加载后优先；Common 仅补充平台没有成功加载的同名文档。若平台同名文档存在但解析/校验失败，当前 Loader 仍可能回退加载 Common 同名文档。这是已核对的现有行为，P6 内容建设阶段不擅自修改 Loader。

#### 已确认的文档内容规范

- 中文文档建议章节：用途、基本语法、常用参数、常用示例；按命令实际需要可省略不适用章节。
- 英文文档使用对应章节：Purpose、Basic syntax、Common options、Common examples。
- **内容以用户要完成的事情为中心，而不是以官方参数列表为中心。** 用户查阅文档时，应能快速回答“我想做什么、该用什么命令、如何直接使用”。
- “常用参数”优先采用需求导向的组织方式，建议表格第一列使用“想要做什么”，再给出使用方式和通俗解释；不把参数名称和官方定义作为内容主体。
- 参数解释使用日常、易理解的语言，说明实际效果和适用场景，避免照搬官方术语或帮助文档原文。
- 示例应尽可能提供完整、可直接复制使用的命令；必要时补充路径、参数或前置条件，避免让初学者自行拼接。
- 只收录高频、实用的功能，不以参数覆盖率或文档长度作为质量目标；低频参数不为追求完整而收录。
- 文档同时服务于快速查找和初学者理解：熟悉命令的用户能快速定位用法，初学者也能理解命令的实际作用。
- 对容易混淆、可能造成误操作或具有风险的操作，补充必要的技术说明和提醒；不为解释概念而堆砌无关背景。
- 参数与示例必须准确。平台行为或语法有差异时分别编写平台专属文档；Common 只收录真正跨平台工具的通用知识。
- Windows 首批文档以 Windows PowerShell 5.1 为主要教学环境，按 PowerShell 5.1 的实际命令、别名、cmdlet 和参数行为编写；不将 CMD/DOS 参数规则直接套用到 PowerShell。CMD 只在确有必要时补充常见兼容说明，不单独建设一套 CMD 教程。PowerShell 7 的新特性暂不纳入首发内容。
- LCMD 只展示知识，不执行文档中的命令。
- 当前 Validator 只校验 Front Matter 的 `summary` 和非空正文；上述章节与内容质量要求属于编辑规范，不应误称为程序已强制校验。

#### 首批命令范围与内容建设顺序（用户已确认）

首批暂定 22 个命令文档主题：

| 分类 | 命令 | 用途 |
|---|---|---|
| Windows 专属 | `dir`、`cd`、`copy`、`move`、`del`、`mkdir`、`rmdir`、`ipconfig`、`ping`、`tasklist` | 文件/目录操作、网络诊断、进程查看 |
| Linux 专属 | `ls`、`cd`、`cp`、`mv`、`rm`、`mkdir`、`rmdir`、`pwd`、`ip`、`ping` | 文件/目录操作、网络诊断、路径查看 |
| Common | `git`、`ssh` | 跨平台版本控制与安全远程连接 |

内容建设顺序已由用户确认：

1. Windows `zh-CN`
2. Linux `zh-CN`
3. Windows `en-US`
4. Linux `en-US`
5. Common `zh-CN`
6. Common `en-US`

Common 必须保留两个语言目录：`commands/common/zh-CN/` 与 `commands/common/en-US/`。Loader 按当前语言回退，不允许跨语言回退。例如 Windows + `zh-CN` 只回退到 Common `zh-CN`，Windows + `en-US` 只回退到 Common `en-US`。

以上是首批内容计划，不代表这些文档已经创建或验收。P6 后续先按上述顺序逐组编写、审查和验证，不一次性生成大批未审阅文档；必要的内容校验工具须在核对现有测试与实际 Schema 后再决定是否增加。

## 13. 协作与状态更新规则

- 一次聚焦一个明确任务；必要时一次只问一个关键问题。
- 不擅自扩大范围，不重复已经确认的设计。
- 不把建议、计划或远程文件存在描述成已实现。
- 修改代码前检查 Git 状态和差异，不覆盖用户未提交的修改。
- 开发总控文档由助手直接维护 GitHub 远程 LCMD-DEV.md；远程更新核验成功后，再指导用户将文档变更拉取到本地。用户不需要手动编辑总控文档或上传文档。
- 代码仍在用户本地开发和测试；用户提供本地执行结果，助手据此更新远程总控文档。
- 文档提交与代码提交分开处理；文档更新不得覆盖用户本地未提交的代码/测试修改。
- 每个阶段完成后更新本总控文档、提交并推送，再核验远程结果。
- 用户本地环境和文件状态必须通过用户提供的命令输出核实；远程 GitHub 状态不能代替本地状态。


## 14. 知识库驱动的平台、语言与第三方工具通用架构（目标设计，尚未实现）

本节是 P6 的正式目标架构。以下规则是待实现设计，不代表当前主程序或知识库已经支持。

### 14.1 核心原则

**主程序提供通用发现、加载、查询和校验机制；平台、语言、工具及命令内容由知识库目录提供。主程序不得硬编码具体平台、语言或第三方工具名称。**

- 知识库目录采用两个顶层类别：`platforms/` 与 `tools/`。
- `platforms/` 保存操作系统平台命令；`tools/` 保存第三方命令行工具知识。
- 当前知识库只需包含首发实际提供的 Windows、Linux 及对应语言目录。无需预先创建 macOS、HarmonyOS 或其他未来平台的空目录。
- 在通用机制实现后，新增平台、语言、工具或子命令，原则上只需按规范增加知识库目录和 Markdown 文档，不修改主程序。
- “无需修改主程序”指知识库发现、配置切换、内容加载、查询和搜索能力已按通用规则实现。新增平台对应的安装包、系统集成、运行环境适配和实际系统测试仍可能需要单独开发。
- LCMD 不检测系统是否安装文档中介绍的命令，也不执行命令。

### 14.2 目标目录结构

```text
lcmd-kb/
├── manifest.json
└── commands/
    ├── platforms/
    │   ├── windows/
    │   │   ├── zh-CN/
    │   │   └── en-US/
    │   ├── linux/
    │   │   ├── zh-CN/
    │   │   └── en-US/
    │   └── <future-platform>/
    │       ├── zh-CN/
    │       └── en-US/
    └── tools/
        ├── git/
        │   ├── zh-CN/
        │   │   ├── git.md
        │   │   ├── init.md
        │   │   ├── status.md
        │   │   └── ...
        │   └── en-US/
        ├── docker/
        │   ├── zh-CN/
        │   │   ├── docker.md
        │   │   ├── run.md
        │   │   ├── build.md
        │   │   └── ...
        │   └── en-US/
        └── ssh/
            ├── zh-CN/
            └── en-US/
```

目录约定：

- 平台命令：`platforms/<platform>/<language>/<command>.md`。普通系统命令继续一条命令一篇文档。
- 第三方工具：`tools/<tool>/<language>/`。工具入口文档统一使用当前工具自身名称命名，即 `<tool>.md`，例如 Git 使用 `git.md`、Docker 使用 `docker.md`。复杂工具在入口文档之外组织子命令详细页；简单或参数型工具可以只有这一篇综合速查文档。
- `<tool>.md` 是由工具目录名确定的通用入口文件约定，不是按具体工具名称编写特例；Loader 根据当前工具目录名定位入口文档。
- 工具子命令与平台命令采用相同的 CLI 参数解析方式：工具名之后的每个参数就是一个子命令路径段，不另设 Git/Docker 等工具专属语法。路径映射规则为：除最后一个子命令段外，前面的段依次作为目录；最后一个段作为同名 `.md` 文件。例如 `lcmd docker compose` 对应 `tools/docker/<language>/compose.md`，`lcmd docker compose up` 对应 `tools/docker/<language>/compose/up.md`；`lcmd git init` 对应 `tools/git/<language>/init.md`。若查询路径对应一个子命令目录但没有同名 Markdown 文档，则显示该目录下可用的下一级子命令列表。路径编码须安全、可移植且无歧义。
- 平台标识、工具标识、子命令路径段及 Markdown 文件主文件名统一采用小写 ASCII slug：只允许 `a-z`、`0-9` 和连字符 `-`；必须以字母或数字开头和结尾，不允许空格、下划线、中文、斜杠或其他特殊字符。多个单词使用连字符连接，例如 `filter-branch`。此规则同样适用于平台命令文档的文件主文件名。
- 语言目录名是语言标识，不使用上述 slug 规则；继续采用规范语言标签形式，例如 `zh-CN`、`en-US`，并按知识库实际目录动态发现，不硬编码允许值。
- 知识库中的 slug 和文件名必须按小写规范存储。用户输入的工具名、平台命令名及子命令参数按大小写不敏感方式匹配，匹配前进行 ASCII 小写规范化；不允许通过大小写差异产生两个不同文档。
- Markdown 文档扩展名统一为小写 `.md`。Windows 保留设备名（如 `CON`、`NUL`、`AUX`、`COM1` 至 `COM9`、`LPT1` 至 `LPT9`）不得作为任何目录名或文件主文件名，即使后面带有扩展名也必须拒绝。
- Loader/Validator 必须拒绝不符合命名规则的目录和文档文件，并防止路径穿越、绝对路径、符号链接逃逸及解析后的实际路径越出对应知识库根目录。不同大小写或规范化后相同的名称视为冲突，不能静默覆盖或任意选择。
- 工具知识默认对当前选择的所有平台可见。Common 旧目录不再作为第三种类别；旧 Common 文档迁移到 `tools/`。若未来确实需要平台专属工具说明，必须先设计通用覆盖规则，不能临时为单个工具添加特例。

### 14.3 平台与语言动态发现及配置切换

配置文件继续保存三个独立信息：

```toml
path = "D:\\Project_DEV\\lcmd-kb"
platform = "windows"
language = "zh-CN"
```

- `path` 始终指向知识库根目录，不随平台或语言切换而改变。
- `platform` 和 `language` 只保存用户当前选择的目录标识，不保存或拼接子目录路径。
- 可用平台从 `commands/platforms/` 下实际存在且结构有效的平台目录动态发现。
- 可用语言从所选平台实际存在的语言目录动态发现；工具内容也按当前语言读取。
- `lcmd platform` 显示当前平台和知识库中发现的可用平台；`lcmd platform <name>` 切换到指定平台。
- `lcmd language` 显示当前平台可用的语言和当前选择；`lcmd language <name>` 切换语言。
- 目录发现阶段从实际目录和符合命名规则的 Markdown 文件发现平台及候选语言；切换前还必须尝试加载目标平台/语言，确认至少有一篇有效平台命令文档。只有验证成功才保存配置；失败时保留原配置，不改变 `path`。
- 当目标平台没有当前语言时，必须明确提示该平台提供哪些语言；不得静默切换语言、平台或知识库路径。用户应先选择该平台实际提供的语言。
- 主程序不得硬编码 `windows`、`linux`、`macos`、`harmonyos` 等平台清单，也不得硬编码 `zh-CN`、`en-US` 等固定语言允许值。
- 知识库路径不可用时，`platform`、`language` 至少仍可查看当前配置值；无法读取知识库时应明确说明不能发现或验证可用值，不得伪造列表。是否允许在离线/路径失效状态下强制设置未验证值，P6 设计时明确，默认不得保存未经验证的值。

示例：当前知识库只有 Windows 和 Linux 时，平台列表只显示这两个平台。未来加入 `commands/platforms/macos/zh-CN/` 后，主程序自动发现 macOS；加入 HarmonyOS 目录后也采用相同机制，无需为平台名称增加代码分支。

### 14.4 工具导航、子命令与查询规则

- `lcmd <tool>` 的工具入口按当前工具语言目录中的文档结构统一决定：
  - 存在 `<tool>.md`：显示该工具入口/总览文档；其他文档作为子命令详细页。
  - 不存在 `<tool>.md`，且只有一篇 Markdown 文档：直接显示该唯一文档，作为工具综合速查页。
  - 不存在 `<tool>.md`，且有多篇 Markdown 文档：显示可用文档/子命令列表，不任意挑选其中一篇。
  - 当前语言目录不存在或没有有效文档：明确提示，不静默切换语言，也不回退到其他语言。
- 工具查询沿用与 Git 等命令行工具相同的参数结构：`lcmd <tool> <subcommand...>`；工具名之后的参数按顺序组成子命令路径，不为特定工具设计单独语法。
- 路径映射：`lcmd git init` 对应 `tools/git/<language>/init.md`；`lcmd docker compose` 对应 `tools/docker/<language>/compose.md`；`lcmd docker compose up` 对应 `tools/docker/<language>/compose/up.md`。即最后一个子命令段映射为同名 Markdown 文件，前面的子命令段映射为目录。
- 若查询路径对应的子命令目录存在、但没有对应的同名 Markdown 文档，则显示该目录下可用的下一级子命令列表。
- 工具名称及子命令路径均由知识库目录/文档推导，不能在主程序中维护 Git、Docker 等名称或子命令清单。
- 查询解析必须支持规范允许的多级子命令路径，并保证与主程序公开选项、`search`、`platform`、`language` 等 CLI 命令不产生不可控冲突。
- 平台命令与第三方工具允许同名。执行简洁查询（如 lcmd git、lcmd ls）时，若平台命令和工具入口同时匹配，必须同时返回并展示，不要求用户使用额外的 command 或 tool 前缀，也不得静默覆盖其中一方。
- 查询结果允许同时包含匹配文档和下一级子命令。若文档与同名目录同时存在，显示文档并同时列出该目录下的子命令。
- 工具目录没有同名入口文档时，只有一篇有效 Markdown 文档则直接显示该文档；有多篇有效文档则显示可用文档/子命令列表。该规则同样适用于子命令路径，不任意挑选多篇文档中的一篇。
- search、platform、language 等 LCMD 公开子命令及全局选项保留为 CLI 入口，不被知识库同名文档覆盖；其他名称按知识库内容查询。
- 文档唯一 ID 直接采用相对于 `commands/` 根目录的规范化知识库路径，使用 `/` 作为逻辑分隔符，并保留 `.md` 扩展名；例如 `platforms/windows/zh-CN/dir.md`、`tools/git/zh-CN/init.md`、`tools/docker/zh-CN/compose/up.md`。该 ID 自然包含类别、平台或工具、语言及完整命令路径，不使用标题、summary 或用户输入生成 ID，也不依赖操作系统本地路径分隔符。

### 14.5 Loader、Parser、Validator 与 Search 的通用要求

#### Manifest 与目录发现

- manifest.json 是知识库根目录必需文件，只负责提供知识库版本号；第一版严格只包含 version 一个字段，值采用 SemVer Major.Minor.Patch。不得在 manifest 中维护平台、语言、工具、命令、文档路径或数量清单；这些内容一律从 commands/ 实际目录和文档动态发现。主程序校验 manifest 的 JSON 格式、字段结构及版本兼容性；缺失或无效 manifest 属于知识库整体错误。
- Loader 分为目录发现和内容加载两个步骤，但仍由同一个 loader.py 模块负责，不额外拆分 discovery 模块。
- discover_catalog(root: Path) 读取并验证知识库根目录、manifest 和目录结构，动态发现平台、平台语言、工具及每个工具自己的语言。目录清单不保存 Markdown 正文。
- 目录发现阶段只判断目录、文件路径和命名规则是否有效；不把文件存在等同于正文有效。平台语言切换必须进一步尝试加载目标语言，确认至少存在一篇有效的平台命令文档后才能保存配置。
- 每个工具的语言独立发现。当前平台/语言加载时，工具若没有对应语言目录或没有有效文档，只跳过该工具；不得因此阻断平台命令和其他工具的加载，也不得静默回退到其他语言。
- 当前平台/语言下没有任何有效平台命令文档时，本次知识加载失败；单篇文档损坏只隔离该文档。工具文档全部缺失或损坏，不影响有效平台命令继续使用。

#### Markdown 文档格式与 Parser

所有知识文档使用 UTF-8 Markdown + TOML Front Matter，正式格式如下：

~~~markdown
+++

summary = "查看当前目录中的文件和子目录，并按名称、类型或时间筛选。"

+++

---

## 用途

列出当前目录或指定目录中的文件和子目录。

## 常用示例

dir -File -Filter *.zip

只列出当前目录中扩展名为 .zip 的文件。
~~~

- 文件以独立的 +++ 行开始 Front Matter，并以另一独立的 +++ 行结束；Front Matter 使用 TOML。分隔符前后允许空行。
- Front Matter 只允许且必须包含一个字段 summary，值必须是去除首尾空白后仍非空的字符串。不设置 title、type、aliases、keywords 或其他重复表达路径信息的字段。
- Front Matter 结束后，正文必须以独立的 --- Markdown 分隔线开始；该分隔线属于正文，Parser 必须保留。
- 正文使用 Markdown 二级标题组织章节，例如 ## 用途、## 基本语法、## 常用参数、## 常用示例、## 必要注意事项。这些章节为推荐结构，不要求每篇文档全部包含；可按实际内容增删或调整。
- 正文不设置用于重复文档名称的一级标题。文档显示名称由知识库路径推导，不从 Markdown 正文提取，也不通过 Front Matter 的 title 维护。
- Parser 只负责解析 TOML 和分离正文：完整保留 TOML 元数据供 Validator 检查，并保留 --- 分隔线及其后的 Markdown 正文。Parser 不负责路径、slug、文档类别或内容质量校验。
- TOML 语法错误、Front Matter 分隔符缺失/不完整、正文分隔线缺失等无法解析的情况，视为单篇文档解析失败。
- Parser 使用 Python 标准库 tomllib，不增加 TOML 第三方依赖。

#### Validator

- Validator 检查 Front Matter 是否只有且必须包含 summary，并验证其为非空字符串；未知字段、重复 TOML 键或非法类型均拒绝该文档。
- Validator 检查正文分隔线和正文非空；不强制固定章节、示例数量或参数覆盖率，不因普通 Markdown 排版不够规范但仍可正常解析而拒绝文档。
- Validator 根据 Loader 提供的相对路径上下文检查目录层级、slug、语言目录、扩展名、Windows 保留设备名、大小写/规范化冲突和路径安全。
- 逻辑文档 ID 使用相对于 commands/ 根目录的 POSIX 路径，统一使用 / 分隔并保留 .md 扩展名；实际文件访问时再转换为当前系统的路径对象。
- 在读取文件前必须完成路径安全检查：拒绝绝对路径、路径穿越、越界符号链接和解析后实际路径越出知识库根目录的情况；只读取知识库范围内的普通文件。
- 文档类别、平台/工具标识、语言和命令路径均从目录结构推导，不使用 Front Matter 的 type 字段。

#### 统一数据模型

所有数据模型集中定义在 knowledge/models.py，采用冻结 dataclass 和 tuple 集合；不建立平台命令与工具文档的继承体系。

- PlatformInfo(name, languages)：一个平台及其候选语言目录。
- ToolInfo(name, languages)：一个第三方工具及其独立的候选语言目录。
- KnowledgeCatalog(root, version, platforms, tools)：知识库根目录、manifest 版本、动态发现的平台和工具目录清单。
- KnowledgeDocument(id, category, platform, tool, language, summary, body)：统一文档模型。平台文档的 platform 非空、tool 为空；工具文档相反。类别仅为 platforms 或 tools。
- 文档 id 是相对于 commands/ 的规范化路径。显示名称由该路径推导，不重复保存 title、name 或 relative_path 字段。
- KnowledgeBase(platform, language, documents)：当前选择范围内成功加载的文档集合，不重复持有完整 Catalog。
- QueryResult(documents, children)：精确查询可同时返回匹配文档集合和下一级子命令名称集合；两者都为空表示未找到。
- SearchResult(document, score)：搜索结果引用统一文档模型并保存相关度。
- Parser 的中间模型 ParsedDocument(metadata, body) 保存完整 Front Matter 元数据和正文；Parser 不提前丢弃未知字段，Validator 校验通过后，Loader 才生成 KnowledgeDocument。

#### 模块边界与接口

目标源码结构：

~~~text
src/lcmd/
├── __init__.py
├── __main__.py
├── main.py
├── cli/
│   └── app.py
├── core/
│   ├── config.py
│   └── paths.py
├── knowledge/
│   ├── models.py
│   ├── loader.py
│   ├── parser.py
│   ├── validator.py
│   ├── query.py
│   └── search.py
└── output/
    └── renderer.py
~~~

- core/config.py：配置模型、读取、写入和原子保存；继续使用现有 [knowledge] 配置节及 path/platform/language 字段，不改变用户配置文件格式。
- core/paths.py：只负责应用配置目录、数据目录和默认知识库路径定位，不扫描知识库内容。
- knowledge/models.py：集中定义上述数据模型，不依赖项目其他模块。
- knowledge/parser.py：parse_document(content: str) -> ParsedDocument；只解析 TOML 和正文。
- knowledge/validator.py：提供文档相对路径校验和解析结果 Schema 校验；不依赖 CLI、Renderer 或 Loader。
- knowledge/loader.py：discover_catalog(root: Path) -> KnowledgeCatalog；load_knowledge(catalog, platform, language) -> KnowledgeBase。负责目录发现、文件读取、Parser/Validator 协调和单篇错误隔离。
- knowledge/query.py：query_document(knowledge, arguments) -> QueryResult；只在已加载的数据中进行精确查询，不读取文件系统。
- knowledge/search.py：search_knowledge(knowledge, keyword, full=False) -> tuple[SearchResult, ...]；只在当前 KnowledgeBase 中搜索，不读取文件系统。
- output/renderer.py：使用 Rich 显示文档、同名匹配结果、子命令列表和搜索结果；负责交互式分页，不执行查询、不读取文件。
- cli/app.py：负责 Typer 命令入口、配置/知识库流程协调、参数处理和用户可见提示；不承载 Parser、Loader、Query 或 Search 的内部实现。
- main.py 与 __main__.py 只负责程序入口。

依赖方向约束：Models 不依赖其他项目模块；Parser 和 Validator 不依赖 Loader/CLI；Loader 依赖 Models、Parser、Validator；Query/Search 只依赖 Models；Renderer 只依赖输出所需模型和 Rich；CLI 负责组合调用。不得产生循环依赖，不增加没有明确需求的 services、repositories、adapters、插件框架或注册表。

#### 精确查询与搜索

- 精确查询使用 lcmd <name> 和 lcmd <tool> <subcommand...>。用户输入不区分 ASCII 英文字母大小写，匹配前规范化；路径段必须符合 slug 规则，不允许用户参数直接构造任意文件路径。
- 平台命令和工具入口同名时同时返回，不设置 AMBIGUOUS 状态，不增加 command、tool 前缀。
- 查询文档和同名子命令目录可以同时存在；QueryResult 同时返回文档和 children。
- 没有工具入口 <tool>.md 且只有一篇有效文档时直接显示该文档；有多篇时显示可用文档/子命令列表。
- search、platform、language 和全局选项为 CLI 保留入口，优先由 CLI 处理；知识库文档不得覆盖这些入口。
- Search 仅检索当前平台的系统命令和当前语言下存在有效文档的工具；不搜索其他平台或其他语言。
- 普通搜索字段包括命令名称、工具名称、完整子命令路径、summary 和正文“用途”说明；--full 在普通搜索字段基础上增加常用参数、常用示例及其他正文。
- 中文采用连续双字片段匹配，单字查询保留单字匹配能力；英文按单词边界切分并忽略大小写；中英文混合查询统一参与字面匹配。
- 多关键词采用 OR 逻辑，任一关键词片段命中即可进入候选；按完整短语命中、命令/工具标识、字段权重及匹配覆盖度计算相关度。名称/完整子命令路径优先级最高，其次 summary，再其次用途；--full 扩展正文参与匹配。具体权重通过测试校准，不在规范中预设任意分值。
- 不引入中文分词库、同义词库、语义搜索或在线搜索。搜索不承诺理解自然语言语义；不要求知识文档堆砌关键词、aliases 或 keywords。
- 搜索结果显示文档名称、用途摘要及来源类别；平台命令显示平台来源，第三方工具显示工具来源。同名内容同时显示，不能相互覆盖。
- 搜索结果默认每页 5 条；不超过 5 条直接显示。超过 5 条且处于交互式终端时才分页，按 Enter 查看下一页、按 Q 退出；非交互终端、管道或重定向直接输出全部结果。精确查询不进入搜索分页。
- Search 负责匹配和排序；Renderer 负责显示和分页；CLI 负责调用两者。搜索排序相同的结果按文档唯一 ID 稳定排序。
- 搜索规则沿用此前已确认的设计，不因新架构重建而引入额外字段或重新设计搜索功能。

#### 错误边界

- 知识库整体错误：知识库根目录不可用、manifest 缺失/无效、Major 不兼容、commands 根目录缺失等；由 Loader 以明确的整体错误向 CLI 传递，本次加载停止。
- 单篇文档错误：文件无法读取、TOML 解析失败、Schema 不合规或路径不合规；Loader 隔离该文档，继续加载其他文档，不向普通用户展示内部路径、诊断报告或异常堆栈。
- 当前平台/语言没有任何有效平台命令文档：本次加载失败；配置切换不保存目标值。
- 个别工具没有当前语言或没有有效文档：跳过该工具，不回退到其他语言，不影响其他内容。
- 普通查询没有匹配文档或子命令：显示“未找到相关命令或工具。”
- 当前查询命中文档但确实无法正常显示：显示“知识内容暂时无法正常显示。”
- 不引入日志框架、日志文件或面向普通用户的错误代码体系；内部异常只用于控制流程。

#### 测试验收要求

- 目录发现：动态增加未知平台、未知语言、未知工具，无需修改主程序；平台语言与工具语言独立发现。
- 文档解析/校验：TOML、未知字段、重复键、summary 类型/空值、缺失 Front Matter、缺失正文 ---、空正文、CRLF、UTF-8、Markdown 正文保留。
- 路径安全：非法 slug、大小写冲突、保留设备名、绝对路径、路径穿越、符号链接逃逸、越界解析路径。
- Loader：平台文档、工具入口、单篇综合文档、多级子命令；单篇损坏隔离；工具缺语言不影响其他工具；平台当前语言无有效命令时拒绝加载。
- Query：大小写不敏感、平台命令与工具同名同时展示、文档与同名目录并存、单篇综合文档、多篇子命令列表、多级路径和未命中。
- Search：沿用已确认的中文双字片段、单字、英文单词边界、中英文混合、OR、字段范围、相关度排序、稳定排序及 --full。
- CLI/Renderer：配置切换成功/失败保护、同名文档来源标注、分页阈值、交互式与非交互式输出、普通用户提示。
- 自动化测试通过不替代真实 CLI 验收；最终必须在 Windows 11 PowerShell 和 Linux Mint 环境完成真实 CLI 验收。

### 14.6 旧结构迁移与兼容性

- 旧结构为 `commands/common/<language>/`、`commands/windows/<language>/`、`commands/linux/<language>/`。
- P6 采用一次性迁移到新结构，不要求主程序长期兼容旧目录。
- 旧 Windows/Linux 文档分别迁移到 `commands/platforms/windows/<language>/` 和 `commands/platforms/linux/<language>/`。
- 旧 Common 第三方工具文档迁移到对应的 `commands/tools/<tool>/<language>/`。例如旧 `common/zh-CN/git.md` 可迁移为 `tools/git/zh-CN/git.md` 工具入口/综合文档，具体内容结构按新规范审查，不机械复制成不符合新 Schema 的文件。
- 迁移必须保留有效知识内容、语言隔离和必要的差异说明；迁移后检查旧目录无残留、文档无丢失、同名 ID 无冲突。
- 旧平台优先/Common 回退逻辑由新类别模型取代：平台系统命令只在所选平台目录查询；第三方工具统一在 tools 目录查询，不再把平台命令和第三方工具混为同一命令命名空间。
- Windows/Linux 既有文档内容、查询、搜索、语言隔离及 CLI 管理行为必须进行回归验收。

### 14.7 P6 实施与验收顺序

1. **最小测试知识库（已完成初版）**：独立知识库仓库已搭建 `platforms/` 与 `tools/` 目录，并放入 Windows/Linux 平台命令、Git 导航与子命令、Docker 多级子命令及 SSH 单篇工具文档。样例用于验证目录与查询模型，不代表最终内容规范已冻结。
2. **主程序审计（已完成）**：已检查远程主程序文件树、主要源码模块、CLI、测试文件和依赖，形成保留、重构、删除、新增建议。远程审计结论不代替用户本地 Git 工作区状态核验。
3. **冻结新架构设计**：明确正式 Markdown 格式（TOML summary + 正文 `---` 分隔线 + Markdown 二级章节，不使用一级标题作为文档标题）、文档 Schema、唯一 ID、统一数据模型、目录及大小写规则、平台/工具独立语言发现、工具语言缺页策略、同名文档同时展示、文档与子目录并存、Query/Search 接口、模块职责与依赖方向、错误边界和测试验收契约。设计确认并写入本总控文档后，才开始清理旧实现。
4. **清理旧主程序实现并建立新骨架**：在主程序仓库中删除旧的 `src/lcmd/` 实现和旧的 `tests/`，按冻结后的最终结构重新建立源码与测试。此操作只清理旧实现，不删除 Git 仓库、不重建仓库、不清除 Git 提交历史；`pyproject.toml`、README、`.gitignore`、`.gitattributes` 等根文件逐项审查，符合新项目要求的保留并修订，不适用的删除。README 按新架构重写。
5. **实现平台/语言动态发现与配置切换**：使用临时新增的平台目录验证主程序无需代码改动即可发现并切换；验证目标平台缺少当前语言时的明确提示。保留必要配置行为，但不保留固定平台/语言枚举。
6. **实现通用知识库核心**：实现 `platforms/` 与 `tools/` 的目录发现、加载、解析、校验、精确查询和搜索；不为 Git、Docker 或其他具体工具编写特例。
7. **集成及真实 CLI 验收**：使用 Git、Docker、SSH 样例进行真实 CLI 验收；新增临时测试工具，只增加知识库文档、不修改主程序，验证扩展机制。自动化测试通过不能替代真实 CLI 验收。
8. **迁移正式知识内容并回归**：按迁移规则转换旧 Windows/Linux/Common 正式内容，删除知识库旧目录和主程序旧兼容逻辑；检查文档无丢失、无重复 ID、无旧结构残留，完成全量测试、Ruff 和真实 CLI 回归。
9. **冻结并扩充内容**：验收平台/语言发现、配置切换、工具导航、多级子命令、搜索唯一性、迁移完整性及离线行为；通过后冻结 Schema 和目录规范，再批量建设其他命令内容。

**重建范围说明：** P6 采用“清理旧实现、按新架构重建”的路线，不以旧代码复用率为目标，也不在旧架构上逐步叠加新架构。经过审查且确实适合新架构的基础实现可以重新采用，但必须以新架构职责为依据；不得为了保留旧代码而保留旧模块、旧测试或兼容分支。清理源码和测试不等于删除 Git 仓库或提交历史。

**最终目标：主程序完成这次通用架构实现后，未来增加 macOS、HarmonyOS、新语言、Git 以外的新工具或工具子命令，只需按规范扩展知识库；不因这些名称或内容新增而修改主程序。** 这不等于自动获得新操作系统的安装包、系统集成或实际运行适配。

### 14.8 新架构洁净度与旧代码清理（强制约束）

P6 不以“在旧程序上增加新功能”为完成标准，而以形成职责清晰、无历史包袱的新架构为标准。不得为了复用旧代码而保留不适合新架构的实现。

强制原则：

1. **不保留已废弃功能**：永久取消的功能不得以隐藏入口、备用实现、兼容分支或配置选项的形式继续存在。
2. **不保留无用代码**：旧常量、旧数据模型、旧函数、旧分支、重复实现、无调用代码，以及只为旧架构服务的抽象，在确认无新架构用途后删除。
3. **不保留无用文件或模块**：现有文件名和目录结构不是必须继承的约束。模块可按新职责重命名、合并、拆分或删除；不得仅因旧项目存在某文件，就在新架构中保留它。
4. **不保留旧架构兼容层**：完成一次性知识库迁移后，删除旧目录扫描、Common 回退、固定平台/语言清单及其他旧模型专属逻辑，不提供长期双格式兼容。
5. **不保留过时测试**：删除只验证废弃行为的测试；将仍有价值的产品行为重新表达为新架构测试。测试数量不是目标，覆盖正确行为和边界才是目标。
6. **避免过度设计**：不引入没有明确需求的抽象层、插件机制、注册表或间接调用。每个模块必须有清晰、独立且必要的职责。
7. **保留经过审查的有效基础**：现有实现只有在符合新架构职责、依赖边界和质量要求时才可保留；配置读写、原子保存、解析、错误隔离、终端渲染等能力也必须逐项审查，不得默认保留或默认重写。
8. **仓库最终状态必须可解释**：源码、测试、依赖、文档和构建配置均应服务于当前产品目标；删除不再使用的依赖、脚本、配置和文档，不留下“以后可能用到”的死代码。

实施要求：

- 编码前先审查当前仓库完整文件树、模块导入关系、公开 CLI、测试覆盖和依赖使用情况，形成“保留 / 重构 / 删除 / 新增”清单。
- 先设计并确认新架构的最终模块边界与依赖方向，再开始改动源码；不能先复制旧目录再逐步打补丁。
- 每次重构后运行对应测试、全量测试和 Ruff；最终检查无未使用代码、无旧架构标识、无无效依赖，并完成真实 CLI 验收。
- 不要求沿用当前文件命名。最终文件树由职责设计决定，允许与旧结构明显不同。
- 不以保留历史测试通过率为目标；以新架构的行为契约、回归覆盖、可维护性和开源协作可读性为验收标准。

**P6 的洁净度验收条件：新主程序中不存在已弃用功能、旧架构兼容代码、无用模块、死代码、无效依赖或只服务于旧实现的测试。任何保留的模块和测试都必须能说明其在当前架构中的必要职责。**
以上为 P6 目标设计与执行约束，尚未实现。

### 14.9 P6 主程序清理与重建决策（已确认）

用户已确认采用一次性清理旧主程序实现、按新架构重建的路线：

- 删除旧 `src/lcmd/` 源码实现和旧 `tests/`，按最终冻结的模块结构与新行为契约重新建立；不保留双架构并存状态。
- 不为提高代码复用率而迁就旧实现。Parser、配置读写、原子保存、终端渲染等代码只有经过审查、确认适合新架构后才可复用；否则重新实现或删除。
- 清理的是旧代码、旧测试和无用配置，不是 Git 仓库本身。保留 Git 提交历史，不删除或重建 GitHub 仓库。
- 根目录文件逐项审查：保留并修订新架构仍需要的项目配置；重写 README；删除不再使用的文件、依赖和脚本。
- 不在设计尚未冻结时立即清空源码。必须先完成第 14.7 节第 3 步列出的 Schema、数据模型、路径规则、查询行为、模块边界和依赖方向，再执行清理。
- 清理前核对用户本地 Git 状态，确保未提交的用户修改不会被覆盖；如有未提交修改，先明确处理方式。
- 重建后只维护一套当前架构、一套对应测试和本总控文档，不保留旧架构兼容层。

此决策是 P6 的正式执行约束，实际清理与重建尚未开始。

### 14.10 P6 新架构接口与数据模型冻结补充（设计已确认，尚未实现）

本节补充 14.5 的可执行数据模型和模块契约。若历史章节中的旧实现描述与本节目标设计冲突，以 14.5、14.10 的新架构契约为准；历史阶段记录只用于说明当时的实现状态，不代表新架构仍保留旧行为。

#### 数据模型

~~~python
@dataclass(frozen=True, slots=True)
class PlatformInfo:
    name: str
    languages: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class ToolInfo:
    name: str
    languages: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class KnowledgeCatalog:
    root: Path
    version: str
    platforms: tuple[PlatformInfo, ...]
    tools: tuple[ToolInfo, ...]

@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    id: str
    category: Literal["platforms", "tools"]
    platform: str | None
    tool: str | None
    language: str
    summary: str
    body: str

@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    platform: str
    language: str
    documents: tuple[KnowledgeDocument, ...]

@dataclass(frozen=True, slots=True)
class QueryResult:
    documents: tuple[KnowledgeDocument, ...]
    children: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class SearchResult:
    document: KnowledgeDocument
    score: float
~~~

- 所有数据类使用 frozen=True, slots=True；集合使用 tuple，避免向调用方暴露可变列表。
- KnowledgeCatalog.root 是知识库根目录；文档 ID 相对于 root/commands/，因此 Loader 可通过受控根目录与 ID 定位文件。
- KnowledgeDocument.category 仅为固定类别 platforms 或 tools；平台名称、工具名称和语言均为动态字符串，不使用平台/工具/语言 Literal 枚举。
- KnowledgeDocument.platform 与 tool 必须且只能有一个非空。显示名称由 ID 路径推导为只读属性，不保存重复的 name 或 title 字段。
- 平台命令显示名称为文件主文件名；工具入口 <tool>.md 显示工具名；工具子命令名称由工具名与相对语言目录的子命令路径组成。
- KnowledgeBase 不重复持有 Catalog；CLI 分别持有 Catalog 和当前 KnowledgeBase。Catalog 用于发现与配置管理，KnowledgeBase 用于查询和搜索。
- QueryResult.documents 可同时包含平台命令和工具的同名文档；children 可与 documents 同时非空。两者都为空表示未找到。
- ParsedDocument 是 Parser 的中间结果，包含完整 TOML 元数据映射和正文；Parser 不提前丢弃未知字段，Validator 校验通过后 Loader 才生成 KnowledgeDocument。

#### 配置模型与接口

- 配置文件保持现有 [knowledge] TOML 节和 path、platform、language 三个字段，不改变用户配置格式。
- 配置数据模型对应 AppConfig(path, platform, language)；path 指向知识库根目录，平台和语言只保存标识。
- core/config.py 提供配置读取和原子保存；core/paths.py 提供应用配置目录、数据目录和默认知识库路径。
- discover_catalog(root: Path) -> KnowledgeCatalog 负责整体知识库检查和全局目录发现，不解析所有 Markdown 正文。
- load_knowledge(catalog, platform, language) -> KnowledgeBase 负责加载指定平台/语言下的有效平台命令，以及具有对应语言内容的工具文档。
- query_document(knowledge, arguments) -> QueryResult 只查询内存中的已加载文档。
- search_knowledge(knowledge, keyword, full=False) -> tuple[SearchResult, ...] 只搜索内存中的已加载文档。
- parse_document(content: str) -> ParsedDocument 负责 TOML Front Matter 和 Markdown 正文分离。
- Validator 分别校验相对文档路径和 ParsedDocument Schema；Loader 负责调用顺序和单篇错误隔离。

#### 语言发现与加载边界

- Catalog 中的平台语言是目录发现阶段找到的候选语言；工具语言是每个工具独立发现的候选语言。
- 候选语言目录必须存在，并包含至少一篇路径/文件名符合规范的 Markdown 文件。
- 目录发现不解析正文；因此候选目录不等于最终有效内容。切换平台或语言时必须尝试加载目标平台语言，确认至少一篇有效平台命令文档后才保存配置。
- 加载当前平台/语言时，平台文档逐篇解析和校验；有效文档进入 KnowledgeBase，单篇失败跳过。
- 当前平台/语言没有任何有效平台命令文档时，加载失败，原配置不变。
- 工具按各自语言目录独立加载；工具缺少当前语言或其文档全部无效时跳过该工具，不进行跨语言回退，不阻断平台命令和其他工具。
- 配置路径不可用时仍可读取和显示已保存的配置值，但不能伪造可用平台/语言清单，也不能保存未经验证的新选择。

#### 异常策略

- 只建立必要的整体知识库错误边界；manifest、根目录、commands 根目录或版本兼容性错误导致本次加载失败。
- 单篇文档解析/校验错误在 Loader 内部捕获并隔离，不中止其他文档加载。
- 不为每一种文件错误建立复杂的异常继承树，不输出诊断报告、日志文件或异常堆栈给普通用户。
- CLI 将整体错误和查询未命中分别转换为已确认的用户提示；不能把整体知识库错误伪装成未找到命令。

#### 模块依赖

~~~text
cli/app.py
├── core/config.py
├── core/paths.py
├── knowledge/loader.py
│   ├── knowledge/models.py
│   ├── knowledge/parser.py
│   └── knowledge/validator.py
├── knowledge/query.py
├── knowledge/search.py
└── output/renderer.py
~~~

- Models 不依赖项目其他模块。
- Parser、Validator 不依赖 Loader、CLI、Renderer。
- Loader 依赖 Models、Parser、Validator。
- Query、Search 只依赖 Models。
- Renderer 负责显示和分页，不访问知识库文件系统，不计算搜索相关度。
- CLI 是流程协调入口；不在 CLI 内重复实现加载、解析、查询或搜索。
- 不增加没有明确产品需求的中间层、插件框架、注册表或兼容层。

#### 冻结状态

本节与 14.5 合并后，作为 P6 主程序重建的目标接口和行为契约。尚未代表代码实现或验收完成。开始清理旧源码前，仍须由用户在本地核对 Git 工作区状态；旧实现和旧测试只在该检查通过后一次性清理。



---

## 15. P6 主程序重建与 Windows 端验收状态（2026-11-03）

本节为当前实际进度记录；若前文历史计划或“尚未实现/尚未开始”的描述与本节冲突，以本节状态为准。P6 的 Linux Mint 跨平台验收仍未完成，因此当前不标记整个 P6 阶段最终关闭。

### 15.1 主程序提交

- 主程序仓库：`WenZoo1982/lcmd`
- 分支：`main`
- P6 实现提交：`acd0467`
- 提交说明：`feat: complete P6 knowledge architecture and CLI integration`
- 已成功推送 GitHub：`5126a20..acd0467 main -> main`
- 推送前本地工作区干净；提交包含 29 个文件，新增 3319 行、删除 1970 行。
- 旧 `knowledge/lookup.py` 与 `tests/test_lookup.py` 已删除；新 `knowledge/models.py`、`knowledge/query.py` 及其测试已加入。
- 本次提交没有包含临时配置、测试知识库或备份文件。

### 15.2 自动化与静态检查

Windows 11 开发环境最近一次验收结果：

| 检查 | 结果 |
|---|---|
| 全量 pytest | 187 passed |
| Ruff lint | All checks passed |
| Ruff format | 28 files already formatted |

自动化测试与真实 CLI 验收分别执行，不以测试通过替代实际命令运行。

### 15.3 真实知识库与 CLI 集成验收

- 真实知识库版本 `0.1.0`；Windows/Linux 与 `zh-CN`/`en-US` 四种平台语言组合均成功加载。
- 固定 CLI 入口：帮助、无参数帮助、版本、platform、language、search 均已验证。
- 动态精确查询：平台命令、工具入口、工具子命令、多级子命令、大小写不敏感和未命中提示均已验证。
- 搜索：中文/英文、多关键词 OR、`--full`、交互式分页和非交互式管道输出均已验证。
- 平台与语言切换成功；非法平台/语言切换失败后原配置保持不变。
- 知识库不可用时的降级行为已真实验证：platform/language 仍显示已保存配置；search 和动态查询返回明确错误；version 显示知识库不可用；原配置通过 SHA256 校验完整恢复。
- 使用隔离临时知识库通过 3 项特殊 CLI 集成场景：平台命令与同名工具同时显示、同名文档与子目录并存、多级子命令查询。临时测试文件自动清理。
- 正式知识库中的 Docker 目录结构已验证入口、run、compose/up 和无入口子目录导航行为。

### 15.4 P6 当前结论

<badge>Windows 端通过</badge>

P6 新架构实现、自动化测试、静态检查、真实知识库集成及 Windows 端 CLI 验收已完成。尚未完成的是 Linux Mint 22.3 环境的跨平台验收；因此 P6 阶段整体仍处于待 Linux 验收状态，不提前宣告最终关闭。

### 15.5 下一阶段：Linux Mint 22.3 跨平台验收

在 Linux Mint 22.3 x86_64 虚拟机中，从 GitHub 拉取主程序与知识库，使用独立虚拟环境安装和测试。按单步方式推进，不假设 Linux 测试机已经 clone 仓库或安装所需工具。

验收顺序：

1. 确认 Linux Mint 版本、架构和 Python 版本（项目最低 Python 3.11）。
2. 从 GitHub 拉取主程序 `WenZoo1982/lcmd`，确认代码包含提交 `acd0467`。
3. 拉取知识库 `WenZoo1982/lcmd-kb`，配置 Linux 下的知识库根目录；不得复用 Windows 绝对路径。
4. 创建 Linux 虚拟环境并安装项目开发依赖。
5. 执行全量 pytest、Ruff lint 和 format。
6. 真实 CLI 验收：帮助、版本、platform/language、中文文档显示、工具入口/多级子命令、中文搜索、分页、平台/语言切换、未命中与知识库不可用降级。
7. 重点检查 Linux 文件系统大小写行为、路径安全、UTF-8 中文输出和终端交互差异。
8. 记录结果并修复跨平台问题；完成后再复核 Git 差异并决定 P6 最终收尾。

**当前下一步仅执行 Linux Mint 测试机环境确认，不提前进行安装或修改。**
