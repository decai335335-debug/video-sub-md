# video-sub-md — 视频字幕批量下载 + AI 分析 + 多语言视频批量下载

一键批量下载 Bilibili / YouTube / Coursera 视频字幕为 Markdown，AI 自动生成深度分析笔记和双语字幕翻译；同时支持从 Bilibili 批量下载多语言游戏角色视频，自动提取中日英韩四语音频轨道并生成 JSON 绑定文件。

---

## 1. 一句话定位

**做视频知识管理时，从"下载字幕→AI分析→双语翻译"到"批量下载多语言视频→提取音频轨道→绑定管理"，全程自动化，不再需要手动复制粘贴、逐句整理或逐个下载。**

---

## 2. 解决什么痛点

### 以前是这样的：
- 想保存视频字幕，需要手动复制粘贴，费时费力
- 多个视频的字幕要逐个处理，无法批量操作
- YouTube 和 B站字幕格式不统一，汇总困难
- 看完视频记不住重点，需要手动整理笔记
- 英文字幕视频需要逐句翻译，没有趁手工具
- 游戏角色视频有多语言版本（中日英韩），需要逐个下载不同语言，管理混乱
- 下载完一批视频后，想继续下载需要重新运行程序
- 翻译后的字幕文件丢失了原始的频道/链接/时长等元数据
- 先做了 AI 深度分析再翻译，分析内容会"吃掉"译文导致错位

### 现在是这样的：
- 一键批量下载字幕，自动识别平台，输出统一 Markdown 格式
- 支持循环下载模式，输入 `q` 退出，其余时间持续运行
- 下载完成后可选择调用 DeepSeek V4 生成四层深度分析
- 英文字幕可一键生成英中双语对照（原文 + `> 译文` 格式）
- **分析内容和双语字幕可以共存**——先分析后翻译，互不影响
- **标题、频道、链接等元数据始终保留**，翻译不会丢失 frontmatter
- 结果文件支持 Obsidian 超链接，一键直达
- **批量下载多语言游戏角色视频**（7 个游戏：原神/崩坏星穹铁道/绝区零/鸣潮/终末地/守望先锋/重返未来1999），自动检测 4 种语言，按角色/类型分类存放
- **自动提取多语言音频轨道**为 MP3，生成 JSON 绑定文件，一个视频 + 四语音频随意切换

### 适合谁用：
- **知识创作者** —— 快速提取视频核心内容，生成笔记素材，AI 自动整理成结构化分析
- **英语学习者** —— 批量下载英文字幕，一键生成双语对照，边看边学
- **游戏内容研究者** —— 批量下载角色 PV/演示视频，自动提取多语言音频，做对比研究
- **本地化工作者** —— 需要获取游戏多语言视频素材，做配音/翻译/分析
- **Obsidian 用户** —— 统一管理视频笔记，支持双向链接和知识图谱

---

## 3. 核心功能

### 字幕下载与分析

| 功能 | 解决什么问题 |
|------|------------|
| **混合链接输入** | 同时粘贴 B站、YouTube、Coursera、Douyin 链接，自动识别平台分别处理，不用手动分类 |
| **循环下载模式** | 下载完成后不退出，继续等待新链接输入，按 `q` 才退出，避免频繁重启程序 |
| **批量并发下载** | 一次性处理多个视频，充分利用带宽，大幅提升效率 |
| **智能语言选择** | 自动按优先级选择字幕语言（中文 > 英文 > 其他），减少手动配置 |
| **Obsidian 一键跳转** | 下载结果表格支持 Ctrl+点击，直接在 Obsidian 中打开文件 |
| **DeepSeek V4 深度分析** | 下载完成后可选择生成四层深度分析（拓扑结构/语义提取/认知机制/批判性重构），解决"看完就忘"的问题 |
| **双语字幕翻译** | 下载完成后可选择生成英中双语字幕（原文 + `> 中文译文`），解决英文字幕阅读障碍 |
| **分析与翻译共存** | 先分析后翻译时，分析引用块和双语字幕互不干扰，不会出现分析内容"吃掉"译文的问题 |
| **Frontmatter 持久保留** | 翻译后的文件始终保留标题、频道、链接、时长、提取时间等元数据 |
| **本地模型支持** | 支持加载本地 Qwen3 等 transformers 模型，分析和翻译均可离线运行，无需消耗 DeepSeek API 额度 |

