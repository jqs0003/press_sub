@echo off
chcp 65001 >nul
title 短剧字幕批量压制工具 - Windows 控制台
echo ========================================================
echo          短剧字幕批量压制工具 (Windows版)
echo ========================================================
echo.

cd /d "%~dp0"

:: 1. 检查是否存在独立打包的 EXE 程序（零依赖、开箱即用）
if exist "%~dp0bin\短剧字幕批量压制工具.exe" (
    echo [OK] 检测到独立可执行程序: bin\短剧字幕批量压制工具.exe
    start "" "%~dp0bin\短剧字幕批量压制工具.exe" %*
    exit /b 0
)

if exist "%~dp0dist\短剧字幕批量压制工具.exe" (
    echo [OK] 检测到独立可执行程序: dist\短剧字幕批量压制工具.exe
    start "" "%~dp0dist\短剧字幕批量压制工具.exe" %*
    exit /b 0
)

:: 2. 检查当前目录是否存在 ffmpeg.exe，若有则加入临时 PATH
if exist "%~dp0ffmpeg.exe" (
    echo [OK] 检测到当前目录下的 ffmpeg.exe，已加入运行路径。
    set "PATH=%~dp0;%PATH%"
) else (
    where ffmpeg >nul 2>nul
    if %errorlevel% neq 0 (
        echo [提示] 系统未检测到 ffmpeg 命令！
        echo 建议下载 Windows 版 ffmpeg.exe 并直接放入本程序根目录：
        echo 下载地址: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
        echo.
    )
)

:: 3. 检查 Python 环境
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到独立 EXE 程序，亦未检测到 Python 环境！
    echo 请先安装 Python 3.9+ 并务必勾选 "Add python.exe to PATH"
    echo 官方下载: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: 4. 检查或创建虚拟环境
if not exist "venv_win" (
    echo [1/3] 正在初始化 Python 虚拟环境 (venv_win)...
    python -m venv venv_win
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败，尝试使用全局 Python 运行...
        goto run_direct
    )
)

call venv_win\Scripts\activate.bat

:: 5. 安装/检查依赖
if not exist "venv_win\.installed" (
    echo [2/3] 首次启动，正在安装 Web 依赖包 (fastapi, uvicorn)...
    python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% equ 0 (
        echo ok > "venv_win\.installed"
    )
)

:start_server
echo [3/3] 正在启动 Web 控制台...
echo 访问地址: http://127.0.0.1:8765
echo.
python app.py --port 8765
goto end

:run_direct
python -m pip install -r requirements.txt
python app.py --port 8765

:end
pause
