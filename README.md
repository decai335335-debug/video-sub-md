# video-sub-md — 一键批量下载视频字幕并 AI 深度分析

从 Bilibili / YouTube 批量下载视频字幕为 Markdown，支持 Ctrl+点击在 Obsidian 中直接打开，并可调用 DeepSeek V4 自动生成四层深度内容分析 + 英中双语字幕翻译。

---

## 1. 一句话定位

**一键批量下载 Bilibili + YouTube 视频字幕为 Markdown，AI 自动生成深度分析笔记和双语字幕翻译。** 做视频知识管理时，不再需要手动复制粘贴字幕，也不再需要逐句整理笔记。

---

## 2. 解决什么痛点

### 以前是这样的：
- 想保存视频字幕，需要手动复制粘贴，费时费力
- 多个视频的字幕要逐个处理，无法批量操作
- YouTube 和 B站字幕格式不统一，汇总困难
- 看完视频记不住重点，需要手动整理笔记
- 英文字幕视频需要逐句翻译，没有趁手工具
- 下载完一批视频后，想继续下载需要重新运行程序
- 翻译后的字幕文件丢失了原始的频道/链接/时长等元数据
- 先做了 AI 深度分析再翻译，分析内容会"吃掉"译文导致错位

### 现在是这样的：
- 一键批量下载，自动识别平台，输出统一 Markdown 格式
- 支持循环下载模式，输入 `q` 退出，其余时间持续运行
- 下载完成后可选择调用 DeepSeek V4 生成四层深度分析
- 英文字幕可一键生成英中双语对照（原文 + `> 译文` 格式）
- **分析内容和双语字幕可以共存**——先分析后翻译，互不影响
- **标题、频道、链接等元数据始终保留**，翻译不会丢失 frontmatter
- 结果文件支持 Obsidian 超链接，一键直达

### 适合谁用：
- **知识创作者** —— 快速提取视频核心内容，生成笔记素材，AI 自动整理成结构化分析
- **英语学习者** —— 批量下载英文字幕，一键生成双语对照，边看边学
- **研究人员** —— 批量采集视频内容用于分析和对比，AI 生成批判性重构视角
- **Obsidian 用户** —— 统一管理视频笔记，支持双向链接和知识图谱

---

## 3. 核心功能

| 功能 | 解决什么问题 |
|------|-------------|
| **混合链接输入** | 同时粘贴 B站和 YouTube 链接，自动识别平台分别处理，不用手动分类 |
| **循环下载模式** | 下载完成后不退出，继续等待新链接输入，按 `q` 才退出，避免频繁重启程序 |
| **批量并发下载** | 一次性处理多个视频，充分利用带宽，大幅提升效率 |
| **智能语言选择** | 自动按优先级选择字幕语言（中文 > 英文 > 其他），减少手动配置 |
| **Obsidian 一键跳转** | 下载结果表格支持 Ctrl+点击，直接在 Obsidian 中打开文件 |
| **DeepSeek V4 深度分析** | 下载完成后可选择生成四层深度分析（拓扑结构/语义提取/认知机制/批判性重构），解决"看完就忘"的问题 |
| **双语字幕翻译** | 下载完成后可选择生成英中双语字幕（原文 + `> 中文译文`），解决英文字幕阅读障碍 |
| **分析与翻译共存** | 先分析后翻译时，分析引用块和双语字幕互不干扰，不会出现分析内容"吃掉"译文的问题 |
| **Frontmatter 持久保留** | 翻译后的文件始终保留标题、频道、链接、时长、提取时间等元数据 |
| **本地模型支持** | 支持加载本地 Qwen3 等 transformers 模型，分析和翻译均可离线运行，无需消耗 DeepSeek API 额度 |
| **CSV 报告** | 每次下载自动生成带时间戳的 CSV 报告，方便追溯 |
| **Token 消耗显示** | 每次 AI 分析/翻译后输出提示词/生成/总计 Token 数，方便统计用量 |
| **AI 模式切换** | 启动时按 0 使用本地模型，按 1 使用 DeepSeek API；直接回车使用 `config.py` 中的默认值 |
| **Cookie 自动注入** | 自动读取 `config.py` 或环境变量，下载需要登录的 B站字幕；启动时自动校验 Cookie 是否有效 |

