@echo off
chcp 65001 >nul
title 打包 Windows EXE - 短剧字幕压制工具
echo ========================================================
echo          Windows EXE 一键打包脚本 (PyInstaller)
echo ========================================================
echo.

cd /d "%~dp0"

:: 检查 Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 请先在 Windows 上安装 Python 3.9+ 并加入系统 PATH！
    pause
    exit /b 1
)

echo [1/3] 正在安装打包依赖 (pyinstaller, requirements)...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo [2/3] 开始执行 PyInstaller 打包...
pyinstaller press_sub.spec --clean -y

if %errorlevel% neq 0 (
    echo [错误] 打包失败，请检查上方日志。
    pause
    exit /b 1
)

echo.
echo [3/3] 打包完成！
echo 生成的 EXE 位于: dist\短剧字幕批量压制工具.exe
echo.
echo 提示：运行 EXE 时请确保电脑已安装 ffmpeg（或将 ffmpeg.exe 复制到与该 EXE 同级目录下）。
pause
