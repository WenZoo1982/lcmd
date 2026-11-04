# LCMD 项目开发总控文档

> 本文档是 LCMD 项目的唯一开发总控入口。它以当前主程序仓库实际代码和已经完成的跨平台/真实 CLI 验收为基线。**已实现、已测试、已确定但未实现、尚未讨论**必须明确区分。后续每次开发开始前，先阅读本文档，再核对本地代码、Git 状态和 GitHub 远程状态；不得把计划写成现成功能。

- 主程序仓库：<https://github.com/WenZoo1982/lcmd>
- 知识库仓库：<https://github.com/WenZoo1982/lcmd-kb>
- Windows 主程序目录：`D:\Project_DEV\lcmd`
- Windows 知识库目录：`D:\Project_DEV\lcmd-kb`
- Linux Mint 测试目录：`~/lcmd`、`~/lcmd-kb`
- 当前代码基线：主程序 `main` 分支，最新代码提交 `c333bdd`（`build: add PyInstaller onedir configuration`）；此前启动迁移恢复提交 `1f28b23`、迁移进度提交 `6ad27f3`、CLI 迁移接入提交 `7024d8d78fee4364a36b0836d2a1187606b92e0f`、CLI 配置入口提交 `dc192a8268eb2f3ddbbac52c26e6e896d1121a98`，迁移核心实现提交 `a516d4cd6681639c7a091413028df2d8b2bb6e27`
- 当前阶段：P6 架构及跨平台验收完成；阶段一任务 1“CLI 参数与命令结构调整”、任务 2“知识库路径迁移 CLI 集成”和任务 3“启动时接入迁移恢复”均已完成。阶段二任务 1“Windows 打包与安装部署架构设计”和任务 2“PyInstaller onedir 打包验证”已完成；任务 3“随包知识库与发行完整性校验”待开始。启动时会先调用 `recover_migration()`，再读取配置和加载知识库。
- 当前程序版本：`0.1.0`
- 当前知识库版本：`0.1.0`（本轮 Windows 实际测试输出；便携目录动态查询和搜索读取的是本机现有测试知识库，并非随包知识库）

---

## 1. 产品定位

LCMD 是面向命令行用户的多平台命令速查与学习工具，核心理念：

**少记忆，易理解；需要时快速查找。**

核心使用场景：

1. **知道命令，查用法**：例如 `lcmd ls`，直接查询已知命令的知识文档。
2. **不知道命令，按功能找**：例如 `lcmd search "复制文件"`，根据用户想完成的任务寻找可能相关的命令或工具。

产品表达：**知道命令，查用法；不知道命令，按功能找。**

产品边界：

- LCMD 读取本地知识库并展示知识内容，不执行用户输入的系统命令或文档中的示例命令。
- 不检测目标命令或第三方工具是否安装；知识库中有文档即可查询，与本机是否安装该命令无关。
- 当前普通查询和搜索不联网。
- LCMD 不是官方手册的完整镜像。知识库内容面向快速查阅和初学者理解，优先说明用途、基本语法、高频常用参数、常用示例和必要注意事项，不追求罗列全部参数。
- 命令内容质量与主程序功能必须区分：主程序负责发现、加载、解析、查询和展示；知识库作者负责筛选高频参数、组织内容、核对示例和补充必要提醒。当前 Validator 不会强制检查固定章节或内容质量。

## 2. 仓库与职责边界

主程序和知识库是两个独立仓库：

| 仓库 | 职责 |
|---|---|
| `WenZoo1982/lcmd` | CLI、配置、路径定位、知识库发现/加载、解析/校验、查询、搜索、终端渲染 |
| `WenZoo1982/lcmd-kb` | Manifest 和 Markdown 知识文档 |

两者独立维护。新增平台、语言、工具或命令内容，原则上只修改知识库目录和 Markdown，不应因此修改主程序。主程序只在通用机制确有缺陷或需要新增通用能力时修改。

当前程序不包含知识库下载、更新、安装程序、自定义路径 CLI 管理入口。不得因为总控文档讨论过这些方向，就将它们描述为已经实现。

## 3. 当前知识库目录与文档合同

本节是知识库维护者的目录、命名和文档编写说明。必须区分三个概念：`manifest.json` 声明知识库版本；目录层级表达内容归属；Markdown 文件名标识具体命令或工具入口。

### 3.1 当前知识库目录

知识库仓库：`WenZoo1982/lcmd-kb`  
Windows 本地目录：`D:\Project_DEV\lcmd-kb`

当前实际模板：

```text
lcmd-kb/
├── manifest.json
└── commands/
    ├── platforms/
    │   ├── linux/
    │   │   ├── en-US/
    │   │   └── zh-CN/
    │   └── windows/
    │       ├── en-US/
    │       └── zh-CN/
    └── tools/
        ├── docker/
        │   └── zh-CN/
        │       └── compose/
        ├── git/
        │   ├── en-US/
        │   └── zh-CN/
        └── ssh/
            └── zh-CN/
```

这只是当前模板，不代表每个平台或工具必须同时提供中英文。语言目录按实际内容添加；未来可以增加日文等其他语言。不同平台、工具可以拥有不同的语言集合。当前语言缺失或没有有效文档时，程序不静默回退到其他语言。

### 3.2 manifest.json：知识库版本声明

`manifest.json` 位于知识库根目录，与 `commands/` 同级。当前格式：

```json
{
  "version": "0.1.0"
}
```

当前主程序实际规则：

- 文件必须存在。
- 必须包含 `version`，且值必须符合三段式 SemVer 格式。
- 当前只允许 `version` 一个字段，不接受额外字段。
- 当前主程序支持的知识库 Major 版本固定为 `0`；Major 不为 `0` 时拒绝加载。
- Minor 和 Patch 可独立变化，不要求与主程序版本相同。
- 主程序和知识库是独立仓库、独立版本；这里声明的是知识库版本。

Manifest 不负责列出平台、语言、工具或命令，不是目录索引，也不记录每篇 Markdown 的路径或摘要。主程序通过扫描 `commands/` 下的实际目录和文件动态发现这些内容。当前 Manifest 也不负责下载、更新或安装知识库。

### 3.3 目录名称与层级：表达内容归属

平台命令路径：

```text
commands/platforms/<platform>/<language>/<command>.md
```

第三方工具路径：

```text
commands/tools/<tool>/<language>/...
```

| 路径段 | 含义 |
|---|---|
| `commands/` | 所有知识文档的统一根目录 |
| `platforms/` | 操作系统或平台自身提供的命令 |
| `platforms/linux/` | Linux 平台命令 |
| `platforms/windows/` | Windows 平台命令 |
| `<platform>/` | 平台标识，例如 linux、windows 或未来平台 |
| `tools/` | 第三方工具或独立软件的命令文档 |
| `tools/git/` | Git 工具文档 |
| `tools/docker/` | Docker 工具文档 |
| `<language>/` | 文档语言，例如 zh-CN、en-US，未来可增加 ja-JP |
| 工具语言目录下的子目录 | 表示工具子命令层级，例如 Docker Compose |

平台命令和第三方工具必须放在各自类别下。Git、Docker、SSH 等第三方工具放在 `tools/`；Linux 的 `ls` 等平台命令放在 `platforms/`。

平台名、工具名和语言目录由主程序动态发现，不是写死的允许值。新增受当前架构支持的平台、工具或语言，按目录约定添加即可，不应仅因新增知识内容而修改主程序。

### 3.4 文件名：标识命令或工具入口

文件名与所在目录共同决定文档身份。

平台命令示例：

```text
commands/platforms/linux/zh-CN/ls.md
commands/platforms/windows/zh-CN/dir.md
```

工具入口页使用工具目录同名文件，即 `<tool>.md`，不是 `index.md`：

```text
commands/tools/git/zh-CN/git.md
commands/tools/docker/zh-CN/docker.md
```

工具子命令通过目录层级和 Markdown 文件名表达。例如：

```text
commands/tools/docker/zh-CN/docker.md
commands/tools/docker/zh-CN/run.md
commands/tools/docker/zh-CN/compose/up.md
```

对应查询：

- `lcmd docker`：查询 Docker 工具入口。
- `lcmd docker run`：查询 Docker 的 run 子命令。
- `lcmd docker compose up`：查询多级子命令 compose up。

工具入口页规则：

- 存在 `<tool>.md`：显示入口文档，并根据目录结构列出可用的直接子命令。
- 没有入口页且只有一篇有效 Markdown：直接显示唯一文档。
- 没有入口页且有多篇有效 Markdown：列出文档，不擅自选择其中一篇。

文件名参与命令身份识别和查询路径解析，不只是展示标题。新增或重命名文件时，应同时考虑用户实际输入的命令路径。

### 3.5 目录和文件命名规则

当前 Loader 对目录名、Markdown 文件名和路径执行安全检查：

- 平台、工具、子命令路径段使用小写 ASCII slug，例如 `linux`、`windows`、`git`、`compose`。
- 语言目录使用语言标签，例如 `zh-CN`、`en-US`。
- 避免空格、大小写混合名称和任意自然语言作为路径段。
- 拒绝符号链接逃逸、解析后路径越出知识库根目录等情况。
- 检查规范化命名冲突及 Windows 保留设备名等风险。
- 避免同一目录出现仅大小写不同、在不同文件系统上可能冲突的名称。

### 3.6 Markdown 文档格式

每篇文档使用 UTF-8 编码和 TOML Front Matter。示例：

```markdown
+++
summary = "列出目录中的文件和子目录，并控制显示格式或隐藏文件。"
+++
---

## 用途

查看当前目录或指定目录中的内容。

## 基本语法

```bash
ls [选项] [路径]
```

## 常用参数

| 想要做什么 | 命令 | 说明 |
|---|---|---|
| 查看当前目录 | `ls` | 简要列出内容 |
| 查看详细信息 | `ls -l` | 显示权限、大小和时间等信息 |
| 显示隐藏文件 | `ls -a` | 同时显示以点开头的项目 |
| 以易读单位显示大小 | `ls -lh` | 文件大小使用 KB、MB 等单位 |

## 常用示例

```bash
ls -lah ~/Downloads
```

以详细格式显示下载目录中的所有项目，包括隐藏文件。

## 必要注意事项

不同 Unix-like 系统可能使用不同实现；本知识库 Linux 内容以常见 GNU 工具行为为基准。
```

当前程序实际校验：

