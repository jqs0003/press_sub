#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
短剧字幕压制 Web API 服务端 (app.py)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 导入业务模块
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    CURRENT_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = CURRENT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.matcher import auto_detect_drama_structure, match_episodes
from web.presser import TaskManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("web_app")

app = FastAPI(title="Video Subtitle Presser Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

task_manager = TaskManager()


class ScanRequest(BaseModel):
    root_dir: Optional[str] = None
    video_dir: Optional[str] = None
    sub_dir: Optional[str] = None
    output_dir: Optional[str] = None


class StartRequest(BaseModel):
    items: List[Dict[str, Any]]
    settings: Dict[str, Any]


class OpenFolderRequest(BaseModel):
    path: str


class ChooseFolderRequest(BaseModel):
    initial_dir: Optional[str] = None


@app.post("/api/choose-folder-native")
async def choose_folder_native(req: ChooseFolderRequest):
    """调起操作系统原生选择文件夹对话框 (macOS AppleScript)"""
    init_path = req.initial_dir
    if not init_path or not os.path.isdir(init_path):
        user_home = Path.home()
        init_path = str(user_home / "Movies") if (user_home / "Movies").exists() else str(user_home)

    clean_init = str(init_path).replace('\\', '\\\\').replace('"', '\\"')

    if platform.system() == "Darwin":
        # AppleScript 原生选择文件夹
        # 严格检查 -128 (用户点击取消)，避免取消时被内部捕获误触发第二次弹窗
        osa_script = f'''
        try
            set defaultFolder to POSIX file "{clean_init}"
            set chosenFolder to choose folder with prompt "请选择短剧或字幕文件夹:" default location defaultFolder
            return POSIX path of chosenFolder
        on error errMsg number errNum
            if errNum is -128 then
                return "CANCEL"
            end if
            try
                set chosenFolder to choose folder with prompt "请选择短剧或字幕文件夹:"
                return POSIX path of chosenFolder
            on error
                return "CANCEL"
            end try
        end try
        '''
        try:
            res = subprocess.run(["osascript", "-e", osa_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            out = res.stdout.strip()
            # 移除结尾的斜杠
            if out.endswith("/"):
                out = out[:-1]
            if out and out != "CANCEL" and os.path.isdir(out):
                return {"canceled": False, "path": out}
            return {"canceled": True, "path": ""}
        except Exception as e:
            logger.warning(f"Native folder picker failed: {e}")
            return {"canceled": False, "unsupported": True, "error": str(e), "path": ""}
    elif platform.system() == "Windows":
        # Windows PowerShell 调起原生选择文件夹对话框
        ps_clean_init = clean_init.replace("'", "''")
        ps_cmd = f'''
        Add-Type -AssemblyName System.Windows.Forms
        $f = New-Object System.Windows.Forms.FolderBrowserDialog
        $f.Description = "请选择短剧或字幕文件夹"
        if ("{ps_clean_init}" -ne "" -and (Test-Path "{ps_clean_init}")) {{
            $f.SelectedPath = "{ps_clean_init}"
        }}
        if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
            Write-Output $f.SelectedPath
        }} else {{
            Write-Output "CANCEL"
        }}
        '''
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            out = res.stdout.strip()
            if out and out != "CANCEL" and os.path.isdir(out):
                return {"canceled": False, "path": out}
            return {"canceled": True, "path": ""}
        except Exception as e:
            logger.warning(f"Windows native folder picker failed: {e}")
            return {"canceled": False, "unsupported": True, "error": str(e), "path": ""}
    else:
        return {"canceled": False, "unsupported": True, "path": ""}


@app.get("/api/browse")
async def browse_folder(path: Optional[str] = Query(None)):
    """浏览本地目录，支持面包屑与快捷路径"""
    import urllib.parse
    target = None
    if path:
        # 解码并去除两端空格
        p_str = urllib.parse.unquote(path).strip()
        candidate = Path(p_str).resolve()
        if candidate.exists() and candidate.is_dir():
            target = candidate
        elif Path(path).exists() and Path(path).is_dir():
            target = Path(path).resolve()

    if not target or not target.exists() or not target.is_dir():
        if getattr(sys, "frozen", False):
            target = Path.cwd() if Path.cwd().exists() else Path.home()
        else:
            target = PROJECT_ROOT

    parent = str(target.parent) if target.parent != target else None
    
    sub_dirs = []
    try:
        for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir() and not entry.name.startswith("."):
                sub_dirs.append({
                    "name": entry.name,
                    "path": str(entry.resolve())
                })
    except (PermissionError, OSError):
        pass

    # 构建面包屑层级
    breadcrumbs = []
    curr = target
    while True:
        breadcrumbs.append({"name": curr.name or "/", "path": str(curr)})
        if curr.parent == curr:
            break
        curr = curr.parent
    breadcrumbs.reverse()

    # 系统常用快捷路径
    root_shortcut = Path.cwd() if getattr(sys, "frozen", False) else PROJECT_ROOT
    shortcuts = [
        {"name": "当前目录", "path": str(root_shortcut)},
        {"name": "用户主目录", "path": str(Path.home())},
        {"name": "影片", "path": str(Path.home() / "Movies")},
        {"name": "桌面", "path": str(Path.home() / "Desktop")},
        {"name": "下载", "path": str(Path.home() / "Downloads")},
    ]
    valid_shortcuts = [s for s in shortcuts if Path(s["path"]).exists()]

    return {
        "current": str(target),
        "parent": parent,
        "breadcrumbs": breadcrumbs,
        "shortcuts": valid_shortcuts,
        "dirs": sub_dirs,
        "is_root": target.parent == target
    }


@app.post("/api/scan")
async def scan_directories(req: ScanRequest):
    """扫描并自动匹配视频与字幕"""
    video_dir = req.video_dir
    sub_dir = req.sub_dir
    output_dir = req.output_dir
    drama_name = ""

    # 若指定了 root_dir 且未完全指定子目录，则自动探测
    if req.root_dir:
        root_path = Path(req.root_dir).resolve()
        # 若传入的 video_dir / sub_dir 不在当前 root_path 内部，视为旧会话残留并重新探测
        if video_dir and not str(Path(video_dir).resolve()).startswith(str(root_path)):
            video_dir = None
        if sub_dir and not str(Path(sub_dir).resolve()).startswith(str(root_path)):
            sub_dir = None

        if not video_dir or not sub_dir:
            detect_res = auto_detect_drama_structure(root_path)
            if not video_dir and detect_res.get("video_dir"):
                video_dir = detect_res["video_dir"]
            if not sub_dir and detect_res.get("sub_dir"):
                sub_dir = detect_res["sub_dir"]
            if not output_dir and detect_res.get("output_dir"):
                output_dir = detect_res["output_dir"]
            drama_name = detect_res.get("drama_name", "")

    # 兜底：若指定了 video_dir 但未指定 sub_dir，自动探测 video_dir 是否直接包含字幕
    if video_dir and not sub_dir:
        v_path = Path(video_dir).resolve()
        detect_res = auto_detect_drama_structure(v_path)
        if detect_res.get("sub_dir"):
            sub_dir = detect_res["sub_dir"]

    if not video_dir or not Path(video_dir).exists():
        raise HTTPException(status_code=400, detail="未找到有效的视频目录，请检查路径或确认目录下包含视频文件")
    if not sub_dir or not Path(sub_dir).exists():
        raise HTTPException(status_code=400, detail="未找到有效的字幕目录，请检查路径或确认目录下包含 .vtt/.srt 字幕文件")

    if not output_dir:
        if video_dir == sub_dir:
            output_dir = str(Path(video_dir) / "output")
        else:
            output_dir = str(Path(video_dir).parent / "output" / Path(video_dir).name)

    items = match_episodes(video_dir, sub_dir, output_dir)
    
    matched_count = sum(1 for it in items if it.get("status") == "matched")
    missing_count = sum(1 for it in items if it.get("status") == "missing_sub")

    return {
        "video_dir": str(Path(video_dir).resolve()),
        "sub_dir": str(Path(sub_dir).resolve()),
        "output_dir": str(Path(output_dir).resolve()),
        "drama_name": drama_name or Path(video_dir).name,
        "total": len(items),
        "matched": matched_count,
        "missing": missing_count,
        "items": items
    }


@app.post("/api/start")
async def start_task(req: StartRequest):
    """启动批量压制"""
    if task_manager.is_running:
        raise HTTPException(status_code=400, detail="已有压制任务正在运行中")
    
    if not req.items:
        raise HTTPException(status_code=400, detail="请至少选择一个待压制集数")

    ok = task_manager.start_batch(req.items, req.settings)
    if not ok:
        raise HTTPException(status_code=400, detail="启动任务失败")
    
    return {"message": "任务已成功启动", "task_id": task_manager.task_id}


@app.post("/api/stop")
async def stop_task():
    """终止压制任务"""
    task_manager.stop_task()
    return {"message": "已下发终止请求"}


@app.get("/api/status")
async def get_task_status():
    """获取当前任务状态与历史日志"""
    status = task_manager.get_status()
    with task_manager._state_lock:
        logs_slice = list(task_manager.logs[-100:])
    return {"status": status, "logs": logs_slice}


@app.get("/api/events")
async def sse_events(request: Request):
    """SSE 实时推送进度与日志流"""
    q: asyncio.Queue = asyncio.Queue()
    task_manager.add_subscriber(q)

    async def event_generator():
        try:
            # 建立连接时先推送一次当前完整状态
            init_payload = {"type": "progress", "data": task_manager.get_status()}
            yield f"data: {json.dumps(init_payload, ensure_ascii=False)}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=2.0)
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 心跳保持
                    yield ": ping\n\n"
        finally:
            task_manager.remove_subscriber(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/open-folder")
async def open_folder(req: OpenFolderRequest):
    """在系统的 Finder 或文件管理器中打开文件夹"""
    target = Path(req.path).resolve()
    if not target.exists():
        # 如果是文件，尝试打开其父目录
        target = target.parent
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"目录不存在: {req.path}")

    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", str(target)], check=True)
        elif platform.system() == "Windows":
            os.startfile(str(target))
        else:
            subprocess.run(["xdg-open", str(target)], check=True)
        return {"message": f"已在系统管理器中打开: {target}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开文件夹失败: {e}")


@app.get("/api/preview-video")
async def preview_video(path: str = Query(...)):
    """支持 Range 请求的本地视频在线播放串流"""
    p = Path(path).resolve()
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="视频文件不存在")
    return FileResponse(p, media_type="video/mp4")


# 静态文件挂载
STATIC_DIR = PROJECT_ROOT / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
