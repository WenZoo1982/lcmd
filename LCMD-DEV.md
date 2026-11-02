# LCMD 项目开发总控文档

> 本文档是 LCMD 唯一的开发总控入口。记录已确认的产品设计、技术约束、开发阶段和经核验的实际状态。每次继续开发，先阅读本文档，再核对本地代码、测试结果、Git 状态和 GitHub 远程状态。计划不代表已实现；历史测试结果不代表当前代码已通过测试。

- 主程序仓库：https://github.com/WenZoo1982/lcmd
- 知识库仓库：https://github.com/WenZoo1982/lcmd-kb
- 本地项目目录：D:\Project_DEV\lcmd
- 当前开发阶段：P3.2 配置与知识库路径架构调整（本地验收完成，代码尚未提交/推送）；下一阶段：P4 内容搜索
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

## 10. 开发阶段计划

| 阶段 | 内容 | 验收重点 |
|---|---|---|
| P0 | 产品定位、架构和总控规划 | 设计决策明确，仓库基线核验 |
| P1 | 主程序基础框架 | 包结构、CLI、配置、路径、帮助和版本 |
| P2 | 知识库解析与加载 | Schema、Parser、Validator、Loader、错误隔离 |
| P3.1 | 命令精确查询与 Markdown 输出 | 精确匹配、大小写处理、查询输出 |
| **P3.2** | **配置与知识库路径架构调整** | 可选自定义 path、移除环境变量、common 回退、安装初始配置与运行时行为符合最终设计 |
| P4 | 内容搜索 | 命令/任务搜索、排序、限制、中文检索 |
| P5 | 任务指南 | 任务查询、命令引用校验、反向关联 |
| P6 | 平台与语言管理 | 查看/切换配置，目录和兼容性检查 |
| P7 | 统一更新系统 | Release 检查、下载、验证、用户确认、更新和回滚 |
| P8 | 独立打包与安装 | Windows x64 EXE、Linux AMD64 DEB |
| P9 | 跨平台验收与首发 | 安装、升级、异常、卸载、文档和 Release 验收 |

每阶段拆分为小任务；先写测试，再实现。完成后记录实际测试命令和结果、Git commit、未解决问题。未通过验收不得标记完成。

## 11. GitHub 与本地仓库状态核验记录（2026-11-02）

以下为公开 GitHub 远程仓库只读核验结果，不代表本地工作区状态，也不代表已在本机执行测试。

### 主程序仓库 WenZoo1982/lcmd

- 默认分支：main。
- 核验时最新提交：8713f7894a79e6693363219691fd9158857b870e，提交信息 docs: record P3.1 command lookup completion。
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

1. core/config.py 的 AppConfig 只有 platform、language，没有可选 path。
2. core/paths.py 仍支持 LCMD_KNOWLEDGE_DIR 环境变量。
3. 当前 Loader 只扫描配置平台目录，尚未实现 common 回退。
4. 当前 CLI 在业务命令启动时读取配置并加载知识库；安装程序生成初始配置的流程尚未实现。
5. 当前 lcmd --version 只显示主程序版本，尚未显示知识库版本。
6. 当前查询未命中时已提示知识库未收录；未实现、也不应实现系统命令发现。
7. 尚未实现搜索、任务查询、平台/语言切换、统一更新、独立打包和安装流程。

上述差异需要通过后续测试和实现逐项解决，不能只修改文档后就认为代码已符合设计。

## 12. 当前状态与下一阶段任务

### 当前状态

- P1、P2、P3.1 的本地代码曾于 2026-11-02 重新验收通过：`python -m pytest` 为 115 passed，`ruff check .` 全部通过，`ruff format --check .` 为 25 files already formatted。
- 上述为 P3.2 开发前的历史测试结果，不代表 P3.2 当前代码的测试结果。
- P3.2 已在本地完成代码实现、自动化测试和真实 CLI 验收；相关代码尚未提交或推送到 GitHub。
- 本次 GitHub 文档更新仅更新 `LCMD-DEV.md`，不包含本地 P3.2 业务代码和测试文件。

### P3.2 配置与知识库路径架构调整：已完成本地验收

实现内容：

1. 配置模型：`[knowledge]` 增加可选 `path`，只接受绝对路径；支持配置读取和保存。
2. 路径模块：默认路径使用 platformdirs；自定义路径由配置指定；不再读取 `LCMD_KNOWLEDGE_DIR`。
3. 路径验证：检查知识库根目录存在性和目录类型；计算路径时不自动创建目录；自定义路径无效时不回退默认路径。
4. Loader：commands 和 tasks 均实现平台文档优先、common 逐项补充；同名文档优先使用平台版本，不重复加载。
5. 测试：覆盖配置、路径、命令回退、任务回退及同名覆盖等场景。

本地阶段验收结果（2026-11-02，用户实际执行并提供输出）：

- `python -m pytest -q`：125 passed。
- `ruff check .`：All checks passed。
- `ruff format --check .`：25 files already formatted。
- `git diff --check`：未发现空白错误；Git 对部分文件提示 LF/CRLF 换行符转换。
- 真实 CLI 自定义知识库路径测试：通过。
- 平台优先测试：`lcmd where` 显示 Windows 专属文档，没有重复显示 common 文档。
- common 回退测试：`lcmd git` 正确显示 common Git 文档。
- 未收录命令测试：正确显示中文未收录提示。
- `lcmd --help`：正常显示帮助信息；其中 “Show this message and exit.” 仍为 Typer 默认英文提示。
- `lcmd --version`：实际输出 `LCMD 0.1.0`。
- CLI 测试后已恢复原配置；测试知识库保留在用户数据目录。
- 当前本地工作区有 6 个代码/测试文件修改，另有本地 `LCMD-DEV.md` 修改；尚未提交、推送。GitHub 文档更新后，应只恢复本地文档文件并拉取远程文档提交，不得覆盖 6 个代码/测试文件。

### 已知待处理差异

- 第 6 节设计要求 `lcmd --version` 显示主程序及本地知识库版本；当前实际只显示主程序版本 `LCMD 0.1.0`。该差异如实保留，后续需安排实现与测试，不得标记为已完成。
- `--help` 中 Typer 默认英文退出提示可在后续界面文案优化时处理。
- 缓存目录、更新临时目录和更新回滚目录尚未实现，按 P7 更新系统阶段规划；安装位置与用户数据分离按 P8 打包安装阶段处理。
- P3.2 代码尚未提交/推送；远程源码仍是 P3.2 实现前的历史状态。不得把本次远程文档提交误认为代码已同步。

### 下一阶段：P4 内容搜索

P3.2 本地验收结束后，下一步先进行 P4 需求和现有代码核对：

1. 明确搜索对象：命令文档和任务文档。
2. 明确搜索范围：标题/文件名、summary、正文；是否支持多关键词和大小写处理。
3. 设计结果排序、数量限制和无结果提示。
4. 先为搜索规则编写测试，再实现搜索逻辑和 CLI。
5. 保持普通查询与搜索离线，不引入联网搜索。
6. 在开始 P4 代码前，先处理 P3.2 本地代码提交/推送与远程同步；不覆盖用户未提交修改。

**当前不提前开始 P4 编码。先完成 P3.2 代码的 Git 提交、推送和远程核验。**

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