- 文档以独立行 `+++` 开始，并存在结束 `+++`。
- Front Matter 是合法 TOML，且必须且只能包含非空字符串字段 `summary`。
- Front Matter 结束后的正文，第一条非空行必须是 `---`。
- 分隔线之后的正文不能为空。
- Parser 解析并分离元数据与正文。
- Validator 不强制固定章节名称、顺序、参数数量或示例数量。
- 单篇文档解析或校验失败时跳过该文档，其他有效文档仍可加载。

### 3.7 内容编写规范：作者负责，不是程序强制规则

LCMD 面向命令行初学者，也面向熟悉命令但一时忘记用法、需要快速查阅的用户。文档应围绕用户想完成的任务，提供简短、准确、容易理解的说明。

作者规范：

- 只展示高频、实用的常用参数，不追求罗列全部参数。
- 使用通俗简洁的语言解释用途和参数，不照搬官方手册的长篇说明。
- 提供准确、尽可能可复制的常用示例，并解释示例的作用。
- 对容易混淆、存在平台差异或可能造成误操作的内容补充必要提醒。
- 可使用“用途、基本语法、常用参数、常用示例、必要注意事项”等章节，但不要求每篇文档必须包含全部章节，也不强制固定顺序。

可在文档中加入以下提醒：

> 本文档展示的是高频常用参数，并非该命令的全部参数。如果需要了解更多参数和完整用法，请参考对应工具或命令的官方文档。

职责边界：

- 主程序负责发现目录和文件、加载 Markdown、解析 Front Matter、校验必要结构、查询并展示内容。
- 知识库作者负责内容准确性、常用参数筛选、示例质量、表达方式和必要注意事项。
- 不得把推荐章节、参数数量、文案风格或“只展示高频参数”等作者规范，擅自变成 Parser、Validator 或 Loader 的强制技术规则。

## 4. 当前主程序实现

### 4.1 技术栈与入口

依据当前 `pyproject.toml`：

- Python：`>=3.11`
- 构建后端：setuptools
- CLI：Typer
- 终端表格/Markdown/Panel：Rich
- 用户目录定位：platformdirs
- TOML 读取：Python 标准库 `tomllib`
- 测试：pytest
- 静态检查与格式：Ruff
- CLI 安装入口：`lcmd = lcmd.main:main`
- 也支持：`python -m lcmd`
- 当前项目版本：`0.1.0`

当前源码结构：

```text
src/lcmd/
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
├── output/
│   └── renderer.py
├── __init__.py
├── __main__.py
└── main.py
```

模块职责：

| 模块 | 当前职责 |
|---|---|
| `cli/app.py` | Typer 应用、动态命令参数接管、初始化状态、配置查看与平台/语言切换、search 固定子命令及动态知识库查询 |
| `core/config.py` | AppConfig、TOML 配置读取/校验/原子保存 |
| `core/paths.py` | platformdirs 用户配置目录、配置文件和默认知识库目录 |
| `core/path_security.py` | 知识库路径规范化、安全边界检查、符号链接/Windows 重解析点检查及迁移目标校验 |
| `core/migration.py` | 知识库迁移事务、SHA-256 完整性校验、迁移日志、旧目录尽力清理与中断恢复核心逻辑 |
| `knowledge/models.py` | 平台、工具、目录、文档、查询及搜索数据模型 |
| `knowledge/loader.py` | Manifest 校验、目录动态发现、路径安全检查、Markdown 文档加载 |
| `knowledge/parser.py` | TOML Front Matter 解析并分离 Markdown 正文 |
| `knowledge/validator.py` | Front Matter 与正文结构校验 |
| `knowledge/query.py` | 平台命令、工具入口和多级子命令的精确查询 |
| `knowledge/search.py` | 关键词拆分、字段匹配、相关度评分和排序 |
| `output/renderer.py` | 文档 Panel、子命令列表、搜索结果表格及交互分页 |
| `main.py` / `__main__.py` | 程序启动入口 |

### 4.2 当前 CLI 命令

当前 CLI 真实提供：

| 调用 | 当前行为 |
|---|---|
| 调用 | 当前行为 |
|---|---|
| `lcmd --help` / `-h` | 显示 Typer 帮助 |
| `lcmd --version` / `-v` | 显示主程序版本及本地知识库版本；版本入口独立处理，不进入普通知识库查询 |
| `lcmd --config` / `-c` | 显示当前知识库路径、平台和语言 |
| `lcmd -c --platform` / `lcmd -c -p` | 显示当前平台及知识库发现的可用平台 |
| `lcmd -c --language` / `lcmd -c -l` | 显示当前语言及当前平台提供的语言 |
| `lcmd -c --platform linux` / `lcmd -c -p linux` | 验证并切换平台，成功后持久化 |
| `lcmd -c --language en-US` / `lcmd -c -l en-US` | 验证并切换语言，成功后持久化 |
| `lcmd -c -p linux -l zh-CN` | 验证最终平台/语言组合后一次性保存配置 |
| `lcmd -c --path <目录>` | 调用 `migrate_knowledge()` 迁移知识库；目标已存在时询问是否覆盖，显示复制字节百分比进度、迁移成功/失败及旧目录清理警告 |
| `lcmd --update` / `-u` | 当前仅提示知识库更新功能尚未实现 |
| `lcmd <command>` | 查询当前平台/语言的知识文档 |
| `lcmd <tool>` | 显示工具入口页和可用子命令；无入口页时按单篇/多篇规则处理 |
| `lcmd <tool> <subcommand...>` | 按路径查询工具子命令文档，支持多级路径 |
| `lcmd search <keyword...>` | 按一个或多个关键词搜索 |
| `lcmd search <keyword...> --full` | 在普通搜索字段基础上扩展到文档全文 |

固定子命令只有 `search`；`platform`、`language` 等普通名称已恢复为动态知识库查询。

当前仍未实现：


- `--update` 对应的在线检查、下载和更新机制。
- 最终完整帮助文档；当前帮助仍由 Typer 根据参数定义生成。
- 系统命令执行、系统命令安装检测或在线搜索功能。

`--path`、`--platform`、`--language` 必须配合 `--config/-c`；`--path` 与平台/语言设置互斥。平台和语言可单独或同时修改。

### 4.3 动态命令解析与查询

- Typer 使用自定义 `DynamicTyperGroup`。唯一固定子命令是 `search`；程序级选项按 CLI 自身规则处理，其他未注册名称作为动态知识库查询参数。`platform`、`language` 不再是固定子命令。
- 单参数查询同时匹配当前平台命令和同名第三方工具。
- 平台命令按文件名精确匹配（查询参数大小写规范化为小写）。
- 工具查询从当前语言工具文档集合中识别入口文件 `<tool>.md`。
- 有入口文件时显示入口文档，同时从文件路径推导直接子命令。
- 无入口文件且只有一篇有效文档时显示该文档。
- 无入口文件且有多篇有效文档时显示文档列表/结果，不随意选择其中一篇。
- 多级子命令路径由参数段映射到目录和最后一个同名 Markdown 文件；查询可以同时返回匹配文档和下级子命令。
- 当前语言目录缺失时，不跨语言回退。

### 4.4 知识库发现、加载与版本

- 知识库根目录必须有 `manifest.json` 和 `commands/platforms`。
- Manifest 当前只允许 `version` 一个字段，采用三段式 SemVer 格式。
- 当前主程序代码将支持的知识库 Major 固定为 `0`；Major 不为 `0` 时拒绝加载。Minor/Patch 不要求与主程序版本相等。
- 平台目录、平台语言目录、工具目录、工具语言目录由实际文件系统动态发现。
- 平台/工具目录和文档 slug 采用小写 ASCII 规则；语言目录按语言标签格式检查。
- Loader 检查根目录、符号链接、路径解析后的根目录边界、目录名冲突和 Windows 保留设备名。
- 平台命令文档从当前 platform/language 加载；第三方工具文档从各工具当前 language 加载。没有当前语言目录或没有有效文档的工具不会阻断平台命令加载。
- 当前平台/语言没有有效平台命令文档时，`load_knowledge` 报错。
- 单篇文档失败时隔离该文档，不使其他文档失效。
- 当前代码未实现知识库版本的远程检查、下载或替换。

### 4.5 搜索与分页

普通搜索字段及权重（当前 `search.py` 实现）：

| 字段 | 权重 |
|---|---:|
| 文档名称、工具名及完整子命令路径 | 10 |
| Front Matter `summary` | 6 |
| 正文中的“用途”章节 | 3 |

- 中文查询会拆分为连续双字片段，并保留完整中文片段；单个汉字作为一个片段。
- 英文按单词 token 处理，匹配使用单词边界。
- 完整关键词命中会增加额外分数；多关键词覆盖率也会增加分数。
- `--full` 在上述字段基础上加入全文正文，权重为 1。
- 结果按分数降序排列；同分时按文档 ID 排序。
- 搜索范围是当前已加载知识库，即当前平台命令和当前语言可用的工具文档。
- 分页由 `render_search_results()` 实现，默认每页 5 条。
- 结果不超过 5 条时一次显示；超过 5 条时，只有在 Rich Console 为终端且标准输入为交互终端时才启用交互分页。
- 分页提示为“按 Enter 查看下一页，按 Q 退出”；Enter 显示下一页，Q 退出。最后一页显示后自动结束。
- 非交互终端中即使结果超过 5 条，也一次性输出，不等待输入。
- 分页不是 search 命令参数，不存在 `--page` 或 `--size`。

## 5. 当前配置与路径实现（不是未来设计）

### 5.1 配置数据结构

当前 `AppConfig`：

- `knowledge_path: Path | None`
- `platform: str = "windows"`
- `language: str = "zh-CN"`

配置文件由 platformdirs 定位：

- 配置目录：`user_config_path("lcmd", appauthor=False)`
- 配置文件：配置目录下的 `config.toml`
- 默认知识库目录：`user_data_path("lcmd", appauthor=False) / "knowledge"`

当前配置文件结构严格为：

```toml
[knowledge]
path = "D:/path/to/lcmd-kb"
platform = "windows"
language = "zh-CN"
```

注意：当前 `load_config()` 要求 `[knowledge]` 必须且只能包含 `path`、`platform`、`language` 三个字段；配置文件中不能省略 `path`。当配置文件不存在时，程序以默认知识库路径和默认 platform/language 初始化；成功加载知识库后保存初始配置。

### 5.2 当前初始化和切换行为

