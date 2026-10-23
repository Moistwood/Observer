@echo off
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
  echo [错误] 没找到 Python。请先安装 3.9 或更高版本：
  echo   https://www.python.org/downloads/
  echo 安装时记得勾选 "Add Python to PATH"
  pause
  exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
if errorlevel 1 (
  echo [错误] Python 版本太低，需要 3.9 以上
  %PY% --version
  pause
  exit /b 1
)

%PY% -c "import fastapi, uvicorn, webview" >nul 2>nul
if errorlevel 1 (
  echo 第一次运行，正在安装依赖...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [错误] 依赖安装失败，检查网络后重试
    pause
    exit /b 1
  )
)

%PY% app.py
if errorlevel 1 pause
