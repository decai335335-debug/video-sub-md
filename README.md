# video-sub-md — 统一视频字幕下载器

一键批量下载 **Bilibili + YouTube** 视频字幕，输出为 Markdown，并可调用 **DeepSeek AI** 自动生成深度内容分析。

---

## 一句话定位

从 Bilibili / YouTube 批量下载视频字幕为 Markdown，支持 Ctrl+点击在 Obsidian 中直接打开，并可 AI 生成深度分析。

---

## 解决什么痛点

### 以前是这样的：
- 想保存视频字幕，需要手动复制粘贴，费时费力
- 多个视频的字幕要逐个处理，无法批量操作
- 看完视频记不住重点，需要手动整理笔记
- YouTube 和 B站字幕格式不统一，汇总困难

### 现在是这样的：
- 一键批量下载，自动识别平台，输出统一 Markdown 格式
- 下载完成后可选择调用 DeepSeek AI 生成四层深度分析
- 结果文件支持 Obsidian 超链接，一键直达

### 适合谁用：
- **知识创作者** —— 快速提取视频核心内容，生成笔记素材
- **AI 学习者** —— 获取字幕数据用于微调或 RAG 构建
- **研究人员** —— 批量采集视频内容用于分析和对比
- ** Obsidian 用户** —— 统一管理视频笔记，支持双向链接

---

## 核心功能

| 功能 | 解决什么问题 |
|------|-------------|
| **混合链接输入** | 同时粘贴 B站和 YouTube 链接，自动识别平台分别处理，不用手动分类 |
| **批量并发下载** | 一次性处理多个视频，充分利用带宽，大幅提升效率 |
| **智能语言选择** | 自动按优先级选择字幕语言（中文 > 英文 > 其他），减少手动配置 |
| **Obsidian 一键跳转** | 下载结果表格支持 Ctrl+点击，直接在 Obsidian 中打开文件 |
| **DeepSeek AI 分析** | 下载完成后可选择生成四层深度分析（拓扑结构/语义提取/认知机制/批判性重构） |
| **CSV 报告** | 每次下载自动生成带时间戳的 CSV 报告，方便追溯 |
| **Cookie 自动注入** | 自动读取环境变量，下载需要登录的 B站字幕 |

---

## 安装方法

### 步骤一：克隆或下载项目

```bash
git clone <仓库地址>
cd video-sub-md
```

### 步骤二：安装依赖

```bash
pip install -r requirements.txt
```

### 步骤三：配置（如需下载 B站字幕）

获取 SESSDATA：
1. 用浏览器打开 `https://www.bilibili.com` 并登录
2. 按 **F12** → **Application** → **Cookies** → `https://www.bilibili.com`
3. 找到 `SESSDATA`，复制它的值

在 `config.py` 中配置（默认已填入）：
```python
DEFAULT_SESSDATA = "你的SESSDATA值"
```

### 步骤四：（可选）配置 DeepSeek API

如需 AI 分析功能，在 `config.py` 中设置 API Key：

```python
DEEPSEEK_API_KEY = "你的API密钥"
```

---

## 使用方法

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

下载完成后会询问：

```
是否为下载的字幕生成深度分析？(a 是 / b 否): a
```

输入 `a` 则调用 DeepSeek 生成分析，输入 `b` 跳过。

### 场景二：命令行直接传链接

**什么时候用**：已知具体链接，不需要交互式输入

```bash
python main.py download "https://www.bilibili.com/video/BV1xx411c7mD" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 场景三：指定语言和并发数

**什么时候用**：想要指定字幕语言，或调整下载速度

```bash
python main.py download --lang zh --max-concurrent 3
```

| 参数 | 说明 |
|------|------|
| `--lang` / `-l` | 指定字幕语言代码，如 `zh`（中文）、`en`（英文） |
| `--max-concurrent` / `-c` | 最大并发数，默认 5 |

### 场景四：使用 Cookie 下载需登录的字幕

**什么时候用**：下载显示"该视频暂无可用字幕"的 B站视频

```bash
# 方式一：命令行参数
python main.py download --cookie "你的SESSDATA值"

# 方式二：环境变量（推荐）
$env:BILI_COOKIE = "你的SESSDATA值"
python main.py download
```

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **语言** | Python 3.10+ | 项目语言 |
| **CLI 框架** | Typer | 命令行界面 |
| **终端 UI** | Rich | 表格、面板等富文本输出 |
| **数据验证** | Pydantic v2 | 数据模型定义 |
| **HTTP 客户端** | requests + aiohttp | B站 API / YouTube 字幕获取 |
| **YouTube 字幕** | youtube-transcript-api + yt-dlp | 字幕提取 |
| **重试机制** | tenacity | 请求失败自动重试 |
| **AI 分析** | DeepSeek API | 深度内容分析生成 |

---

## 文件结构

```
video-sub-md/
├── main.py              # 统一 CLI 入口，下载逻辑 + AI 分析调用
├── config.py            # 全局配置（SESSDATA、输出目录、DeepSeek API）
├── models.py            # 通用数据模型（DownloadResult、BatchReport）
├── requirements.txt     # 依赖列表
├── README.md
└── core/
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

## 常见问题

**Q: B站视频显示"该视频暂无可用字幕"？**
A: 大概率是 Cookie 未设置或已过期。请重新获取 SESSDATA 并更新 `config.py` 中的 `DEFAULT_SESSDATA`。

**Q: YouTube 显示 IP 被封锁或请求超时？**
A: YouTube 对请求频率敏感，程序已内置限速（1-3 秒随机延迟）。如仍被封，暂停一段时间再试，或使用代理网络。

**Q: 文件名点击后 Obsidian 提示"未找到文件"？**
A: 检查 `config.py` 中的 `OBSIDIAN_VAULT_ROOT`（仓库根目录）和 `OBSIDIAN_VAULT_NAME`（仓库名称）是否与实际 Obsidian 配置一致。

**Q: DeepSeek API 调用失败？**
A: 检查 `config.py` 中的 `DEEPSEEK_API_KEY` 是否正确。如使用环境变量方式，确保已设置 `$env:DEEPSEEK_API_KEY`。

**Q: 下载的字幕文件名被截断？**
A: 已修复。旧文件可删除后重新下载。如遇特殊字符问题，程序会自动删除 Windows 文件名保留字符（`\\/:*?"<>|`）。

---

## 未来开发路线图

### 当前状态：稳定版

### 近期（下个版本）
- **多语言字幕同时下载** —— 用户反馈有时需要中英双语对照，一次性获取更方便
- **支持指定输出格式（SRT/TXT/MD）** —— 当前默认 MD，可选择其他格式

### 中期（未来 3-6 个月）
- **插件系统** —— 让社区可以自定义后处理流程（如自动同步到 Notion、生成思维导图等）
- **Web 界面** —— 提供图形界面，降低非技术用户上手门槛

### 长期愿景
- 成为视频内容知识管理的首选工具，不只是下载字幕，而是构建**视频知识库**的入口

### 如何参与
- 有需求？提交 Issue 并打上 `enhancement` 标签
- 想贡献？查看 `good first issue` 标签

---

## 更新日志

### v0.2.0
- 新增 **DeepSeek AI 深度分析**功能，下载完成后可生成四层解码分析（拓扑结构/语义提取/认知机制/批判性重构）
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