- `initialize_state()` 读取现有配置；若配置文件不存在，则使用默认路径、默认平台和默认语言。
- 如果配置文件存在但配置内容无效，初始化会抛出配置错误；CLI 显示初始化失败。
- 若知识库目录或当前平台/语言加载失败，初始化返回知识库不可用状态，不会自动切换到其他语言或知识库路径。
- 只有知识库成功加载且配置文件原本不存在时，才写入初始配置。
- `platform` / `language` 切换先尝试加载目标知识库状态，成功后保存配置；失败时保留原配置。
- 切换 platform/language 时保留现有知识库路径。
- `--version` 单独读取配置和 Manifest 版本，不加载 Markdown 文档，也不创建或写入配置。

### 5.3 当前路径管理能力与剩余限制

- 用户可通过 `lcmd -c` 查看当前知识库路径，通过 `lcmd -c --path <目录>` 执行知识库迁移。
- CLI 调用 `migrate_knowledge()`，目标目录已存在时通过交互确认后才以 `overwrite=True` 重试；用户拒绝时取消迁移，不改动配置。
- 迁移失败会显示错误并以退出码 1 退出；旧知识库清理警告会显示给用户，但迁移仍报告成功。
- CLI 使用 Rich 进度条显示知识库文件复制的字节百分比；该进度仅覆盖复制阶段，不代表完整性校验、配置切换和旧目录清理的整体进度。
- 当前没有安装器负责把知识库部署到默认数据目录，也没有独立的备份、回滚或恢复默认路径功能。
- `recover_migration()` 已接入启动流程；启动时先执行迁移恢复，再读取配置和初始化知识库。

## 6. 当前已完成测试与验收

以下结果来自本轮用户实际执行的命令输出、此前 Linux VM 测试记录及 GitHub 同步记录。测试结果是该次验收证据，不代表未来任何代码修改后自动继续有效。

### 6.1 Linux Mint 22.3 自动化检查

主程序仓库在 Linux VM 中执行：

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

结果：

- pytest：187 passed
- Ruff lint：All checks passed
- Ruff format：28 files already formatted

当时主程序与知识库均与对应 `origin/main` 同步，工作区干净。Linux 主程序同步到提交 `d2b40a5`，知识库提交为 `4ad7071`。

### 6.2 Windows 11 本轮真实 CLI 验收

测试入口：在 `D:\Project_DEV\lcmd` 使用项目虚拟环境运行：

```powershell
.\.venv\Scripts\python.exe -m lcmd
```

本轮确认结果：

| 测试项 | 实际结果 |
|---|---|
| `--version` | 显示 LCMD 0.1.0、知识库 0.1.0 |
| 默认知识库 | Windows 中文 `dir` 文档可正常加载；`ls` 未命中是因为测试知识库没有对应 Windows 文档，不是程序缺陷 |
| 平台切换 | Windows 切换到 Linux 成功；Linux `ls` 文档正常显示 |
| 功能搜索 | `search "当前目录"` 返回 5 条结果，包含平台命令和第三方工具文档 |
| 全文搜索 | `search --full "隐藏文件"` 返回结果，`ls` 排序靠前；与普通搜索结果排序存在差异 |
| 平台持久化 | 关闭并重新打开 PowerShell 后，当前平台仍为 Linux |
| 语言读取/切换 | 当前语言可读取为 zh-CN；切换到 en-US 成功 |
| 英文文档 | Linux `ls` 英文文档的章节、表格和示例正常渲染 |
| Git 工具入口 | `lcmd git` 显示 Git 导航页及 `init` 子命令 |
| Git 子命令 | `lcmd git init` 正常显示英文文档 |
| Docker 工具入口 | en-US 下没有 Docker 文档，查询未命中；切换 zh-CN 后入口正常显示 `run`、`compose` |
| Docker 子命令 | `lcmd docker run` 正常显示；`lcmd docker compose up` 正常显示三级路径文档 |
| 搜索分页 | 使用 `search "的" --full` 得到 6 条结果；第一页显示 1–5，第二页显示 6；Enter 翻页正常，最后一页结束正常 |

关于 Docker 的语言行为：当前知识库只有 Docker `zh-CN` 文档；当前语言为 `en-US` 时不回退到中文，返回未找到；切换到 `zh-CN` 后正常显示。这是当前设计预期，不是故障。

分页实测时第一页提示“按 Enter 查看下一页，按 Q 退出”；本轮实际观察到 Enter 进入第二页并正确显示第 6 条。Q 退出分支由代码实现，但本轮记录不把它标记为本轮实际按键验收。

### 6.3 Windows 11 CLI 知识库迁移集成与进度显示自动化检查（提交 `6ad27f3`）