### 视频批量下载（新增）

| 功能 | 解决什么问题 |
|------|------------|
| **7 游戏批量下载** | 支持原神/崩坏星穹铁道/绝区零/鸣潮/终末地/守望先锋/重返未来1999，一次运行下载全部角色视频 |
| **多语言自动检测** | 自动识别视频分P中的 `【英】/【日】/【韩】/【中】` 等语言标记，区分单视频和多语言视频 |
| **视频 + 音频分离** | 多语言视频：P1 下载为 MP4 视频，所有 P 提取为 MP3 音频；单视频：直接下载 MP4 |
| **JSON 绑定文件** | 生成绑定 JSON，记录视频与各语言音频的对应关系，方便后续切换和管理 |
| **按角色分类存放** | 自动按 `角色名/视频类型/` 创建文件夹，如 `丝柯克/角色PV/` |
| **路径回写 JSON** | 下载完成后将实际文件路径写回原 JSON，方便后续程序读取和使用 |
| **Cookie 自动复用** | SESSDATA 保存后自动复用，下次下载直接回车确认 |

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

**方式一：复制配置文件模板（推荐）**

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

> ⚠️ `config.py` 已被加入 `.gitignore`，不会被提交到 GitHub。

**方式二：环境变量**

```bash
# DeepSeek API Key
$env:DEEPSEEK_API_KEY = "your-api-key"

# Bilibili SESSDATA
$env:BILI_COOKIE = "your-sessdata"
```

> 注意：如果使用第三方启动器，可能自带缓存的 `BILI_COOKIE`，建议改用 `config.py` 或项目自带的 `run.ps1` / `run.cmd` 启动。

### 步骤四：安装 ffmpeg（视频下载必需）

```powershell
# 方式一：winget（推荐）
winget install ffmpeg

# 方式二：手动下载并加入 PATH
# https://ffmpeg.org/download.html
```

验证安装：
```bash
ffmpeg -version
```

### 步骤五：配置输出目录（可选）

修改 `config.py`：

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
  > https://www.douyin.com/jingxuan?modal_id=7632664889143627059
  >
```

下载完成后会询问：

```
是否为下载的字幕生成深度分析？(a 是 / b 否): a
是否为下载的字幕生成翻译？(a 是 / b 否): a
```

- 输入 `a` 启用，输入 `b` 跳过
- 深度分析调用 **Pro 模型**，翻译调用 **Flash 模型**
- 可以组合：a,a = 分析+翻译，a,b = 只分析，b,a = 只翻译，b,b = 都跳过

### 场景二：批量下载游戏角色视频（多语言）

**什么时候用**：需要下载某个游戏的全部角色视频，自动提取多语言音频

```powershell
# 下载原神全部角色视频
cd E:\Projects\ai\video-sub-md
python download_genshin_videos.py
```

1. 输入 SESSDATA（或回车使用已保存的）
2. 脚本自动遍历 JSON 中的所有角色
3. 按 `角色名/视频类型/` 分类下载
4. 多语言视频自动提取 4 种音频（MP3）并生成 JSON 绑定

**支持的游戏**：

| 游戏 | 脚本 | 输出目录 |
|------|------|---------|
| 原神 | `download_genshin_videos.py` | `视频\原神` |
| 崩坏星穹铁道 | `download_hsr_videos.py` | `视频\崩坏星穹铁道` |
| 绝区零 | `download_zzz_videos.py` | `视频\绝区零` |
| 鸣潮 | `download_wuthering_videos.py` | `视频\鸣潮` |
| 终末地 | `download_endfield_videos.py` | `视频\终末地` |
| 守望先锋 | `download_ow_videos.py` | `视频\守望先锋` |
| 重返未来1999 | `download_r1999_videos.py` | `视频\重返未来1999` |

### 场景三：下载单个多语言视频

**什么时候用**：只需要下载一个特定的多语言视频

```bash
python download_bili_multilang.py
```

输入 BV 号，脚本自动列出分P：

```
[1] [中文] 《原神》角色预告-「丝柯克：寰墟之叹」 (2:33)
[2] [日文] 日-《原神》角色预告-「丝柯克：寰墟之叹」 (2:38)
[3] [英文] 英-《原神》角色预告-「丝柯克：寰墟之叹」 (2:38)
[4] [韩文] 韩-《原神》角色预告-「丝柯克：寰墟之叹」 (2:38)

  [W] 下载中文视频 + 全部语言音频
  [Q] 全部下载为视频