---

## 4. 安装方法

### 步骤一：克隆项目

```bash
git clone https://github.com/decai335335-debug/video-sub-md.git
cd video-sub-md
```

### 步骤二：安装依赖

```bash
pip install -r requirements.txt
```

### 步骤三：配置 API 密钥、Cookie 和本地模型

**方式一：复制配置文件模板（推荐，最不容易被启动器/终端缓存覆盖）**

```bash
cp config.example.py config.py
```

然后编辑 `config.py`，填入你的真实值：

```python
# config.py
DEEPSEEK_API_KEY = "your-api-key"
DEFAULT_SESSDATA = "your-sessdata"

# 本地模型路径（可选）
LOCAL_MODEL_PATH = r"E:\Projects\ai\sensevoice_ime\model\千问3-1.7B"

# AI 模式默认值："local" 或 "api"
DEFAULT_AI_MODE = "local"
```

> ⚠️ `config.py` 已被加入 `.gitignore`，不会被提交到 GitHub。请勿手动移除 `.gitignore` 中的 `config.py` 条目。

**方式二：环境变量**

```bash
# DeepSeek API Key
$env:DEEPSEEK_API_KEY = "your-api-key"

# Bilibili SESSDATA（如需下载登录后才能看到的字幕）
$env:BILI_COOKIE = "your-sessdata"
```

> 注意：如果你使用第三方启动器/菜单打开本工具，启动器可能自带缓存的 `BILI_COOKIE` 环境变量，导致 `config.py` 中的值被覆盖。此时建议改用 `config.py` 配置，或使用项目根目录的 `run.ps1` / `run.cmd` 启动（会自动清空 `BILI_COOKIE`）。

### 步骤四：配置输出目录（可选）

修改 `config.py` 中的 `DEFAULT_OUTPUT_DIR` 和 `OBSIDIAN_VAULT_ROOT`：

```python
DEFAULT_OUTPUT_DIR = Path("E:/Obsidian/主仓库/11-subtitles")
OBSIDIAN_VAULT_ROOT = Path("E:/Obsidian/主仓库")
OBSIDIAN_VAULT_NAME = "主仓库"
```

---

## 5. 使用方法

### 场景一：批量下载视频字幕（最常用）

**什么时候用**：需要一次性获取多个视频的字幕内容

```bash
python main.py download
```

进入交互模式，粘贴混合链接（空行结束）：

```
  > https://www.bilibili.com/video/BV1xx411c7mD
  > https://www.youtube.com/watch?v=dQw4w9WgXcQ
  >
```

下载完成后会询问两个独立问题：

```
是否为下载的字幕生成深度分析？(a 是 / b 否): a
是否为下载的字幕生成翻译？(a 是 / b 否): a
```

- 输入 `a` 启用该功能，输入 `b` 跳过
- 深度分析调用 **Pro 模型**，翻译调用 **Flash 模型**
- 可以组合：a,a = 分析+翻译，a,b = 只分析，b,a = 只翻译，b,b = 都跳过
- **分析与翻译顺序无关**——先分析后翻译，或只翻译不分析，frontmatter 和分析内容都会正确保留

### 场景二：持续下载模式（推荐）

**什么时候用**：需要下载多个批次视频，不想每次都重新运行程序

下载完成后，程序会返回输入界面等待新链接。输入 `q` 退出程序。

### 场景三：命令行直接传链接

**什么时候用**：已知具体链接，不需要交互式输入

```bash
python main.py download "https://www.bilibili.com/video/BV1xx411c7mD" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 场景四：指定语言和并发数

**什么时候用**：想要指定字幕语言，或调整下载速度

```bash
python main.py download --lang zh --max-concurrent 3
```

| 参数 | 说明 |
|------|------|
| `--lang` / `-l` | 指定字幕语言代码，如 `zh`（中文）、`en`（英文） |
| `--max-concurrent` / `-c` | 最大并发数，默认 5 |

### 场景五：使用 Cookie 下载需登录的字幕

**什么时候用**：下载显示"该视频暂无可用字幕"的 B站视频

```bash
# 方式一：命令行参数
python main.py download --cookie "你的SESSDATA值"