用户在 Windows 11、Python 3.14.10 环境中，对 `D:\Project_DEV\lcmd` 执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
git diff --check
```

结果：

- CLI 定向测试：52 passed
- 全量测试：252 passed
- Ruff lint：All checks passed
- Ruff format：32 files already formatted
- `git diff --check`：通过（Git 显示 LF 将在后续操作时转换为 CRLF 的换行符提示，不是 diff 空白错误）

本轮在 `cli/app.py` 中将 `progress_callback` 接入首次迁移和确认覆盖后的迁移调用，并使用 Rich 显示复制字节进度；该百分比只代表文件复制阶段，不代表完整迁移流程。`tests/test_cli.py` 验证两种迁移调用均传递回调，并通过模拟回调执行验证 CLI 可正确处理进度更新。原有覆盖确认、取消、迁移错误和清理警告测试继续通过。迁移核心实现及其 SHA-256 完整性校验、配置切换和恢复边界未修改。**本轮未进行真实磁盘路径的人工迁移 CLI 验收。**

---

## 7. 当前仓库与同步基线

主程序 `main` 分支当前代码提交为 `c333bdd`（`build: add PyInstaller onedir configuration`），完整提交 SHA 为 `c333bdde94343d8991a3b30bf21c6cdaed145758`，用户已在 Windows 本地完成 commit 和 push。当前远程 `LCMD-DEV.md` 由本次文档同步提交更新；文档提交完成后，用户再在本地执行 `git pull --ff-only origin main`。

本次代码提交新增根目录 `lcmd.spec`，并在 `pyproject.toml` 的 dev 可选依赖中增加 `pyinstaller>=6.22,<7`。用户在 Windows 11 build 26300、Python 3.14.10、PyInstaller 6.22.3 环境中完成 onedir 构建、便携目录复制、help/version、动态查询和搜索验证；全量 pytest 为 251 passed、4 skipped，Ruff lint/format 通过。动态查询和搜索使用本机现有测试知识库，正式随包知识库尚未实现；PATH 隔离不等同于完全无 Python 的干净机器测试。详细证据见第 6.6 节。

---

## 8. 当前阶段结论与已确认的后续产品设计

### 8.1 当前阶段状态

**已完成：P6 主程序与知识库通用架构。** 已完成主程序/知识库分离、目录动态发现、平台与语言加载、工具入口和多级子命令查询、功能搜索、全文搜索及交互分页，并完成 Windows 与 Linux Mint 环境的阶段性测试和 CLI 验收。证据见第 6、7 节。

**阶段一进度：**

- **已完成——任务 1：CLI 参数与命令结构调整。** 配置查看、平台/语言查看与切换、组合切换、`--update/-u` 占位提示、动态查询命令结构已实现并提交。
- **已完成——任务 2：知识库路径迁移 CLI 集成。** `--path` 已接入 `migrate_knowledge()`，覆盖确认、用户取消、迁移错误、清理警告及 Rich 复制字节百分比进度均已实现；代码提交 `7024d8d` 完成主体集成，`6ad27f3` 完成进度显示。Windows CLI 定向测试 52 passed、全量测试 252 passed，Ruff lint/format 和 `git diff --check` 均通过。进度百分比仅覆盖文件复制阶段，不代表完整迁移流程。
- **已完成——任务 3：启动时接入 `recover_migration()`。** `initialize_state()` 在读取配置前调用恢复函数；恢复异常会阻止后续初始化，并由根 CLI 显示具体错误、以退出码 1 退出。

任务 1 提交：`dc192a8268eb2f3ddbbac52c26e6e896d1121a98`。任务 2 最近提交：`6ad27f3`。任务 3 提交：`1f28b23`。本轮启动恢复通过自动化测试验证；未进行真实迁移日志/磁盘清理的人工故障注入验收。

**阶段二进度：**

- **已完成——任务 1：Windows 打包与安装部署架构设计。** 已确认 PyInstaller onedir + Inno Setup 单 EXE 图形安装器的技术路线，以及用户级安装、知识库部署、PATH 和用户数据保护原则；尚无安装器实现。
- **已完成——任务 2：PyInstaller onedir 打包验证。** `lcmd.spec` 和 PyInstaller dev 依赖已提交（`c333bdd`）。Windows 11 下构建和便携目录 help/version、动态查询、搜索均已验证；全量测试 251 passed、4 skipped，Ruff 检查通过。测试边界与“尚未在完全无 Python 的干净机器验证”、测试知识库未随包部署等限制见第 6.6 节。
- **待开始——任务 3：随包知识库与发行完整性校验。** 必须先确定正式知识库版本，再建立独立发行清单和内容校验；不得将当前 integration fixtures 当作正式发行知识库，也不得扩展现有 Manifest schema。

**尚未实现：** Windows 安装器与安装初始化、主程序/知识库更新机制，以及最终完整帮助信息。以下内容是用户已确认的产品行为和开发约束，不代表代码已经实现。

### 8.2 知识库与配置文件职责（已确认）

- 主程序与知识库继续使用两个独立仓库、独立版本号。
- `manifest.json` 只声明知识库版本，当前只允许 `version` 字段；不写入用户机器上的绝对路径、平台、语言或其他用户配置。
- `config.toml` 保存用户本机配置，包括知识库路径、当前平台和当前语言。
- 知识库目录结构继续由实际文件系统动态发现；不把平台、语言或工具清单写死进 Manifest。
- 不得为了路径管理或安装流程擅自扩展 Manifest 字段，除非未来重新讨论并明确批准知识库格式变更。

### 8.3 CLI 参数空间与解析规则（设计已确认；基础入口已实现，迁移与完整帮助待完成）

LCMD 的核心用途是查询知识库中的命令文档。除固定的程序级参数和唯一固定子命令 `search` 外，普通名称应留给知识库动态查询，避免未来知识库增加命令文档时与程序子命令冲突。

**固定入口与优先级：**

1. 程序级选项：`--help`、`--version`、`--config`、`--update`。
2. 固定子命令：`search`。大小写不敏感；`lcmd search` 没有搜索词时显示搜索用法提示。
3. 其他普通名称和参数路径交给知识库动态查询。
4. 不再把 `platform`、`language` 注册为 LCMD 固定子命令；它们是普通知识库查询目标。
5. 知识库即使存在名为 `search` 的文档，也不通过普通动态查询入口展示；`search` 保留为唯一固定搜索入口。

**长参数与短参数映射：**

| 长参数 | 短参数 | 用途 |
|---|---|---|
| `--help` | `-h` | 帮助 |
| `--version` | `-v` | 显示版本 |
| `--config` | `-c` | 查看或修改配置 |
| `--path` | 不提供短参数 | 设置知识库路径 |
| `--platform` | `-p` | 查看或设置平台（小写 p） |
| `--language` | `-l` | 设置语言 |
| `--update` | `-u` | 更新主程序/知识库（更新范围和机制按后续阶段设计） |

所有参数都使用双横杠长参数形式；短参数使用单横杠加一个字母。上述映射为当前已确认方案，不应自行改成其他字母或为 `--path` 增加短参数。

**配置参数组合约束：**

- 只允许 `--config` 与 `--path` 单独组合：`lcmd --config --path="D:\\knowledge"`。
- `--config` 可以单独查看当前配置：`lcmd --config` 或 `lcmd -c`。
- 平台和语言可以分别单独设置，也可以同时设置：`lcmd --config --platform=linux`、`lcmd --config --language=en-US`、`lcmd --config --platform=linux --language=en-US`。
- 短参数等价形式：`lcmd -c -p=linux -l=en-US`。`-P` 不作为别名，旧参数会被拒绝。
- **路径模式与平台/语言模式互斥**：`--path` 不得与 `--platform` 或 `--language` 出现在同一次配置调用中。例如 `lcmd --config --path="D:\\knowledge" --platform=linux` 和路径与语言混用均应拒绝。
- `--config` 不得与 `--version`、`--help`、`--update` 混用；程序级操作之间的冲突应给出明确中文错误提示。
- 不提供 `--show-path`、`--reset-path`、`--path=default` 等额外选项；不提供恢复默认知识库路径的专用功能。
- 参数错误必须用清晰中文说明具体冲突和正确用法，不向普通用户暴露难懂的异常堆栈。

**配置行为：**

- `--config` 不带配置项时显示当前配置，至少包含当前知识库路径、平台和语言；主程序安装位置/程序路径的准确展示定义需结合安装形态确定。
- 路径设置与平台/语言设置是两种互斥配置模式。
- 平台与语言可以一次提交；先验证目标知识库是否同时支持该平台/语言组合，再整体保存。验证失败时不允许只保存其中一个字段。
- 路径变更必须走知识库迁移流程，不是简单修改 TOML 中的 path。
- 最终 `--help` 必须完整说明所有长/短参数、组合限制和示例。

### 8.4 自定义知识库路径与迁移（用户行为已确认；迁移 CLI 已接入）

**路径语义与目标限制：**

- 用户提供的路径就是知识库根目录，不自动追加 `knowledge` 子目录。
- 目标目录必须是独立目录；禁止磁盘根目录（如 `C:\\`、`D:\\`）。
- 不允许目标路径指向系统目录、用户配置目录或 LCMD 主程序安装目录。
- 不允许目标路径与当前知识库相同，也不允许目标路径是当前知识库的父目录或子目录。
- 必须进行规范化/解析后的路径安全检查，避免符号链接或路径穿越绕过目录限制。
- 目标目录不存在时自动创建。
- 目标目录已存在时，必须先明确询问是否覆盖；用户拒绝则取消，不修改原配置和原知识库。用户同意后删除整个目标目录再复制，不做合并。
- 目标路径不是目录、无法访问或无权限时，拒绝迁移并说明原因。
- 目标目录覆盖前必须告知用户其中原有内容将被删除；不能承诺恢复被覆盖的目标目录数据。
- 目标目录读取/写入权限与配置文件写入权限分别检查。

**迁移事务顺序：**

1. 检查当前知识库有效性、源路径和目标路径安全性。
2. 如果目标目录已存在，显示覆盖警告并取得用户明确确认；拒绝则立即取消。
3. 用户确认覆盖后，删除目标目录整体内容；不与原目录合并。
4. 将当前知识库复制到目标根目录，显示总体百分比进度，并提醒用户不要关闭程序或中断迁移。
5. 复制完成后执行文件完整性检查。
6. 完整性检查通过后，更新 `config.toml` 中的知识库路径；平台和语言保持原值。
7. 确认配置原子写入成功后，删除原知识库目录，迁移完成。

**失败保护：**

- 复制失败或完整性检查失败：不切换配置，不删除原知识库。
- 配置写入失败：保留原配置和原知识库，不删除源目录。
- 用户拒绝覆盖：不修改目标目录、源知识库和配置。
- 同盘、跨盘统一采用“复制 → 验证 → 切换配置 → 删除旧目录”的安全流程；不以直接移动替代。
- 完整性检查的具体实现由开发阶段确定，至少需要能验证复制结果完整；可采用相对文件清单及内容校验等实现手段，不要求用户决定内部算法。
- 不保留迁移前的旧知识库副本作为长期备份；一个 LCMD 安装实例只维护一个当前知识库位置。

**中断恢复仍需落实为实现设计：**

- 如果复制阶段中断，原配置和原知识库保持不变；再次选择同一目标路径时按既定规则询问覆盖。
- 如果配置已经成功切换，但删除旧知识库前发生断电，可能暂时留下新旧两份目录。实现时必须设计可恢复的清理记录/启动检查，确认当前配置指向的新知识库有效后，再完成旧目录清理；不能误删当前配置指向的知识库。
- 启动恢复机制的具体记录格式、清理时机和异常提示属于实现细节，需在开发前结合代码确定，但不得改变上述迁移事务原则。

### 8.4.1 迁移核心模块与 CLI 配置入口实现状态

提交 `a516d4c`（`feat: add secure knowledge base migration`）新增以下文件：

- `src/lcmd/core/path_security.py`：独立路径安全检查模块，提供 `validate_knowledge_path()` 和 `validate_migration_target()`；检查解析后路径边界、受保护目录、源/目标重叠、符号链接及 Windows Reparse Point。
- `src/lcmd/core/migration.py`：独立迁移核心模块，提供 `migrate_knowledge()` 和 `recover_migration()`；负责复制、文件 SHA-256 与目录清单校验、原子配置切换、迁移日志和旧目录清理恢复。
- 对应测试：`tests/test_path_security.py`、`tests/test_migration.py`。

当前实现落实的关键行为：

- 目标路径是知识库根目录，不追加子目录；目标已存在时默认要求调用方明确传入覆盖确认。
- 复制阶段通过可选 `progress_callback` 报告已复制字节和总字节；总大小只用于进度，不作为完整性校验条件。
- 完整性检查比较相对路径文件清单、SHA-256 和目录清单；扫描时拒绝符号链接、重解析点和特殊文件。
- 配置使用现有 `save_config()` 原子保存；只有复制和验证成功后才切换路径，平台和语言保持不变。
- 旧目录清理是尽力操作。清理失败时迁移仍成功，发出 `MigrationCleanupWarning` 并保留迁移日志。
- 迁移日志独立保存旧/新路径、源目录身份及原始文件清单；恢复时先确认当前配置指向的新知识库有效，再验证旧目录身份和剩余内容，避免误删当前知识库或被替换的目录。
- 若配置缺失、日志损坏、目录身份不符或源目录出现非预期内容，恢复逻辑拒绝自动删除。

当前 CLI 接入状态（提交 `7024d8d78fee4364a36b0836d2a1187606b92e0f`）：

- `cli/app.py` 已接入 `--config/-c`、`--platform/-p`、`--language/-l` 的配置查看和切换；平台与语言组合先验证最终组合，再只保存一次配置。
- `lcmd -c --path <目录>` 已调用 `migrate_knowledge(config_file, path)`。首次调用不覆盖；遇到 `MigrationConfirmationRequired` 后通过 `typer.confirm()` 询问，用户确认才以 `overwrite=True` 重试，拒绝则取消。
- CLI 捕获 `MigrationError` 并以退出码 1 结束；捕获 `MigrationCleanupWarning` 并显示警告，迁移仍显示成功。
- Rich CLI 已通过 `progress_callback` 显示复制字节百分比；该进度只覆盖文件复制阶段，不代表完整性校验、配置切换和旧目录清理的整体进度。
- `--update/-u` 仍仅为占位提示，不包含更新机制。
- `recover_migration()` 已接入程序启动流程。

阶段一任务 1、任务 2 和任务 3 均已完成。任务 3 将迁移恢复接入启动初始化流程；安装包、更新机制和完整帮助仍属于后续独立工作，不应在没有重新核对路线图和当前代码前提前推进。

### 8.5 Windows 安装包与首次初始化（产品方向已确认；部署架构设计已完成，尚未实现）

已确认的产品行为：

- Windows 用户下载一个安装包（优先单个 EXE），通过图形安装向导完成安装。
- 安装后无需用户预先安装 Python、pip 或开发工具。
- 安装主程序时默认同时部署官方知识库，避免安装后没有可查询内容。
- 安装向导允许用户选择程序安装位置，也允许选择知识库根目录；两者是不同位置。
- 安装初始化必须检查知识库目标位置。目标目录已有内容时，先识别知识库结构和现有数据，再说明覆盖范围与风险；未经明确同意不得覆盖。
- 用户拒绝覆盖时，必须允许选择其他位置或取消安装，不得擅自删除或合并已有目录。
- 安装包部署的知识库根目录遵守第 8.4 节路径语义，不额外套一层 `knowledge`。
- 安装完成后，配置文件记录实际知识库根目录；已有用户配置、平台、语言和自定义知识库路径不得被升级程序静默重置。
- 如果运行时在当前配置路径找不到有效知识库，应提示检查安装/完整性，并指导用户使用 `--config` 查看配置、使用 `--config --path=...` 迁移现有知识库。
- 路径配置是迁移现有知识库，不等于下载或安装知识库；没有可迁移的当前知识库时，不能假装迁移成功。
- 卸载程序默认只移除程序文件、安装器创建的快捷方式和 PATH 项，不删除知识库和用户配置。用户数据清理策略如需增加，必须单独设计并明确征求同意。
- 当前知识库仓库只有少量 integration fixtures，不能作为正式发行知识库；正式安装包必须使用完成内容规范并经过验收的官方知识库版本。

### 8.5.1 Windows 打包与安装器技术路线（设计已确认）

**主程序打包：PyInstaller，采用 onedir 模式。**

- 使用 PyInstaller 将 LCMD 主程序、Python 解释器及运行依赖打包为独立目录。
- 打包产物保留控制台模式，必须支持 stdin/stdout/stderr；不得使用 windowed/noconsole 模式破坏 CLI 交互。
- 先验证 onedir 产物，再由安装器封装；当前不采用 onefile 作为首选内部打包模式。
- onedir 目录中的可执行文件命名为 `lcmd.exe`。依赖文件由 PyInstaller 一并收集，用户无需单独安装 Python。
- 官方知识库作为独立数据目录交付，不与可执行程序混为一个运行时资源目录，便于安装器部署、完整性验证及未来独立更新。
- 参考：<https://pyinstaller.org/en/stable/operating-mode.html>、<https://pyinstaller.org/en/stable/spec-files.html>。

**图形安装器：Inno Setup。**

- 使用 Inno Setup 将 PyInstaller onedir 输出、官方知识库和安装所需元数据封装为单个 Windows EXE 安装包。
- 安装向导负责程序目录选择、知识库目录检查与选择、安装进度、快捷方式、当前用户 PATH 配置和卸载入口。
- 默认采用当前用户安装模式，不主动请求管理员权限；默认程序目录为 `%LOCALAPPDATA%\Programs\LCMD`。用户可选择其他有写入权限的目录。
- 将程序目录加入当前用户 PATH，使新启动的终端可以直接执行 `lcmd`；不得修改系统级 PATH。卸载时只移除安装器添加的 LCMD PATH 项，并保留 PATH 中其他内容。
- 安装器修改环境变量后应通知 Windows 更新环境变量；已打开的终端不会自动获得新 PATH，需重新打开终端。
- 参考：<https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm>、<https://jrsoftware.org/ishelp/topic_admininstallmode.htm>、<https://jrsoftware.org/ishelp/topic_setup_changesenvironment.htm>。
- 正式发布前核对所选 Inno Setup 版本的许可条款及商业使用要求。

### 8.5.2 安装目录与用户数据目录（设计已确认）

| 内容 | 默认位置/规则 | 生命周期 |
|---|---|---|
| LCMD 主程序 | `%LOCALAPPDATA%\Programs\LCMD` | 由安装器安装、升级和卸载 |
| 知识库 | `get_default_knowledge_path()` 返回的位置，即 platformdirs 用户数据目录下的 `knowledge` | 用户数据；默认不随程序卸载删除 |
| 配置文件 | `get_config_file()` 返回的位置，即 platformdirs 用户配置目录下的 `config.toml` | 用户配置；默认不随程序卸载删除 |
| 用户自定义知识库 | 用户选择的知识库根目录 | 用户数据；不由程序升级或卸载擅自删除 |

约束：

- 安装器必须以当前用户身份处理用户数据目录，避免管理员提升安装时把知识库或配置写入另一个管理员账户的用户目录。
- 程序安装目录与知识库目录必须分离；程序升级不得覆盖知识库目录。
- 知识库默认目标必须调用/遵循现有 `get_default_knowledge_path()` 的语义，不在安装器中另行硬编码一套默认路径。
- 用户选择的知识库路径就是知识库根目录，不额外追加 `knowledge`。
- 配置初始化必须遵守现有 `AppConfig` 和 `save_config()` 合同；具体由安装器调用内部初始化入口还是由程序首次启动完成，仍需在实现前结合源码确定。
- 首次安装成功后，配置记录实际知识库路径；升级时保留已有配置，不因安装目录或知识库默认位置变化而静默重置用户路径、平台或语言。

### 8.5.3 已有知识库与用户数据保护（设计已确认）

安装器检查目标路径时，不得仅凭“目录存在”就判断可以覆盖：

1. 目标不存在或为空目录：可以部署随包知识库。
2. 目标包含有效 LCMD 知识库：显示识别结果和版本；默认保留现有知识库，允许用户继续使用现有库、选择其他安装位置，或在明确确认后整体替换。
3. 目标包含非空但无效/不完整的知识库，或包含其他用户文件：明确说明检测结果和将被删除的范围；只有用户再次明确确认整体替换后才可覆盖。
4. 用户拒绝覆盖：不得修改目标目录；提供选择其他目录或取消安装。
5. 不执行目录合并，不把随包知识库静默写入已有目录。

覆盖语义沿用第 8.4 节：明确确认后整体替换目标目录，不承诺恢复被覆盖数据。实现时还必须考虑复制失败、校验失败和安装中断，不能在新知识库部署验证通过前破坏现有数据。

卸载默认保留知识库和配置。修复安装可以恢复程序文件；若知识库缺失且目标为空，可以重新部署；若目标已有内容，仍须执行上述识别与确认流程。

### 8.5.4 知识库完整性与 Manifest 兼容性（设计已确认）

- 当前 `manifest.json` 只允许 `version` 字段，安装阶段不得擅自扩展该格式。
- 安装包需要额外的发行文件清单/校验信息，用于核对随包知识库文件是否完整；该校验信息与知识库 Manifest 分离，不改变现有知识库目录合同。
- 完整性校验至少覆盖相对路径、文件数量和文件内容摘要；具体清单格式、生成时机、验证入口及失败回滚在后续任务中确定。
- `discover_catalog()` 负责现有结构发现，不等同于逐文件发行完整性校验；不得把两者混为一谈。
- 不能仅凭 `manifest.json` 存在或 `discover_catalog()` 成功，就宣称随包知识库所有文件均完整。

### 8.5.5 阶段二任务拆分与边界

1. **任务 1：Windows 打包与安装部署架构设计。** 已完成设计；本次只更新总控文档，尚无打包或安装代码。
2. **任务 2：PyInstaller onedir 打包验证。已完成（提交 `c333bdd`）。** 已建立根目录 `lcmd.spec`，并将 `pyinstaller>=6.22,<7` 加入 dev 可选依赖；Windows 11 下构建和便携目录 help/version、动态查询、搜索均已验证。当前仅完成 PATH 临时隔离测试，尚未在完全无 Python 的干净机器验证；动态查询和搜索使用本机测试知识库，随包知识库留待任务 3。详细证据见第 6.6 节。
3. **任务 3：随包知识库与发行完整性校验。** 选择正式知识库版本，生成独立文件清单并验证部署内容；不得扩展现有 `manifest.json` schema。
4. **任务 4：Inno Setup 安装器。** 实现单 EXE 安装包、用户级程序目录、用户 PATH、知识库目录选择和安装/卸载基础流程。
5. **任务 5：首次初始化与已有数据处理。** 按 8.5.2–8.5.4 实现配置初始化、目标识别、明确覆盖确认、取消和失败保护。
6. **任务 6：安装、升级、修复、卸载验收。** 验证首次安装、已有有效/无效目录、用户自定义路径、已有配置、升级、修复、卸载及中断恢复。

当前阶段二仍未实现任何打包或安装功能。当前知识库只有测试样例，任务 2 可以先用专门的测试知识库验证打包链路，但不得将该产物标记为正式发行版。

### 8.6 更新机制与阶段顺序（方向已确认，细节待设计）

主程序与知识库是独立仓库、独立版本。未来提供 `--update` / `-u` 作为程序级更新入口。更新检查、下载来源、版本兼容策略、用户确认、失败回滚和主程序/知识库更新顺序尚未完成设计，不得提前假定为已实现。

当前确定的开发推进顺序：

1. **阶段一：自定义知识库路径与迁移。** 已完成。路径安全检查、迁移核心模块、`--path` 迁移调用、覆盖确认、错误/警告处理、复制字节百分比进度显示及启动时 `recover_migration()` 均已实现。
2. **阶段二：Windows 安装包与初始化。** 安装主程序并默认携带官方知识库，处理已有目录、覆盖确认、自定义安装位置和首次配置。
3. **阶段三：更新机制。** 设计并实现主程序/知识库独立更新能力，提供 `--update` / `-u`。
4. **阶段四：完整 CLI 帮助。** 将最终参数、短参数、组合约束、错误示例和使用示例整理进 `--help`。

阶段顺序是已确认的产品计划，不代表阶段已经开始或完成。每阶段仍需先核对源码、制定改动范围和验收标准，再进入实现。

### 8.7 设计决策维护规则

- 本节标记为“已确认”的业务规则，后续不得在没有用户提出变更的情况下重复询问或擅自改写。
- 标记为“待落实/待设计”的内容只讨论尚未决定的实现细节，不重新打开已确认的产品行为。
- 代码实现与本节冲突时，先核对代码和测试，再按用户已确认设计修正实现；不能默默以旧代码行为覆盖新设计。
- 功能实现和验收后，更新本节状态及相关源码调用链、测试证据；计划不能写成现成功能。

---

## 9. 下一阶段推进规则

- 以第 8 节已确认设计为产品行为基线，不重复询问已确认事项。
- 每次只推进一个关键实现问题；先核对当前源码、Git 状态和相关测试，再明确本次改动范围。
- 先完成阶段一，再进入阶段二、三、四；不跨阶段提前实现。
- 对仍标记为待设计的实现细节，一次聚焦一个关键问题，并说明它对已确认行为的影响。
- 修改代码前检查 Git 状态和 diff，不覆盖用户未提交修改。
- 不擅自提交代码；代码实现与总控文档维护分开。
- 阶段验收后更新本总控文档，明确区分已确认、已实现、已测试和已人工验收。

## 10. 固定协作与验收规则

- 一次聚焦一个明确任务；必要时一次只问一个关键问题。
- 不擅自扩大范围，不重复已经确认的设计，不用大量无关诊断代替目标排查。
- 以实际源码、用户终端输出和远程仓库状态为证据；不假装访问用户本地文件。
- 计划、建议、自动化测试结果、人工 CLI 实测结果分别记录，不混为一谈。
- 功能代码变更至少执行相关定向测试、全量 pytest、Ruff lint 和 Ruff format；涉及 CLI、配置或路径时增加真实运行验证。
- 代码提交与总控文档提交分开。
- 总控文档由助手维护 GitHub 远程 `LCMD-DEV.md`；远程更新完成后，再由用户在本地执行 fast-forward pull 同步。
- 每次文档更新后核对提交结果；用户本地环境状态仍以用户提供的命令输出为准。

---

## 11. 关键实现事实速查

| 项目 | 当前事实 |
|---|---|
| 主程序版本 | 0.1.0 |
| 知识库版本 | 0.1.0（本轮 Windows CLI 输出） |
| 知识库 Major | 当前代码只接受 0 |
| Python 最低版本 | 3.11 |
| 默认平台 | windows |
| 默认语言 | zh-CN |
| 配置文件 | platformdirs 用户配置目录下 config.toml |
| 默认知识库路径 | platformdirs 用户数据目录下 knowledge |
| 配置字段 | [knowledge] path、platform、language，三者均为必需字段 |
| 自定义路径 | `-c --path <目录>` 已接入迁移 API；覆盖确认、错误、清理警告、复制字节百分比进度及启动恢复均已实现 |
| 搜索分页 | 每页 5 条；交互终端自动分页 |
| 在线更新 | 已确认未来提供 --update/-u；更新机制未设计/实现 |
| 安装包 | 已确认 Windows 安装默认携带官方知识库；安装包未实现 |
| 主程序/知识库远程 Release 更新 | 未实现 |
| 命令执行 | 不执行 |
| 系统命令安装检测 | 不检测 |


## 12. 核心数据模型与对象关系

本节依据当前 `src/lcmd/knowledge/models.py` 和 `src/lcmd/cli/app.py`。

所有知识模型均为 `@dataclass(frozen=True, slots=True)`：实例创建后字段不可重新赋值，并使用 slots。不要把它们当作可随意修改的普通字典。

### 12.1 运行状态

`AppState`（定义于 `cli/app.py`）：

| 字段 | 类型 | 含义 |
|---|---|---|
| `config` | `AppConfig` | 当前用户配置 |
| `catalog` | `KnowledgeCatalog \| None` | 已发现的知识库目录索引；初始化失败时可为 None |
| `knowledge` | `KnowledgeBase \| None` | 当前平台/语言加载出的文档集合；不可用时为 None |

`AppState` 是 CLI 初始化后放入 Typer 根 Context 的运行状态。search、platform、language 和动态查询命令从根 Context 读取它。切换平台或语言时返回新的 AppState，不原地修改旧状态。

### 12.2 知识库模型

| 模型 | 字段 | 说明 |
|---|---|---|
| `PlatformInfo` | `name: str`、`languages: tuple[str, ...]` | 一个平台及其实际发现的语言目录 |
| `ToolInfo` | `name: str`、`languages: tuple[str, ...]` | 一个第三方工具及其实际发现的语言目录 |
| `KnowledgeCatalog` | `root: Path`、`version: str`、`platforms: tuple[PlatformInfo, ...]`、`tools: tuple[ToolInfo, ...]` | Manifest 版本和动态目录发现结果 |
| `KnowledgeDocument` | `id`、`category`、`platform`、`tool`、`language`、`summary`、`body` | 单篇已解析、已校验文档 |
| `KnowledgeBase` | `platform: str`、`language: str`、`documents: tuple[KnowledgeDocument, ...]` | 当前平台/语言下可查询的全部有效文档 |
| `QueryResult` | `documents: tuple[KnowledgeDocument, ...]`、`children: tuple[str, ...]` | 精确查询结果；文档与下级命令可同时存在 |
| `SearchResult` | `document: KnowledgeDocument`、`score: float` | 一篇文档及其搜索得分 |

`KnowledgeDocument` 的 `category` 只能是 `"platforms"` 或 `"tools"`。其 `__post_init__()` 要求 platform 与 tool 必须且只能指定一个；category 也必须与指定的归属字段相符。该模型校验的是文档归属关系，不校验 Markdown 内容质量。

`id` 是知识文档相对于知识库命令内容的 POSIX 风格路径标识。查询、搜索和渲染模块会从该 ID 解析命令名、工具名和子命令层级。新增路径规则时必须同步检查这几个消费者，不能只改 Loader。

### 12.3 Parser 中间模型

`ParsedDocument` 定义在 `knowledge/parser.py`，承载 Front Matter 元数据和 Markdown 正文，供 Validator 检查。它不是最终知识文档；Loader 在解析、校验通过后才构造 `KnowledgeDocument`。

## 13. 模块函数、输入输出与错误边界

本节记录当前源码中的主要函数。新增、重命名或改变函数契约时，应同步更新本节。

### 13.1 CLI：`src/lcmd/cli/app.py`

| 函数/类型 | 当前职责与契约 |
|---|---|
| `DynamicTyperGroup.resolve_command(ctx, args)` | Typer 命令解析钩子。已注册命令或以 `-` 开头的首参数交给 Typer；其他未知首参数被记录为动态知识查询参数，并创建占位命令对象。 |
| `initialize_state(config_file=None, default_knowledge_path=None)` | 读取配置或建立默认配置；调用 `discover_catalog()` 和 `load_knowledge()`；返回 AppState。知识库加载的 `KnowledgeLoadError/OSError` 转为 catalog/knowledge 均为 None 的不可用状态；配置读取错误不在此处吞掉。 |
| `switch_platform(state, platform, config_file)` | 要求已有 catalog；将平台名转小写；先加载新平台/当前语言，再保存配置；成功后返回新 AppState。 |
| `switch_language(state, language, config_file)` | 要求已有 catalog；先加载当前平台/新语言，再保存配置；成功后返回新 AppState。 |
| `_show_platforms()` / `_show_languages()` | 展示当前选择和 catalog 实际发现的可用值；catalog 不可用或平台不存在时显示提示。 |
| `_show_version()` | 显示程序版本；只读取配置和发现 Manifest/catalog 版本，不加载 Markdown 文档，也不写配置。 |
| `create_app()` | 注册 Typer 应用、根 callback 和 search/platform/language 命令；动态查询在根 callback 中处理；配置模式下的 `--path` 调用迁移 API 并处理覆盖确认、迁移错误和清理警告。 |

根 callback 的执行顺序是：若指定 `--version`，先走版本专用路径并退出；否则初始化 AppState 并放入根 Context。配置模式下若指定 `--path`，调用 `migrate_knowledge()` 并传入进度回调；Rich 显示复制阶段的字节百分比进度。目标已存在时捕获 `MigrationConfirmationRequired` 并请求用户确认，确认后以 `overwrite=True` 重试且继续传入进度回调，取消则退出；迁移错误显示原因并以退出码 1 退出，清理警告会显示但不阻止成功结果。若解析器记录了动态参数，则要求 knowledge 可用，调用 `query_document()` 和 `render_query_result()` 后退出；否则由 Typer 调用注册的 search/platform/language 命令。没有子命令时显示帮助。

search 命令把多个 keyword 参数用空格连接成一个字符串，调用 `search_knowledge()`，再调用 `render_search_results()`。platform/language 无参数时显示可用值；有参数时调用对应 switch 函数。切换失败时 CLI 显示失败提示并以退出码 1 退出。

### 13.2 配置与路径：`core/config.py`、`core/paths.py`

| 函数/类型 | 当前职责与契约 |
|---|---|
| `ConfigError` | 配置读取、解析、结构、字段或保存失败的 ValueError 子类 |
| `AppConfig` | 不可变配置对象，字段为 knowledge_path、platform、language |
| `_validate_config(config)` | 检查对象类型、路径类型/非空、platform 和 language 为非空字符串 |
| `load_config(path)` | UTF-8（允许 BOM）读取 TOML；要求顶层只有 knowledge，且该表恰好有 path/platform/language；将 path 展开用户目录后转 Path；错误转 ConfigError |
| `save_config(config, path)` | 验证配置；创建父目录；写同目录临时文件、flush/fsync 后用 os.replace 原子替换；失败转 ConfigError，并尽力清理临时文件 |
| `get_config_dir()` | 通过 platformdirs 获取用户配置目录 |
| `get_config_file()` | 配置目录下的 config.toml |
| `get_data_dir()` | 通过 platformdirs 获取用户数据目录 |
| `get_default_knowledge_path()` | 返回数据目录下 knowledge；只计算路径，不创建知识库目录 |

配置文件严格要求三个字段，不能把“AppConfig 有默认值”误解为“现有 TOML 可以省略字段”。配置模块只检查路径字段是否为有效 Path 值，不检查路径是否存在、Manifest 是否兼容或 Markdown 是否可加载；这些属于 Loader。

### 13.3 文档解析与校验：`parser.py`、`validator.py`

| 函数/类型 | 当前职责与契约 |
|---|---|
| `parse_document(content)` | 解析开头 TOML Front Matter，返回 ParsedDocument；负责分离 metadata/body，不负责 summary 业务规则和正文分隔线规则 |
| `DocumentParseError` | Front Matter 缺失、格式错误或重复键等解析错误 |
| `validate_document(document)` | 校验 metadata 必须是只含非空字符串 summary 的字典；正文首个非空行必须是独立的 `---`，其后正文必须非空 |
| `DocumentValidationError` | 文档结构不符合当前必要合同 |

Parser 和 Validator 有意分工：Parser 不因 summary 缺失或正文分隔线不正确而越权判断；Validator 不负责 TOML 文本解析。不要把推荐章节、参数数量、语言表达或示例质量加入 Validator。

### 13.4 Loader：`knowledge/loader.py`

| 函数/类型 | 当前职责与契约 |
|---|---|
| `KnowledgeLoadError` | 知识库整体结构、兼容性或加载条件错误 |
| `_is_within_root(path, root)` | 检查解析后的路径是否位于根目录内 |
| `_is_reserved_name(name)` | 检查 Windows 保留设备名 |
| `_validate_slug(name, description)` | 检查小写 ASCII slug 及保留名 |
| `_validate_language(name)` | 检查语言目录标签格式 |
| `_check_duplicate_names(paths, description)` | 检查同级目录大小写折叠后的名称冲突 |
| `_list_directories(path, description, root)` | 检查目录可访问性、符号链接、越界路径和同级名称冲突，再排序返回目录 |
| `_read_manifest(root)` | 读取 JSON，要求只有 version 字段、版本符合当前三段式格式且 Major 为 0 |
| `discover_catalog(root)` | 验证知识库根目录、Manifest、commands/platforms，动态发现平台/语言/工具/语言，返回 KnowledgeCatalog |
| `_load_markdown_directory(...)` | 递归读取一个语言目录中的 Markdown，解析、校验并构造 KnowledgeDocument；文档级问题通常隔离跳过 |
| `load_knowledge(catalog, platform, language)` | 验证平台和语言可用性，加载当前平台命令及当前语言可用的工具文档，返回 KnowledgeBase |

路径安全策略需要按阶段准确理解：

- 目录发现阶段的目录扫描会拒绝扫描目录中的符号链接、越界路径和同级目录名称冲突；这些问题可能使 catalog 发现失败。
- Markdown 加载阶段对单个符号链接文档/目录会跳过；对不可读取或解析、校验失败的单篇文档进行隔离。
- 同一目录中，`foo.md` 与 `foo/` 是允许的组合；同类型的 Markdown 文件或目录若大小写折叠后冲突，则冲突项会被跳过。
- 当前平台/语言必须有至少一篇有效平台命令文档，否则 load_knowledge 失败。
- 工具没有当前语言目录时跳过该工具；工具文档无效不会自动使平台命令整体失效。
- tools 目录可以不存在；commands/platforms 是必需结构。

新增知识库类别或路径层级时，必须同时更新 catalog discovery、document ID 生成、query/search/render 对 ID 的解释，以及测试。不能只在目录中新增一层就假设程序自动理解其语义。

### 13.5 精确查询：`knowledge/query.py`

| 函数 | 当前职责 |
|---|---|
| `_get_tool_documents(knowledge, tool)` | 从当前 KnowledgeBase 中筛选指定工具文档，并提取其相对路径段 |
| `_find_tool_entry(tool_documents, tool)` | 查找根语言目录下的同名入口文件 `<tool>.md` |
| `_find_document(tool_documents, target)` | 将目标路径最后一段映射为同名 .md 文件并查找 |
| `_find_children(tool_documents, target, tool)` | 从文档 ID 推导指定位置的直接子命令 |
| `_query_tool(knowledge, tool, subcommands)` | 实现工具入口、无入口单篇/多篇和子命令查询 |
| `query_document(knowledge, arguments)` | 统一查询入口；单参数时同时匹配平台命令和同名工具，再组合 documents/children |

`query_document()` 对输入参数执行小写规范化。平台命令只在参数长度为 1 时匹配；工具名称和子命令路径按工具文档 ID 的路径段匹配。最终文档按 ID 排序，子命令去重并排序。

### 13.6 搜索：`knowledge/search.py`

| 函数 | 当前职责 |
|---|---|
| `_extract_usage(body)` | 从 Markdown 中提取标题为“用途”的章节，遇到下一个标题结束 |
| `_query_units(keyword)` | 将查询拆为中文片段和英文 token，并去重保序 |
| `_contains_unit(text, unit)` | 中文使用包含匹配；英文使用不区分大小写的单词边界匹配 |
| `_contains_phrase(text, keyword)` | 完整关键词匹配；含中文时使用包含匹配，否则使用英文边界匹配 |
| `_document_names(document)` | 生成参与搜索的命令名、工具名和子命令路径 |
| `_score_field(text, units, weight)` | 按命中单元覆盖率计算字段得分 |
| `_score_document(document, units, keyword, full)` | 汇总名称、summary、用途及可选全文得分，并加完整短语和多关键词覆盖奖励 |
| `search_knowledge(knowledge, keyword, full=False)` | 搜索当前 KnowledgeBase，丢弃零分文档，按得分降序和 ID 升序稳定排序 |

多关键词采用 OR 命中；覆盖奖励使命中更多查询片段的文档更有优势。搜索不扫描磁盘、不联网，也不搜索未加载的平台或语言。

### 13.7 路径安全与知识库迁移：`core/path_security.py`、`core/migration.py`

| 函数/类型 | 当前职责与契约 |
|---|---|
| `PathSecurityError` | 知识库路径安全校验失败 |
| `validate_knowledge_path(path, protected_paths=None)` | 校验知识库根目录、解析后路径边界及受保护路径，并通过 `discover_catalog()` 验证知识库结构 |
| `validate_migration_target(target_path, source_path, protected_paths=None)` | 校验迁移目标与源目录的安全边界及重叠关系；不负责执行迁移 |
| `MigrationError` | 迁移或恢复过程失败 |
| `MigrationConfirmationRequired` | 目标目录存在且调用方尚未明确确认覆盖 |
| `MigrationCleanupWarning` | 新知识库已切换成功，但旧目录未能完全清理 |
| `migrate_knowledge(config_path, target_path, overwrite=False, progress_callback=None, protected_paths=None)` | 执行复制、完整性验证、配置切换和旧目录尽力清理；返回更新后的 `AppConfig` |
| `recover_migration(config_path, protected_paths=None)` | 根据独立迁移日志验证当前新库、旧目录身份及剩余内容，再尝试完成旧目录清理；无日志时返回 False |

迁移日志文件名为 `.lcmd-migration.json`，位于配置文件所在目录。日志包含 source、target、state、source_identity 和 source_manifest。源目录身份用于拒绝清理被替换的目录；源清单保留文件 SHA-256 与目录相对路径，以支持部分删除后的安全恢复。旧目录清理失败时保留日志。

`migrate_knowledge()` 已由 CLI 的 `-c --path <目录>` 调用；覆盖确认、迁移异常、清理警告和 Rich 复制字节百分比进度均已接入。进度回调只覆盖文件复制阶段。`recover_migration()` 已在 `initialize_state()` 中接入，启动时先恢复迁移，再读取配置和加载知识库。

### 13.8 终端渲染：`output/renderer.py`

| 函数 | 当前职责 |
|---|---|
| `_get_document_name(document)` | 从 ID 生成显示名称 |
| `_get_document_source(document)` | 生成平台命令/第三方工具来源说明 |
| `_get_console(console)` | 使用传入 Console 或创建默认 Console |
| `render_document(document, console)` | 用 Rich Markdown 和 Panel 显示单篇文档 |
| `render_query_result(result, console)` | 显示零结果提示、一个或多个文档，以及可选的子命令表 |
| `_render_search_page(results, start, end, console)` | 显示指定切片的搜索表格 |
| `render_search_results(results, console, page_size=5)` | 处理空结果、分页阈值、非交互一次性输出和交互翻页 |

分页输入只接受空输入（下一页）或 q（退出）；其他输入会重新提示。page_size 小于 1 时抛出 ValueError。分页属于 Renderer，不属于 Search 算法。

## 14. 端到端执行流程

### 14.1 启动和初始化

```text
console script / python -m lcmd
  -> main.main()
  -> create_app()
  -> Typer 根 callback
  -> initialize_state()
       -> recover_migration(config_file)
       -> load_config() 或创建默认 AppConfig
       -> discover_catalog(knowledge_path)
       -> load_knowledge(catalog, platform, language)
       -> 首次成功时 save_config()
  -> AppState 放入 ctx.obj
  -> 根据程序级参数分发
       -> -c --path <目录>
            -> migrate_knowledge(config_file, target_path, progress_callback=...)
            -> Rich 显示复制字节百分比进度
            -> 若目标存在：请求确认；确认后 overwrite=True 并再次传入进度回调
            -> 显示迁移成功、迁移失败或旧目录清理警告
       -> 其他配置、search、动态知识查询