```

输入 `W`：下载 P1 为 MP4 视频，所有 P 提取为 MP3 音频，生成 JSON 绑定。

### 场景四：按 Section 选择下载视频

**什么时候用**：合集视频中有多个 section，只想下载某个 section

```bash
python download_bili_video.py
```

支持两种模式：
- **UGC 合集**：列出 sections，选择下载
- **多P视频**：列出分P，按数字选择语言（1=中文, 2=日文...）

### 场景五：修复已下载的多语言视频（补音频）

**什么时候用**：之前下载的视频缺少多语言音频，需要补提取

```bash
python fix_multilang.py wuthering
```

脚本会扫描已下载的 MP4，检测实际分P，补提取缺少的音频轨道。

---

## 6. 技术栈

### 字幕下载与分析

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
| **AI 分析** | DeepSeek V4 Pro / 本地模型 | 四层深度分析生成 |
| **AI 翻译** | DeepSeek V4 Flash / 本地模型 | 英中双语字幕翻译 |

### 视频批量下载

| 层级 | 技术 | 说明 |
|------|------|------|
| **语言** | Python 3.12 | 视频下载脚本 |
| **HTTP 客户端** | requests | Bilibili API 请求 |
| **API 签名** | WBI 签名 | Bilibili 接口动态签名 |
| **视频处理** | ffmpeg | 视频下载、音频提取（MP3） |
| **数据格式** | JSON | 多语言绑定文件 |
| **配置管理** | 本地 JSON | Cookie 自动保存复用 |

### 工具链

| 工具 | 用途 |
|------|------|
| Obsidian | Markdown 笔记管理与知识图谱 |
| DeepSeek API | 大模型推理与翻译 |
| ffmpeg | 视频下载、转码、音频提取 |

---

## 7. 文件结构

```
video-sub-md/
├── main.py                        # 字幕下载 CLI 入口
├── config.py                      # 全局配置（API Key、Cookie、目录）
├── config.example.py              # 配置模板
├── models.py                      # 通用数据模型
├── requirements.txt               # 依赖列表
├── run.ps1                        # PowerShell 启动脚本
├── run.cmd                        # CMD 启动脚本
├── README.md                      # 用户文档
├── DEV_LOG.md                     # 开发日志
│
# === 视频批量下载脚本 ===
├── download_bili_video.py         # 多P视频选择下载器（支持 UGC 合集 + 多P）
├── download_bili_multilang.py     # 多语言视频下载器（视频 + 全部音频）
├── download_bili_section.py       # Section 选择音频下载器
├── download_bili_section_video.py   # Section 选择视频下载器（1080P）
├── download_bili_collection_audio.py  # 通用音频下载器（UGC 合集 + 多P）
├── download_bili_audio.py         # 基础音频下载器
│
# === 7 游戏批量下载脚本 ===
├── download_genshin_videos.py     # 原神角色视频批量下载
├── download_hsr_videos.py         # 崩坏星穹铁道
├── download_zzz_videos.py         # 绝区零
├── download_wuthering_videos.py   # 鸣潮
├── download_endfield_videos.py    # 终末地
├── download_ow_videos.py          # 守望先锋
├── download_r1999_videos.py       # 重返未来1999
├── fix_multilang.py               # 多语言视频修复（补音频）
│
# === 核心模块 ===
├── core/
│   ├── local_llm.py               # 本地大模型推理客户端
│   ├── translator.py              # AI 翻译引擎
│   ├── bilibili/                  # B站引擎
│   │   ├── downloader.py          # 字幕下载主逻辑
│   │   ├── extractor.py           # BV 号提取
│   │   ├── formatter.py           # 字幕格式转换
│   │   ├── metadata.py            # 元数据获取
│   │   ├── models.py              # 数据模型
│   │   ├── http.py                # HTTP 会话管理
│   │   └── wbi_sign.py            # WBI 签名算法
│   └── youtube/                   # YouTube 引擎
│       ├── downloader.py
│       ├── extractor.py
│       ├── formatter.py
│       ├── metadata.py
│       └── models.py
│
# === 输出目录（运行时生成）===
└── downloads/                     # 下载输出
    ├── audio/                     # 音频下载
    ├── video_1080p/              # 视频下载
    └── multilang/                # 多语言视频+音频