# 方式二：环境变量（推荐）
$env:BILI_COOKIE = "你的SESSDATA值"
python main.py download
```

---

## 6. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **语言** | Python 3.10+ | 项目语言 |
| **CLI 框架** | Typer | 命令行界面 |
| **终端 UI** | Rich | 表格、面板等富文本输出 |
| **数据验证** | Pydantic v2 | 数据模型定义 |
| **HTTP 客户端** | requests + aiohttp | B站 API / YouTube 字幕获取 |
| **YouTube 字幕** | youtube-transcript-api + yt-dlp | 字幕提取 |
| **重试机制** | tenacity | 请求失败自动重试 |
| **本地 AI** | transformers + torch | 本地 Qwen3 等模型推理 |
| **AI 分析** | DeepSeek V4 Pro / 本地模型 | 四层深度分析生成（拓扑/语义/认知/批判） |
| **AI 翻译** | DeepSeek V4 Flash / 本地模型 | 英中双语字幕翻译（带编号对齐 + 强制行数修复） |

### 工具链

| 工具 | 用途 |
|------|------|
| Obsidian | Markdown 笔记管理与知识图谱 |
| DeepSeek API | 大模型推理与翻译 |

---

## 7. 文件结构

```
video-sub-md/
├── main.py              # 统一 CLI 入口，下载逻辑 + AI 分析/翻译调用
├── config.py            # 全局配置（API Key、Cookie、本地模型、模型选择）
├── config.example.py    # 配置模板（复制为 config.py 后填入真实值）
├── models.py            # 通用数据模型（DownloadResult、BatchReport）
├── requirements.txt     # 依赖列表
├── run.ps1              # PowerShell 启动脚本（自动清空 BILI_COOKIE，强制使用 config.py）
├── run.cmd              # CMD 启动脚本（自动清空 BILI_COOKIE，强制使用 config.py）
├── README.md            # 用户文档
├── DEV_LOG.md           # 开发日志（迭代历史、踩坑记录、设计决策）
└── core/
    ├── local_llm.py     # 本地大模型推理客户端（transformers，Qwen3 支持）
    ├── translator.py    # AI 翻译引擎（分段翻译 + 编号对齐 + 双语合并 + 文件写入）
    ├── bilibili/        # B站字幕下载引擎
    │   ├── downloader.py   # 下载主逻辑
    │   ├── extractor.py    # BV 号提取
    │   ├── formatter.py    # 字幕格式转换（MD/SRT/TXT）
    │   ├── metadata.py     # 元数据获取（标题、CID、字幕轨道）
    │   ├── models.py       # B站专用数据模型
    │   └── wbi_sign.py     # WBI 签名（部分接口需要）
    └── youtube/         # YouTube 字幕下载引擎
        ├── downloader.py   # 下载主逻辑
        ├── extractor.py    # 视频 ID 提取
        ├── formatter.py    # 字幕格式转换
        ├── metadata.py     # 元数据获取
        └── models.py       # YouTube 专用数据模型
```

---

## 8. 常见问题

**Q: B站视频显示"该视频暂无可用字幕"？**

A: 大概率是 Cookie 未设置或已过期。请重新获取 SESSDATA：
1. 用浏览器打开 `https://www.bilibili.com` 并登录
2. 按 **F12** → **Application** → **Cookies** → `https://www.bilibili.com`
3. 找到 `SESSDATA`，复制值到 `config.py` 的 `DEFAULT_SESSDATA`
4. 如果你使用第三方启动器，启动器可能缓存了旧的 `BILI_COOKIE`，请改用项目根目录的 `run.ps1` / `run.cmd` 启动

**Q: 启动时提示"当前 Cookie 未通过 B站登录校验"？**

