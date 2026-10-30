#!/bin/bash
# 一键打包 macOS 独立可执行程序
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "       macOS 独立可执行程序打包脚本 (PyInstaller)        "
echo "========================================================"
echo

# 1. 寻找 Python 环境
VENV_PYTHON="/Users/jqs/chaodian/video/venv/bin/python3"
if [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -f "$VIRTUAL_ENV/bin/python3" ]; then
    PYTHON_CMD="$VIRTUAL_ENV/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    echo "❌ 错误: 未检测到 Python 3 环境"
    exit 1
fi

echo "[1/3] 检查并安装打包依赖..."
"$PYTHON_CMD" -m pip install -q -r requirements.txt
"$PYTHON_CMD" -m pip install -q pyinstaller

echo "[2/3] 开始执行 PyInstaller 打包..."
"$PYTHON_CMD" -m PyInstaller press_sub.spec --clean -y

echo "[3/3] 整理可执行程序发布目录..."
mkdir -p "$SCRIPT_DIR/bin"
cp "$SCRIPT_DIR/dist/短剧字幕批量压制工具" "$SCRIPT_DIR/bin/短剧字幕批量压制工具"
chmod +x "$SCRIPT_DIR/bin/短剧字幕批量压制工具"

echo
echo "✅ 打包完成！"
echo "👉 可执行文件位于: $SCRIPT_DIR/bin/短剧字幕批量压制工具"
echo "💡 提示：双击该文件或运行 ./run_web.sh 即可直接启动，无需安装 Python 或任何依赖！"