```

当前启动流程会先调用 `recover_migration(config_file)`，再读取配置和发现/加载知识库。若恢复失败并抛出 `MigrationError`，根 callback 显示“知识库迁移恢复失败”及具体原因，以退出码 1 结束；不会继续读取配置或扫描知识库。调用时保留 `protected_paths=None` 默认行为，使核心路径安全模块继续应用默认受保护目录规则。迁移 CLI 已向核心函数传入 `progress_callback`，并显示复制阶段的字节百分比进度。

注意两个不同的失败路径：

- 配置文件存在但无法读取/解析/校验：ConfigError 向 CLI 传播，根 callback 显示初始化失败并以退出码 1 退出。
- 配置有效，但知识库发现或加载遇到 KnowledgeLoadError/OSError：initialize_state 返回 catalog=None、knowledge=None 的 AppState；之后查询或搜索提示知识库不可用，platform/language 查询仍可显示当前配置，但无法列出可用值。

首次启动只有在知识库成功加载后才保存默认配置。首次知识库加载失败不会写入初始配置。

### 14.2 精确命令查询

```text
lcmd docker compose up
  -> DynamicTyperGroup 将未知命令参数保存到 ctx.meta
  -> 根 callback 初始化 AppState
  -> 检查 state.knowledge
  -> query_document(knowledge, ("docker", "compose", "up"))
  -> _query_tool()
  -> _find_document() / _find_children()
  -> QueryResult
  -> render_query_result()
  -> Rich 文档 Panel 和/或子命令表
