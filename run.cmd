@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "BILI_COOKIE="
cd /d "%~dp0"
python main.py download
