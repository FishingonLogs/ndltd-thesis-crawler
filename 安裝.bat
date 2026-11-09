@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   NDLTD 博碩士論文爬蟲工具 - 安裝
echo ============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [錯誤] 找不到 Python。請先安裝 Python 3.11+ 並勾選 "Add Python to PATH"。
  echo 下載： https://www.python.org/downloads/
  pause
  exit /b 1
)

echo [1/3] 建立虛擬環境 .venv ...
py -m venv .venv
if errorlevel 1 ( echo [錯誤] 建立虛擬環境失敗 & pause & exit /b 1 )

echo [2/3] 安裝套件 ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo [錯誤] 套件安裝失敗 & pause & exit /b 1 )

echo [3/3] 下載瀏覽器核心 Chromium（約 150MB，請稍候）...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 ( echo [錯誤] 瀏覽器下載失敗 & pause & exit /b 1 )

echo.
echo ============================================
echo   安裝完成！請執行「啟動.bat」開啟程式。
echo ============================================
pause