```

---

## 8. 常见问题

**Q: B站视频显示"该视频暂无可用字幕"？**

A: 大概率是 Cookie 未设置或已过期。请重新获取 SESSDATA：
1. 用浏览器打开 `https://www.bilibili.com` 并登录
2. 按 **F12** → **Application** → **Cookies** → `https://www.bilibili.com`
3. 找到 `SESSDATA`，复制值到 `config.py` 的 `DEFAULT_SESSDATA`
4. 如果使用第三方启动器，改用 `run.ps1` / `run.cmd` 启动

**Q: 视频下载脚本提示"未检测到 ffmpeg"？**

A: 视频下载和音频提取依赖 ffmpeg。安装方法：
```powershell
winget install ffmpeg
```
安装后重新打开终端，确保 `ffmpeg -version` 能正常输出。

**Q: 多语言视频只下载了中文，没有日文/英文/韩语音频？**

A: 可能是语言标记检测问题。运行修复脚本补提取：
```bash
python fix_multilang.py <游戏key>
# 例如：python fix_multilang.py wuthering
```

**Q: 启动时提示"当前 Cookie 未通过 B站登录校验"？**

A: SESSDATA 已失效，请重新获取并更新到 `config.py`。如果确认已更新但仍报警，说明环境变量 `BILI_COOKIE` 覆盖了 `config.py`，请删除该环境变量或使用 `run.ps1` / `run.cmd` 启动。

**Q: 下载的 JSON 文件里的 `file` 字段有什么用？**

A: `file` 字段记录了视频/音频的实际本地路径。下载完成后，脚本会自动把路径写回 JSON，方便后续程序（如播放器、分析工具）读取和使用。

**Q: YouTube 显示 IP 被封锁或请求超时？**

A: YouTube 对请求频率敏感，程序已内置限速（1-3 秒随机延迟）。如仍被封，暂停一段时间再试，或使用代理网络。

**Q: 文件名点击后 Obsidian 提示"未找到文件"？**

A: 检查 `config.py` 中的 `OBSIDIAN_VAULT_ROOT` 和 `OBSIDIAN_VAULT_NAME` 是否与实际 Obsidian 配置一致。视频标题中的 `#` 字符会被自动替换为 `_`，因为 Obsidian URI 把 `#` 解析为标题锚点分隔符。

**Q: DeepSeek API 调用失败或分析内容被截断？**

A: 
1. 检查环境变量 `$env:DEEPSEEK_API_KEY` 或 `config.py` 中的值是否正确
2. 确认使用的是 `deepseek-v4-pro`（分析）或 `deepseek-v4-flash`（翻译）
3. API timeout 已设置为 180 秒，如仍超时可能是网络问题

**Q: 翻译后的字幕行数和原文对不上？**

A: 当前版本已修复：全局连续编号 `[1]`~`[N]` + 强制行数对齐，确保原文 N 行 → 译文 N 行。

**Q: 视频下载脚本可以移到其他文件夹运行吗？**

A: 可以。脚本使用绝对路径引用 `video-sub-md` 项目目录（`PROJECT_DIR = Path(r"E:")`），所以脚本可以放在任意位置运行。

---

## 9. 未来开发路线图

### 当前状态：稳定版（v0.6.0）

字幕下载稳定运行，视频批量下载功能已上线，支持 7 个游戏的多语言视频下载和音频提取。

### 近期（下个版本 v0.7.0）

| 功能 | 为什么优先做 |
|------|-------------|
| **多语言字幕同时下载** | 用户反馈有时需要中英双语对照原文，一次性获取比下载两次更方便 |
| **支持指定输出格式（SRT/TXT/MD）** | 当前默认 MD，部分用户需要将字幕导入视频剪辑软件（需 SRT） |
| **视频下载 GUI 界面** | 降低非技术用户上手门槛，图形化选择游戏、查看进度 |
| **多语言音频自动合并** | 将视频 + 多语言音频合并为一个 MKV 文件（带多音轨），播放器可直接切换语言 |

### 中期（未来 3-6 个月 v0.8.x ~ v1.0.0）

