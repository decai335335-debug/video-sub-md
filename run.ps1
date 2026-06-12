# 强制使用 config.py 中的 DEFAULT_SESSDATA，忽略外部 BILI_COOKIE 环境变量
$env:BILI_COOKIE = ""

# 进入脚本所在目录
Set-Location $PSScriptRoot

# 启动交互式下载
python main.py download
