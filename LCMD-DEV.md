# LCMD 项目开发总控文档

> 本文档是 LCMD 唯一的开发总控入口。记录已确认的产品设计、技术约束、开发阶段和经核验的实际状态。每次继续开发，先阅读本文档，再核对本地代码、测试结果、Git 状态和 GitHub 远程状态。计划不代表已实现；历史测试结果不代表当前代码已通过测试。

- 主程序仓库：https://github.com/WenZoo1982/lcmd
- 知识库仓库：https://github.com/WenZoo1982/lcmd-kb
- 本地项目目录：D:\Project_DEV\lcmd
- 当前开发阶段：P3.3 CLI 行为补齐；P3.2 配置路径与 common 回退已完成代码审查、测试验收、提交并推送
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
- 首发语言为简体中文；文档应简洁、准确、易懂、可复制，对高风险操作给出必要提醒。

## 2. 平台与发行范围

| 平台 | 首发 | 说明 |
|---|---|---|
| Windows x64（Intel/AMD，AMD64） | 支持 | 独立 .exe 安装程序 |
| Linux AMD64（x86_64） | 支持 | Debian 系 .deb，首发面向 Linux Mint、Ubuntu、Debian |
| Linux ARM64 | 暂不支持 | 后续按需求增加 |
| macOS Intel | 暂不支持 | 后续增加独立构建与测试 |
| macOS Apple Silicon（ARM64） | 暂不支持 | 后续增加独立构建与测试 |
| Windows ARM64 | 暂不支持 | 后续评估 |

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
    ├── commands/
    │   ├── common/zh-CN/
    │   ├── linux/zh-CN/
    │   ├── windows/zh-CN/
    │   └── macos/zh-CN/
    └── tasks/
        ├── common/zh-CN/
        ├── linux/zh-CN/
        ├── windows/zh-CN/
        └── macos/zh-CN/

- commands 与 tasks 分开管理；一条命令一个 Markdown 文件，文件名为命令正式名称。
- common 收录跨平台工具的通用知识，例如 Git、Python、Docker；不是操作系统预装命令的集合。
- Linux Mint、Ubuntu、Debian 共用 Linux 知识目录，不按发行版拆分。
- Linux 首发以 GNU 命令体系为基准，优先覆盖 Ubuntu 22.04 / Debian 12 这一代系统常见 GNU 工具；较新参数在文档中标注版本要求。不专门支持 BusyBox/Toybox。
- 同名命令优先使用平台专属文档；平台专属文档不存在时回退到 common。例如 Linux 查询 Git：先查 commands/linux/zh-CN/git.md，未命中再查 commands/common/zh-CN/git.md。平台文档命中后立即返回，不合并显示 common 文档。
- tasks 使用相同的“当前平台优先、common 回退”规则。
- 知识库允许逐步收录命令。目录为空或某条命令尚未收录，不代表知识库无效。

### 文档格式

命令和任务文档使用 UTF-8 Markdown + TOML Front Matter：

- 必填 summary：非空字符串。
- 任务文档可选 commands：字符串数组，缺省按空数组处理。
- 不设置 keywords、aliases。
- 命令名称、平台、语言从目录和文件名推导。
- Parser 负责解析 Front Matter；Validator 负责 Schema 校验；Loader 负责发现、加载和汇总诊断。
- 单篇文档错误隔离：跳过无效文档并报告路径和原因，其他有效文档继续加载；知识库根目录、manifest 或兼容性错误属于整体错误。

## 4. 配置与路径设计

配置文件由 platformdirs.user_config_path() 定位，内容示意：

    [knowledge]
    platform = "linux"
    language = "zh-CN"

    # 可选。必须是绝对路径；不设置时使用 platformdirs 默认用户数据目录。
    # path = "D:/LCMD/knowledge"

