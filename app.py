#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
短剧字幕压制 Web 工具启动器 (app.py)
"""

import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))


def open_browser_later(url: str, delay: float = 1.0):
    """延迟在系统浏览器中自动打开控制台网址"""
    def _open():
        time.sleep(delay)
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", url])
            elif platform.system() == "Windows":
                os.startfile(url)
            else:
                subprocess.run(["xdg-open", url])
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description="短剧字幕批量压制 Web 工具")
    parser.add_argument("--host", default="127.0.0.1", help="绑定监听 Host (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="绑定端口 (默认 8765)")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("错误: 缺少 uvicorn 依赖。请确保在配备 fastapi/uvicorn 的 Python 虚拟环境中运行。")
        sys.exit(1)

    url = f"http://{args.host}:{args.port}"
    print("=" * 60)
    print(f"🎬 短剧字幕批量压制 Web 工作台正在启动...")
    print(f"🌐 本地访问地址: {url}")
    print(f"💡 按 Ctrl+C 可停止服务")
    print("=" * 60)

    if not args.no_browser:
        open_browser_later(url, delay=1.2)

    from web.app import app
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
