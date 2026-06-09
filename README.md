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
| **CSV 报告** | 每次下载自动生成带时间戳的 CSV 报告 |

---

## 安装

```bash
pip install -r requirements.txt
```

## 使用

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