| 功能 | 带来的价值 |
|------|-----------|
| **插件系统** | 让社区可以自定义后处理流程（如自动同步到 Notion、生成思维导图、导出 Anki 卡片），避免核心代码膨胀 |
| **Web 界面** | 降低非技术用户上手门槛，图形化粘贴链接、查看进度、管理历史任务 |
| **翻译质量评分** | 对 AI 翻译结果自动打分，低质量段落高亮提醒用户手动校对 |
| **配置管理升级** | 引入 `pydantic-settings` 替代手动 `config.py`，支持 `.env` 文件和环境变量自动加载 |
| **更多游戏支持** | 扩展支持其他游戏的多语言视频（如崩坏3、明日方舟、蔚蓝档案等） |

### 长期愿景

- **方向**：成为视频内容知识管理的**首选入口工具**，不只是下载字幕，而是从"看视频"到"形成知识资产"的完整 pipeline；同时成为游戏多语言视频素材管理的**标准工具**
- **生态位**：在同类项目中，差异化定位是**深度 AI 分析 + 双语翻译 + Obsidian 工作流 + 多语言视频批量下载**的四位一体，而非单纯的字幕下载器或视频下载器

### 如何参与

- 有需求？提交 Issue 并打上 `enhancement` 标签
- 想贡献？查看 `good first issue` 标签（如改进翻译对齐算法、增加新平台支持、新增游戏批量下载脚本）

---

## 10. 更新日志

- v0.6.0 (2026-07-10) ✅ 新增 7 游戏批量视频下载器（原神/崩铁/绝区零/鸣潮/终末地/守望先锋/重返未来1999） ✅ 新增多语言视频自动检测（【英】/【日】/【韩】/【中】格式） ✅ 新增多语言音频提取为 MP3 + JSON 绑定 ✅ 新增 fix_multilang.py 修复脚本（补提取音频） ✅ 新增 download_bili_multilang.py 单视频多语言下载器 ✅ 新增 download_bili_video.py 多P选择下载器 ⚡ 优化视频下载脚本编码兼容性（Windows GBK 控制台） ⚡ 优化 Cookie 自动保存复用机制 📋 新增视频下载配置独立管理（download_video_config.json）
- v0.5.4 (2026-06-12) 🔧 修复 B站字幕接口 WBI 签名未应用的问题 🔧 修复 `main.py` 中 `config.DEFAULT_SESSDATA` 引用错误 🔧 修复空 `subtitle_url` 导致的 `Invalid URL` 崩溃 🔧 修复先分析后翻译时字幕体被识别为空的回归问题 ✅ 新增 `<!-- SUBTITLE_START -->` 结构标记，明确分隔分析区与字幕区 ✅ 新增启动时 Cookie 登录状态校验 ✅ 新增 `need_login_subtitle` 检测 ✅ 新增本地大模型支持（Qwen3） ✅ 新增每次 AI 调用后输出 Token 消耗 ⚡ 优化调试输出 `_debug()`，Windows GBK 控制台 Unicode 自动降级
- v0.5.0 (2026-06-10) 🔧 修复翻译后丢失 frontmatter 的问题 🔧 修复先分析后翻译时分析内容"吃掉"译文的问题 🔧 修复 YouTube 视频标题含 `#` 时 Obsidian URI 解析错误 🔧 修复 Windows 路径 `Path.relative_to()` 因大小写/盘符差异导致失败 ✅ 新增 `config.example.py` 模板，正式分离敏感配置与代码仓库
- v0.4.0 (2026-06-10) ✅ 新增双语字幕翻译功能（Flash 模型） ✅ 新增分段翻译，长字幕自动分 chunk ✅ 新增循环下载模式
- v0.3.0 (2026-06-10) ✅ 升级 DeepSeek API 至 V4 系列 ✅ 启用 reasoning 模式（thinking + reasoning_effort） ✅ 增加 timeout 180s 和 max_tokens 32768
- v0.2.0 (2026-06-09) ✅ 新增 DeepSeek AI 深度分析功能（四层协议） ✅ 修复中文文件名被 `Path.with_suffix()` 截断的 bug
- v0.1.0 (2026-06-08) 🚀 初始版本，支持 Bilibili + YouTube 混合链接批量下载字幕，统一 Markdown 输出，Obsidian 集成