A: 说明当前使用的 SESSDATA 已失效。请按上一问重新获取最新 SESSDATA 并更新到 `config.py`。如果确认 `config.py` 已更新但仍报警告，说明环境变量 `BILI_COOKIE` 覆盖了 `config.py`，请删除该环境变量或使用 `run.ps1` / `run.cmd` 启动。

**Q: 为什么命令行带 `--cookie` 可以，从启动器打开不行？**

A: `--cookie` 参数优先级最高，会覆盖所有其他配置。启动器打开时可能带入了旧的 `BILI_COOKIE` 环境变量，导致读到过期 Cookie。解决方法：
1. 删除系统/用户环境变量中的 `BILI_COOKIE`
2. 只用 `config.py` 管理 Cookie
3. 或使用项目自带的 `run.ps1` / `run.cmd` 启动（会自动清空环境变量中的 `BILI_COOKIE`）

**Q: YouTube 显示 IP 被封锁或请求超时？**

A: YouTube 对请求频率敏感，程序已内置限速（1-3 秒随机延迟）。如仍被封，暂停一段时间再试，或使用代理网络。

**Q: 文件名点击后 Obsidian 提示"未找到文件"？**

A: 检查 `config.py` 中的 `OBSIDIAN_VAULT_ROOT`（仓库根目录）和 `OBSIDIAN_VAULT_NAME`（仓库名称）是否与实际 Obsidian 配置一致。另外，视频标题中的 `#` 字符会被自动替换为 `_`，因为 Obsidian URI 把 `#` 解析为标题锚点分隔符。

**Q: DeepSeek API 调用失败或分析内容被截断？**

A: 
1. 检查环境变量 `$env:DEEPSEEK_API_KEY` 或 `config.py` 中的值是否正确
2. 确认使用的是 `deepseek-v4-pro`（分析）或 `deepseek-v4-flash`（翻译）
3. API timeout 已设置为 180 秒，如仍超时可能是网络问题
4. 分析用 Pro 模型输出较长，确保 `max_tokens=32768` 已生效

**Q: 翻译后的字幕行数和原文对不上？**

A: 当前版本已修复：
- 给每行原文加上**全局连续编号** `[1]` ~ `[N]`
- AI 返回后**验证编号连续性**，不连续则报警
- 行数不匹配时**强制对齐**，按比例合并或补齐
- 最终保证原文 N 行 → 译文 N 行，一一对应插入

**Q: 翻译后文件丢失了频道、链接等元数据？**

A: v0.5.0 已修复。旧版本的 `add_translation_to_file()` 把 `---` 误当成 YAML frontmatter 成对边界来处理，导致元数据被错误重建。新版本改为 `split("---", 1)`，正确识别 `---` 为 Markdown 分隔线，frontmatter 始终保留。

**Q: 先分析后翻译，分析内容"吃掉"了译文？**

A: v0.5.0 已修复该问题。v0.5.4 进一步修复：分析生成时会写入 `<!-- SUBTITLE_START -->` 标记明确分隔分析区和字幕区，翻译时只替换标记后的字幕部分，分析内容完整保留。

**Q: 先分析后翻译，分析内容消失了？**

A: 这是 v0.5.4 之前版本的已知问题。原因是分析区内可能包含 `---` Markdown 分隔线，导致字幕提取逻辑误把分析区截断。v0.5.4 已改用 `<!-- SUBTITLE_START -->` 标记做结构定位，分析区始终完整保留。

**Q: AI 分析里英文太多，能不能输出更多中文？**

A: v0.5.4 已在 system prompt 中明确要求：除非直接引用原文，否则所有分析、总结、表格内容必须使用中文；引用原文应简短并附中文解释。如仍不满意，可把 `config.py` 中的 `DEEPSEEK_MODEL` 从 `deepseek-v4-pro` 保持为 Pro（中文理解更强），或检查本地模型对中文指令的遵循度。

**Q: 下载的字幕文件名被截断或包含乱码字符？**

A: 程序会自动删除 Windows 文件名保留字符（`\/:*?"<>|`），并将 `#` 替换为 `_`（避免 Obsidian URI 锚点解析问题）。文件名最大长度限制为 150 字符。