```

`lcmd ls` 与 `lcmd docker compose up` 共用动态入口，但 query 内部根据参数长度和文档类别分别处理平台命令及工具子命令。

### 14.3 搜索

```text
lcmd search "复制文件" --full
  -> Typer search_command
  -> 合并多个 keyword 参数
  -> search_knowledge(knowledge, keyword, full=True)
  -> 生成 query units
  -> 对每篇 KnowledgeDocument 计算相关度
  -> 排序得到 SearchResult tuple
  -> render_search_results()
  -> Rich 表格 / 交互分页
```

搜索计算与输出分页必须保持分层。增加新的搜索字段或改变权重修改 search.py 并更新搜索测试；改变每页数量、提示或输入行为修改 renderer.py 并更新渲染测试。

### 14.4 平台/语言切换

```text
lcmd platform linux
  -> 读取根 AppState
  -> switch_platform()
       -> replace(config, platform=输入值.lower())
       -> load_knowledge(现有 catalog, 新平台, 当前语言)
       -> save_config(新配置)
       -> 返回新 AppState
  -> CLI 显示切换成功
```

language 切换流程相同，只替换 language 字段。两种切换均先加载成功再保存配置；加载失败不会保存。保存失败由 ConfigError 传播，CLI 显示切换失败。知识库路径保持不变。

### 14.5 版本显示

`lcmd --version` 走专用分支：读取现有配置或使用默认知识库路径，调用 `discover_catalog()` 读取知识库版本；不调用 `load_knowledge()`，不解析 Markdown，不保存初始配置。因此版本显示可报告 Manifest 版本，但不等同于完整知识库可用性检查。

## 15. 测试地图与证据边界

测试文件与功能对应关系：

| 测试文件 | 主要覆盖范围 | 测试数量（当前源码） |
|---|---|---:|
| `tests/test_cli.py` | 帮助、版本、动态查询、search/platform/language、初始化/切换，以及迁移调用、覆盖确认、取消、异常、清理警告和进度回调 | 52（本轮 pytest 收集） |
| `tests/test_config.py` | 默认值、TOML 读写、字段校验、原子保存失败保护 | 17 |
| `tests/test_loader.py` | Manifest、目录发现、路径命名、平台/语言选择、文档隔离、符号链接和冲突 | 26 |
| `tests/test_models.py` | 数据模型字段、归属约束、不可变和 slots | 12 |
| `tests/test_query.py` | 平台命令、工具入口、子命令、多级路径、同名匹配和子命令列表 | 15 |
| `tests/test_search.py` | 中文/英文拆分、匹配边界、字段范围、全文、OR、评分优先级和稳定排序 | 16 |
| `tests/test_renderer.py` | 文档/查询/搜索展示、空结果、终端分页、退出、无效输入和 page_size | 16 |
| `tests/test_parser.py` | Front Matter 边界、TOML 解析错误、正文保留和职责边界 | 12 |
| `tests/test_validator.py` | summary、正文分隔线、空正文、CRLF 和非修改性 | 19 |
| `tests/test_paths.py` | platformdirs 路径、Path 类型、默认路径不创建目录 | 6 |

表中其他测试数量为此前的源码函数统计，不代表当前 pytest 收集总数。Windows 本轮 `tests/test_cli.py` 收集并通过 51 项，全量 pytest 收集并通过 251 项。**实际测试总数以每次重新运行 pytest 的结果为准**，不要把测试函数数量等同于 pytest 收集数量。

测试证据分层：

1. 源码实现：证明当前代码路径和分支存在。
2. 自动化测试：证明测试用例覆盖的输入和断言行为。
3. 用户人工 CLI 验收：证明用户在指定 Windows 环境中实际观察到的行为。
4. 历史 Linux 运行记录：证明当时该提交在 Linux VM 中通过，不代表本次文档提交重新运行过测试。

后续功能开发必须根据改动模块选择定向测试，并执行全量 pytest、Ruff lint、Ruff format。涉及终端交互、配置目录或路径语义时，还需在目标操作系统做真实 CLI 验收。

### 6.3 Windows 11 迁移核心模块自动化测试（提交 `a516d4c`）

用户在 Windows 11、Python 3.14.10 环境中实际执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_migration.py -v
```