- 配置保存 platform、language，以及可选的知识库根目录 path。
- path 指向知识库根目录，不是 commands/<platform>/<language> 子目录；必须是绝对路径。
- 未设置 path 时使用 platformdirs.user_data_path() 下的默认知识库目录。
- 缓存和更新临时文件使用 platformdirs.user_cache_path()；配置目录使用 platformdirs.user_config_path()。
- 安装程序首次安装时检测运行平台和系统语言，生成初始配置。主程序运行时读取配置，不反复检测系统语言或擅自更改平台。
- 用户手动切换平台/语言，只修改配置字段，按新配置检索；不要求用户更换实际操作系统。
- 不再支持 LCMD_KNOWLEDGE_DIR 环境变量覆盖。
- 不静默切换到其他路径、平台或语言。

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
- Major 按项目已确认的兼容基线规则管理；用户定义 Major 与支持平台数量对应。新增平台支持时，主程序和知识库同步提升 Major。
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
| lcmd <command> | 查询当前配置平台的命令文档 |
| lcmd <command> --full | 扩展资料入口，具体行为待对应阶段实现 |
| lcmd search <keyword> | 搜索命令和任务知识 |
| lcmd task <task-name> | 查询任务指南 |
| lcmd platform [name] | 查看或切换知识平台 |
| lcmd language [name] | 查看或切换知识语言 |
| lcmd --update | 统一检查并更新主程序、知识库 |

- 命令名称精确匹配，不区分大小写。
- 查询顺序：当前平台目录优先，未命中再查 common；两者都未命中才提示知识库尚未收录。
- 不检查系统命令是否存在，不执行用户输入；普通查询不联网。

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
| P3.3 | 补齐现有 CLI 合同 | `--version` 同时显示主程序和本地知识库版本；统一帮助/错误提示文案；只处理明确的 CLI 行为差异 | 对应测试通过；帮助、版本、未收录提示真实运行符合第 6 节 |
| P4 | 内容搜索 | 搜索 commands 和 tasks；覆盖名称、summary、正文；明确多关键词规则、排序和数量限制；离线运行 | 搜索规则有测试；命令行输出清晰；无结果提示准确 |
| P5 | 任务指南 | `lcmd task <name>`；任务文档加载、查询、关联命令校验 | 平台优先/common 回退规则一致；有效任务可查；无效关联有诊断 |
| P6 | 平台与语言管理 | `platform`、`language` 查看和切换；配置持久化与输入校验 | 切换后查询结果正确；非法值不破坏原配置 |
| P7 | 知识库仓库与首批内容 | 完成 lcmd-kb 的 manifest/目录结构；编写首批高频命令和任务文档；建立内容检查流程 | 主程序可加载真实知识库；文档格式、版本和平台目录通过校验 |
| P8 | 统一更新 | GitHub Releases 版本检查、下载、校验、用户确认、替换、失败恢复 | 主程序/知识库分别更新；兼容性与失败场景有测试；普通查询仍离线 |
| P9 | 安装包与跨平台构建 | Windows x64 安装包、Linux AMD64 .deb；安装位置与用户数据分离 | 在目标系统完成干净安装、启动、升级和卸载验证 |
| P10 | 首发验收 | 整理用户文档、版本说明、Release 资产与发布检查清单 | Windows x64、Linux AMD64 首发范围逐项验收通过 |

### 执行顺序与范围控制

1. P3.2 已完成并推送；后续按 P3.3、P4、P5、P6、P7 的顺序推进。
2. P3.3 只修复已经确认的 CLI 合同差异，不借机重构 CLI。
3. P4、P5、P6 按顺序完成核心使用体验；每阶段只实现当前阶段所需能力。
4. P7 再集中建设真实知识库内容，避免主程序功能和内容编写互相阻塞。
5. P8 更新系统是高风险阶段，先完成流程设计和失败场景测试，再实现替换/回滚。
6. P9 先保证 Windows x64，再完成 Linux AMD64；不为首发加入 macOS、ARM64。
7. 不把缓存、临时目录、备份回滚等更新专用机制提前独立开发；按 P8 的实际更新流程一次性设计。
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
- 尚无 manifest.json、commands/、tasks/ 或正式知识库内容。
- 远程没有发现 GitHub Release。