---

## 9. 未来开发路线图

### 当前状态：稳定版（v0.5.4）

### 近期（下个版本 v0.6.0）

| 功能 | 为什么优先做 |
|------|-------------|
| **翻译编号强制对齐兜底** | 当前翻译已通过全局编号大幅改善，但 AI 仍偶发行数偏差，需要更鲁棒的后处理机制确保 100% 对齐 |
| **多语言字幕同时下载** | 用户反馈有时需要中英双语对照原文，一次性获取比下载两次更方便 |
| **支持指定输出格式（SRT/TXT/MD）** | 当前默认 MD，部分用户需要将字幕导入视频剪辑软件（需 SRT） |
| **VS Code 终端 OSC 8 兼容性** | VS Code 更新后内置终端不再渲染 OSC 8 超链接，需增加 `--open` 标志或 PowerShell fallback |

### 中期（未来 3-6 个月 v0.7.x ~ v1.0.0）

| 功能 | 带来的价值 |
|------|-----------|
| **插件系统** | 让社区可以自定义后处理流程（如自动同步到 Notion、生成思维导图、导出 Anki 卡片），避免核心代码膨胀 |
| **Web 界面** | 降低非技术用户上手门槛，图形化粘贴链接、查看进度、管理历史任务 |
| **翻译质量评分** | 对 AI 翻译结果自动打分，低质量段落高亮提醒用户手动校对 |
| **配置管理升级** | 引入 `pydantic-settings` 替代手动 `config.py`，支持 `.env` 文件和环境变量自动加载，避免 config.py 被误提交的安全风险 |

### 长期愿景

- **方向**：成为视频内容知识管理的**首选入口工具**，不只是下载字幕，而是从"看视频"到"形成知识资产"的完整 pipeline
- **生态位**：在同类项目中，差异化定位是**深度 AI 分析 + 双语翻译 + Obsidian 工作流**的三位一体，而非单纯的字幕下载器

### 如何参与

- 有需求？提交 Issue 并打上 `enhancement` 标签
- 想贡献？查看 `good first issue` 标签（如改进翻译对齐算法、增加新平台支持）

---

## 10. 更新日志

### v0.5.4 (2026-06-12)
- 🔧 修复 B站字幕接口 WBI 签名未应用的问题（`wbi_sign.py` 已存在但未被调用，导致部分视频无法获取字幕）
- 🔧 修复 `main.py` 中 `config.DEFAULT_SESSDATA` 引用错误（未 import config 模块）
- 🔧 修复空 `subtitle_url` 导致的 `Invalid URL` 崩溃
- 🔧 修复先分析后翻译时字幕体被识别为空的回归问题：`_split_file_sections()` 中 `str.find()` 返回 `-1` 时，`-1 < 200` 被误判为 `True`，导致无分析的文件被当成有分析处理
- ✅ 新增 `<!-- SUBTITLE_START -->` 结构标记，明确分隔分析区与字幕区，彻底解决分析区内含 `---` 分隔线时的解析歧义
- ✅ 新增启动时 Cookie 登录状态校验，无效 Cookie 会明确提示
- ✅ 新增 `need_login_subtitle` 检测，需要登录的字幕会给出清晰错误信息而非“暂无可用字幕”
- ✅ 新增本地大模型支持：启动时按 0 使用本地 Qwen3 模型，按 1 使用 DeepSeek API；分析和翻译均可调用本地模型
- ✅ 新增每次 AI 调用后输出 Token 消耗（提示词 / 生成 / 总计）
- ⚡ 优化调试输出 `_debug()`，Windows GBK 控制台下遇到 Unicode 字符自动降级为 ASCII