结果：18 passed。随后执行项目级检查，结果为 pytest 228 passed、Ruff lint 通过、Ruff format 32 files already formatted。

本轮新增 4 个文件：`migration.py`、`path_security.py`、`test_migration.py`、`test_path_security.py`。迁移定向测试覆盖覆盖确认、复制/完整性/配置保存失败保护、旧目录清理失败、日志恢复、目录身份替换检测、部分删除恢复、非预期文件拒绝及配置缺失提示等行为。

### 6.4 Windows 11 CLI 迁移集成自动化检查（提交 `7024d8d78fee4364a36b0836d2a1187606b92e0f`）

用户在 Windows 11、Python 3.14.10 环境中实际执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
git diff --check
```

结果：CLI 定向测试 52 passed；全量测试 252 passed；Ruff lint 通过；Ruff format 为 32 files already formatted；`git diff --check` 通过。

CLI 测试通过 Mock 验证迁移 API 调用、覆盖确认、取消、迁移错误、清理警告及进度回调传递和执行。迁移核心的文件复制、SHA-256 完整性检查、配置切换和恢复边界由核心模块测试覆盖。本轮没有进行真实磁盘路径的人工迁移 CLI 验收。Rich 进度条显示复制阶段的字节百分比，不代表完整迁移流程。

### 6.5 Windows 11 启动迁移恢复 CLI 集成检查（提交 `1f28b23`）

用户在 Windows 11、Python 3.14.10 环境中实际执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cli.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
git diff --check
```

