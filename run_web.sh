#!/bin/bash
# 一键启动短剧字幕批量压制 Web 工作台
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 优先探测项目专属虚拟环境
VENV_PYTHON="/Users/jqs/chaodian/video/venv/bin/python3"

if [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -f "$VIRTUAL_ENV/bin/python3" ]; then
    PYTHON_CMD="$VIRTUAL_ENV/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    echo "❌ 错误: 未找到可用的 Python 3 环境"
    exit 1
fi

echo "🚀 使用 Python: $PYTHON_CMD"
exec "$PYTHON_CMD" "$SCRIPT_DIR/app.py" "$@"