### v0.5.3
- **修复** AI 分析标题层级倒序：Prompt 要求 AI 直接从 `###` 开始，避免与 `## 🔍 深度分析` 并列
- **修复** 时间轴方括号 `[主题]` `[动作]` 被误解析为链接，改为普通文本
- **修复** 表格被 `- ` 列表包裹导致渲染失败，格式规范锁新增"表格不要放在列表内部"
- **修复** 时间区间反引号包裹不完整（`` `01:17`-`04:40` `` → `` `01:17-04:40` ``）
- **修复** `##` 直接跳到 `####` 的层级断裂，第二层插件激活要求输出 `### 插件X：xxx型分析` 中间层级
- **新增** Prompt 格式规范锁扩展至 10 条，覆盖标题/表格/列表/时间区间/方括号

### v0.5.2
- **修复** AI 深度分析的 Markdown 格式渲染问题：Prompt 中 6 处表格格式从列表项改为标准 Markdown 表格
  - 1.2 语义提取：支撑论据表（4列）、概念图谱（3列）
  - A1 学习路径：核心知识模块（4列）、常见陷阱地图（3列）
  - A2 知识晶体提取（4列）、B2 修辞与说服分析（4列）
- **修复** 分析内容被 `> ` 引用块包裹导致渲染失败的问题，改用 `## 🔍 深度分析` 标题分隔
- **修复** `_clean_summary_markdown()` 洗掉列表缩进的问题，保留子列表的两个空格缩进
- **新增** Prompt 格式规范锁（7条规则）+ 后处理自动清洗，确保表格/列表/论证树正确渲染

### v0.5.1
- **新增** Bilibili 字幕文件头部格式统一为 YouTube 风格（频道/链接/语言/时长/提取时间）
- `SubtitleResult` 新增 `author`/`url`/`duration` 字段，元数据更完整
- B站和 YouTube 字幕文件结构完全一致，便于后续 AI 分析/翻译统一处理

### v0.5.0
- **修复** 翻译后丢失 frontmatter（标题、频道、链接等元数据）的问题
- **修复** 先分析后翻译时分析内容"吃掉"译文导致错位的问题
- **修复** YouTube 视频标题含 `#` 时 Obsidian URI 解析错误（`#` 替换为 `_`）
- **修复** Windows 路径 `Path.relative_to()` 因大小写/盘符差异导致失败，改为字符串前缀匹配
- **新增** `config.example.py` 模板，正式分离敏感配置与代码仓库

### v0.4.1
- **修复** 翻译行数错位：全局编号 `[1]`~`[N]` + 强制行数对齐 `_force_line_alignment()`
- **新增** 分段翻译，长字幕自动分 chunk 避免 API 长度限制
- **优化** Prompt 强化：明确禁止换行拆分、禁止输出额外内容

### v0.4.0
- **新增** 双语字幕翻译功能，使用 Flash 模型快速翻译英文字幕
- 下载完成后可选择同时生成深度分析（Pro）和/或翻译（Flash）
- 翻译格式：`原文` + 换行 + `> 中文译文`
- config.py 新增 `DEEPSEEK_FLASH_MODEL` 配置项

### v0.3.0
- **新增** 循环下载模式 —— 下载完成后不退出，持续等待新链接输入，按 `q` 退出
- **升级** DeepSeek API 至 V4 系列（`deepseek-v4-pro` / `deepseek-v4-flash`）
- 增加 `thinking` + `reasoning_effort` 参数，启用推理模式提升分析质量
- API timeout 从 60 秒增加到 180 秒
- `max_tokens` 从 800 提升至 32768，避免长分析被截断

### v0.2.0
- **新增** DeepSeek AI 深度分析功能，下载完成后可生成四层解码分析（拓扑结构/语义提取/认知机制/批判性重构）
- 修复中文文件名被 `Path.with_suffix()` 截断的 bug
- 文件名非法字符处理改为直接删除而非替换为下划线
- 文件名最大长度从 80 扩展到 150 字符

### v0.1.0
- 支持 Bilibili + YouTube 混合链接输入
- 自动识别平台并分发到对应下载引擎
- 统一并发调度（B站线程池 + YouTube 异步）
- 下载结果表格支持 Ctrl+点击跳转 Obsidian
- 支持 `BILI_COOKIE` 环境变量和 `--cookie` 参数
- 自动生成 CSV 报告