结果：CLI 定向测试 55 passed；全量测试 255 passed；Ruff lint 通过；Ruff format 为 32 files already formatted；`git diff --check` 通过。Git 输出的 LF/CRLF 提示属于换行符转换警告。

本轮在 `src/lcmd/cli/app.py` 中导入并接入 `recover_migration()`。恢复调用位于 `initialize_state()` 的配置读取之前，因此即使配置文件不存在，也不会先创建默认配置绕过恢复逻辑。调用未显式传入 `protected_paths`，保留路径安全模块的默认受保护目录规则。

恢复抛出 `MigrationError` 时，初始化立即中止；根 CLI 输出“知识库迁移恢复失败”及具体错误，并以退出码 1 退出。新增 CLI 测试验证恢复先于配置读取和知识库加载、恢复失败阻断初始化，以及根 CLI 的错误输出和退出码。

本轮自动化测试使用 Mock 验证 CLI 接入和异常路径；迁移核心的日志解析、目录身份校验、清理和恢复边界由既有迁移核心测试覆盖。本轮未进行真实磁盘迁移中断后的人工故障注入验收。

### 6.6 Windows 11 PyInstaller onedir 打包验证（提交 `c333bdd`）

用户在 Windows 11 build 26300、Python 3.14.10 x64 环境中，使用项目虚拟环境和 PyInstaller 6.22.3 完成 onedir 构建验证。PyInstaller 作为开发/构建依赖加入 `pyproject.toml`，版本约束为 `pyinstaller>=6.22,<7`；不属于 LCMD 运行时依赖。

正式打包配置为仓库根目录的 `lcmd.spec`，已纳入版本控制。配置要点：

- 入口为 `src/lcmd/__main__.py`，不是只定义 `main()` 的 `src/lcmd/main.py`。
- 使用 PyInstaller `COLLECT` 生成 onedir 目录。
- `console=True`，保留 CLI 所需的控制台及标准输入/输出/错误流。
- 可执行文件名为 `lcmd.exe`。
- 构建命令：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm lcmd.spec
```

构建成功，生成 `dist\lcmd\lcmd.exe`。构建目录共 20 个文件，约 22.97 MB；Python 运行时及所需 VC Runtime 文件已随目录收集。将整个 `dist\lcmd` 复制到独立目录 `D:\LCMD-Portable-Test` 后，完成以下人工验证：

| 验证项 | 实际结果 |
|---|---|
| 便携目录中的 `lcmd.exe --version` | 成功，退出码 0 |
| 便携目录中的 `lcmd.exe --help` | 成功，退出码 0 |
| 从当前 PowerShell PATH 临时排除项目 `.venv\Scripts`、系统 Python 3.14 目录及其 Scripts 目录后启动 | 版本和帮助仍成功 |
| 动态命令查询 `lcmd ls` | 成功，显示完整中文命令文档 |
| 搜索 `lcmd search ls` | 成功，返回 1 条中文搜索结果 |

上述动态查询和搜索读取的是本机现有测试知识库；当前 onedir 产物尚未包含正式随包知识库，因此这两项证明的是打包程序可调用查询/搜索流程，不证明知识库已随包部署。当前知识库仓库只有 integration fixtures，不能作为正式发行内容。

**环境限制：** PATH 隔离测试只是临时排除了指定 Python 路径，并非在完全没有 Python 安装的干净 Windows 机器上测试；不能据此宣称已完成无 Python 干净机器验收。当前也尚未进行 Inno Setup 安装器验收。

提交前质量检查结果：

- 全量 pytest：255 项收集，251 passed、4 skipped、0 failed。4 项跳过均因当前 Windows 环境不支持创建文件或目录符号链接。
- Ruff lint：`All checks passed!`
- Ruff format：`32 files already formatted`
- `git diff --check` 和暂存区 `git diff --cached --check`：无空白错误；Git 的 LF/CRLF 转换提示不是检查失败。
- 提交：`c333bdde94343d8991a3b30bf21c6cdaed145758`（`build: add PyInstaller onedir configuration`），已推送到 `origin/main`。

## 16. 新功能开发前的代码定位规则

收到新功能需求后，先在总控文档中定位业务流程，再按以下顺序核对代码：

1. 确认用户场景和产品行为，不把界面表现直接等同于内部实现。
2. 查找现有数据模型是否已有可复用字段或对象。
3. 沿端到端流程找到 CLI 入口、业务函数、数据模型和 Renderer。
4. 区分已有能力、缺失入口、缺失业务逻辑和缺失测试。
5. 明确本次需要修改的文件及其职责；优先复用现有函数，不复制 Loader、Parser 或配置校验规则。
6. 明确兼容性约束和失败行为，尤其是配置原子保存、切换先加载后保存、文档级错误隔离、语言不回退和搜索/渲染分层。
7. 先补充或调整测试，再实现功能；验收后更新本总控文档中的实现状态、调用链、测试证据和版本基线。

总控文档是开发入口，不替代代码审查。每次任务开始仍须核对目标文件当前内容、Git 状态和远程基线；但对于本文已准确记录且代码未变化的业务逻辑，不要求用户重复解释。若代码与本文冲突，以当前实际代码和测试为准，并在任务结束时修正文档。

## 17. 核心模块修改影响速查

| 需求类型 | 首要模块 | 通常需要同步检查 |
|---|---|---|
| 新增 CLI 命令/全局选项 | `cli/app.py` | 动态命令分发、帮助、CLI 测试 |
| 修改配置字段/格式 | `core/config.py` | `AppConfig`、初始化、切换、旧配置兼容、配置测试 |
| 修改默认目录 | `core/paths.py` | platformdirs 行为、初始化、路径测试 |
| 新增知识库目录类别/层级 | `knowledge/loader.py` | models、document ID、query、search、renderer、loader 测试 |
| 修改 Markdown 格式 | `knowledge/parser.py` / `validator.py` | Loader 错误隔离、知识库文档合同、parser/validator 测试 |
| 修改平台命令或工具导航 | `knowledge/query.py` | QueryResult、ID 路径约定、Renderer、query 测试 |
| 修改搜索匹配/权重 | `knowledge/search.py` | 中文/英文匹配、排序稳定性、search 测试 |
| 修改表格、Panel、分页交互 | `output/renderer.py` | Console/TTY 行为、renderer 测试 |
| 修改启动/初始化/切换流程 | `cli/app.py` | ConfigError、KnowledgeLoadError、持久化时序、CLI 测试 |

本表是定位入口，不意味着每项需求只修改表中一个文件。任何跨层需求都应沿调用链检查完整影响范围。