### 远程源码与最终设计的已知差异

1. CLI 的 `--version` 当前只显示主程序版本，尚未显示本地知识库版本。
2. `--help` 仍出现 Typer 默认英文退出提示 `Show this message and exit.`；帮助/错误提示文案尚未统一。
3. 当前 CLI 在业务命令启动时读取配置并加载知识库；安装程序生成初始配置的流程尚未实现。
4. 尚未实现搜索、任务查询、平台/语言切换、统一更新、独立打包和安装流程。
5. 当前查询未命中时已提示知识库未收录；未实现、也不应实现系统命令发现。

上述差异需要通过后续测试和实现逐项解决，不能只修改文档后就认为代码已符合设计。

## 12. 当前状态与下一步

### 当前真实状态（2026-11-02）

#### 主程序代码

- 本地分支：`main`。
- P3.2 代码提交：`22674fea7d03343a41bfeb7ef62966bb930647ab`。
- 用户已成功执行 `git push origin main`，GitHub 返回 `be3ac2b..22674fe  main -> main`，确认代码已推送至远程 `main`。
- 提交前用户执行 `git status --short`，工作区为空；提交后没有再产生代码修改。
- 本地代码提交与本次总控文档更新分开处理；本次文档更新完成后，用户需要再 pull 文档提交。

#### P3.2 本地验收结果（由用户实际执行并反馈）

- `python -m pytest -q`：125 passed。
- `ruff check .`：All checks passed。
- `ruff format --check .`：25 files already formatted。
- `git diff --check`：未发现空白错误；Git 对部分文件提示 LF/CRLF 换行符转换，不影响提交。
- 真实 CLI 验收：Windows 专属 `where` 文档优先；common `git` 文档正确回退；未收录命令显示中文提示；`--version` 当前显示 `LCMD 0.1.0`。
- `--help` 仍出现 Typer 默认英文提示 `Show this message and exit.`；版本和帮助文案问题留在 P3.3 处理。
- 上述测试和 CLI 结果是用户在本地执行的记录；本次助手没有在 GitHub 远程执行测试。

### P3.2 已完成的交付内容

1. `AppConfig` 增加可选 `knowledge.path`，只接受绝对路径，支持 TOML 读取和保存。
2. 默认知识库路径使用 platformdirs；不再读取 `LCMD_KNOWLEDGE_DIR` 环境变量。
3. 路径计算不自动创建知识库目录；自定义路径无效时明确报错，不回退默认目录。
4. commands 和 tasks 均实现平台专属文档优先、common 逐项补充；同名文档不重复加载。
5. 六个源码/测试文件已完成差异审查；代码独立提交并推送，提交为 `22674fe`。
6. P3.2 已完成，不再重复运行已通过的测试；除非后续发现具体问题，否则不回头扩展本阶段范围。

### 下一阶段：P3.3 CLI 行为补齐

P3.3 只处理已确认的 CLI 合同差异，不重构 CLI，不提前实现搜索或任务功能。

1. `lcmd --version` / `-v`：同时显示主程序版本和本地知识库 manifest 版本；不得联网。
2. 统一 `--help` 中 Typer 默认英文退出提示及当前明确存在的帮助/错误提示文案，保持中文 CLI 体验。
3. 为版本输出、帮助输出和相关错误文案补充或调整自动化测试。
4. 使用本地知识库进行真实 CLI 验收，确认版本显示、帮助提示和未收录提示。
5. 完成定向测试、全量 pytest、Ruff lint/format、diff 审查后，独立提交并推送代码；再单独更新本总控文档。

### 后续阶段进入条件

- P3.3 完成后：进入 P4 内容搜索。
- P4 完成后：按 P5、P6、P7 顺序推进。
- P8 更新系统开始前：先冻结更新行为、版本兼容、下载验证、失败回滚规则。
- P9 打包前：主程序和知识库必须已有可用 Release 版本。
- 首发范围保持 Windows x64 与 Linux AMD64，不在首发阶段扩展 macOS/ARM64。
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
