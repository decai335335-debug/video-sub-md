# video-sub-md — 统一视频字幕下载器

一键批量下载 **Bilibili + YouTube** 视频字幕，自动识别平台、混合链接输入，输出为 Markdown，支持 **Ctrl+点击在 Obsidian 中打开**。

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **混合链接输入** | 同时粘贴 Bilibili 和 YouTube 链接，自动识别平台分别处理 |
| **智能平台识别** | `bilibili.com` / `BV` 号 → B站；`youtube.com` / `youtu.be` → YouTube |
| **并发下载** | 统一并发控制，B站线程池 + YouTube 异步混合调度 |
| **Obsidian 一键跳转** | 下载结果表格中的文件名支持 **Ctrl+点击** 直接在 Obsidian 中打开 |
| **统一输出目录** | B站 → `11-subtitles/bilibili/`，YouTube → `11-subtitles/Youtube/` |
| **Cookie 支持** | 自动读取 `BILI_COOKIE` 环境变量，下载需要登录的字幕 |
| **CSV 报告** | 每次下载自动生成带时间戳的 CSV 报告 |

---

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

### 交互模式（最常用）

```bash
python main.py download
```

进入交互模式，粘贴混合链接（空行结束）：

```
  > https://www.bilibili.com/video/BV1xx411c7mD
  > https://www.youtube.com/watch?v=dQw4w9WgXcQ
  > https://space.bilibili.com/123456/channel/collectiondetail?sid=789
  >
```

### 命令行直接传链接

```bash
python main.py download "https://www.bilibili.com/video/BV1xx411c7mD" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 指定语言和并发数

```bash
python main.py download --lang zh --max-concurrent 3
```

---

## 配置

修改 `config.py`：

```python
# 输出根目录
DEFAULT_OUTPUT_DIR = Path("E:/Obsidian/主仓库/11-subtitles")

# Obsidian Vault（用于生成可点击链接）
OBSIDIAN_VAULT_ROOT = Path("E:/Obsidian/主仓库")
OBSIDIAN_VAULT_NAME = "主仓库"
```

---

## Cookie 配置（B站字幕下载必需）

部分 B站视频的字幕需要登录才能获取。支持两种方式传入 Cookie：

### 方式一：环境变量（推荐，启动菜单自动注入）

```powershell
$env:BILI_COOKIE="你的SESSDATA值"
python main.py download
```

### 方式二：命令行参数

```bash
python main.py download --cookie "你的SESSDATA值"
```

**获取 SESSDATA 的方法**：
1. 用浏览器打开 `https://www.bilibili.com` 并登录
2. 按 `F12` → **Application / 应用** → **Cookies → https://www.bilibili.com**
3. 找到 `SESSDATA`，复制它的值

> ⚠️ **安全提示**：SESSDATA 相当于登录凭证，不要分享到公开仓库。

---

## 常见问题

**Q: B站视频显示"该视频暂无可用字幕"？**
A: 大概率是 Cookie 未设置。部分字幕（尤其是 AI 生成字幕）需要登录才能通过 API 获取。请按上方说明配置 SESSDATA。

**Q: YouTube 显示 IP 被封锁？**
A: YouTube 对请求频率敏感，暂停一段时间再试，或更换网络/IP。

**Q: 文件名点击后 Obsidian 提示"未找到文件"？**
A: 检查 `config.py` 中的 `OBSIDIAN_VAULT_ROOT` 和 `OBSIDIAN_VAULT_NAME` 是否与实际 Obsidian 仓库匹配。

**Q: 表格里的文件名没有下划线（不可点击）？**
A: 确保使用 **Windows Terminal**，且终端窗口足够宽。`Console(force_terminal=True)` 已强制启用超链接输出。

---

## 技术栈

- Python 3.10+
- Typer + Rich（终端 UI）
- B站 API + yt-dlp / youtube-transcript-api
- Pydantic v2

---

## 项目结构

```
video-sub-md/
├── main.py              # 统一 CLI 入口
├── config.py            # 全局配置
├── models.py            # 通用数据模型
├── requirements.txt
├── README.md
└── core/
    ├── bilibili/        # B站字幕下载引擎
    │   ├── extractor.py
    │   ├── metadata.py
    │   ├── downloader.py
    │   ├── formatter.py
    │   └── models.py
    └── youtube/         # YouTube 字幕下载引擎
        ├── extractor.py
        ├── metadata.py
        ├── downloader.py
        ├── formatter.py
        └── models.py
```

---

## 更新日志

### v0.1.0

- 支持 Bilibili + YouTube 混合链接输入
- 自动识别平台并分发到对应下载引擎
- 统一并发调度（B站线程池 + YouTube 异步）
- 下载结果表格支持 Ctrl+点击跳转 Obsidian
- URL 编码处理含空格文件名
- 支持 `BILI_COOKIE` 环境变量和 `--cookie` 参数
- `Console(force_terminal=True)` 确保 exe 启动菜单正常输出 OSC 8 超链接
