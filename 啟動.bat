@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [錯誤] 尚未安裝。請先執行「安裝.bat」。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m ndltd_spider.main
