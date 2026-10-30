#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量压制任务管理器与执行调度器 (presser.py)
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger("presser")


class TaskManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self):
        self.is_running = False
        self.cancel_requested = False
        self.task_id = ""
        self.start_time = 0.0
        self.end_time = 0.0
        self.settings: Dict[str, Any] = {}
        self.items: List[Dict[str, Any]] = []
        self.logs: List[Dict[str, str]] = []
        self.max_logs = 1000
        self.subscribers: List[asyncio.Queue] = []
        self.thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()

    def get_status(self) -> Dict[str, Any]:
        with self._state_lock:
            total = len(self.items)
            completed = sum(1 for it in self.items if it.get("state") == "completed")
            failed = sum(1 for it in self.items if it.get("state") == "failed")
            processing = sum(1 for it in self.items if it.get("state") == "processing")
            
            elapsed = 0.0
            if self.is_running and self.start_time > 0:
                elapsed = time.time() - self.start_time
            elif self.end_time > self.start_time:
                elapsed = self.end_time - self.start_time

            pct = round((completed + failed) / total * 100, 1) if total > 0 else 0.0

            return {
                "task_id": self.task_id,
                "is_running": self.is_running,
                "cancel_requested": self.cancel_requested,
                "total": total,
                "completed": completed,
                "failed": failed,
                "processing": processing,
                "progress_pct": pct,
                "elapsed_sec": round(elapsed, 1),
                "items": self.items,
                "settings": self.settings,
                "log_count": len(self.logs)
            }

    def add_log(self, level: str, message: str):
        now_str = datetime.now().strftime("%H:%M:%S")
        entry = {"time": now_str, "level": level, "msg": message}
        with self._state_lock:
            self.logs.append(entry)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)
        self._notify_subscribers({"type": "log", "data": entry})

    def _notify_subscribers(self, payload: Dict[str, Any]):
        for q in list(self.subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                pass

    def add_subscriber(self, q: asyncio.Queue):
        self.subscribers.append(q)

    def remove_subscriber(self, q: asyncio.Queue):
        if q in self.subscribers:
            self.subscribers.remove(q)

    def stop_task(self):
        with self._state_lock:
            if self.is_running:
                self.cancel_requested = True
                self.add_log("WARN", "已收到停止请求，正在等待当前正在进行的集数结束...")

    def start_batch(self, items: List[Dict[str, Any]], settings: Dict[str, Any]) -> bool:
        with self._state_lock:
            if self.is_running:
                return False

            self.is_running = True
            self.cancel_requested = False
            self.task_id = f"task_{int(time.time())}"
            self.start_time = time.time()
            self.end_time = 0.0
            self.settings = settings
            self.logs.clear()
            
            # 初始化分集状态
            self.items = []
            for it in items:
                item_copy = dict(it)
                item_copy["state"] = "pending"
                item_copy["duration_sec"] = 0.0
                item_copy["error_msg"] = ""
                item_copy["output_size_mb"] = 0.0
                self.items.append(item_copy)

        self.add_log("INFO", f"启动批量压制任务 (共 {len(items)} 集, 并发: {settings.get('concurrency', 2)})")
        
        self.thread = threading.Thread(target=self._run_worker, daemon=True)
        self.thread.start()
        return True

    def _run_worker(self):
        settings = self.settings
        concurrency = int(settings.get("concurrency", 2))
        font_size = int(settings.get("font_size", 18))
        bottom_pct = float(settings.get("bottom_pct", 20.0))
        alignment = int(settings.get("alignment", 2))
        bitrate = settings.get("bitrate", "1200k")
        encoder = settings.get("encoder", "h264_videotoolbox")
        sync_overwrite = bool(settings.get("sync_overwrite", False))

        # 计算 ASS MarginV: 基于标准 ASS 288 高度
        margin_v = max(5, int(288 * (bottom_pct / 100.0)))
        force_style = f"FontSize={font_size},Alignment={alignment},MarginV={margin_v}"

        # 跨系统编码器自适应
        import platform
        if platform.system() != "Darwin" and encoder == "h264_videotoolbox":
            encoder = "h264_nvenc"  # Windows/Linux 优先尝试 NVENC，若无卡会自动回退 libx264

        self.add_log("INFO", f"字幕参数配置: 字号={font_size}px, 距底={bottom_pct}%, Alignment={alignment}, MarginV={margin_v}")
        self.add_log("INFO", f"编码器参数: {encoder}, 码率: {bitrate}, 同步覆盖原文件: {'是' if sync_overwrite else '否'}")

        # 过滤需要处理的项目
        target_items = [it for it in self.items if it.get("selected", True) and it.get("status") == "matched"]

        def process_one(item_dict: Dict[str, Any]):
            if self.cancel_requested:
                item_dict["state"] = "canceled"
                return

            v_path = Path(item_dict["video_path"])
            s_path = Path(item_dict["sub_path"])
            out_path = Path(item_dict["output_path"])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            
            tmp_out = out_path.parent / f"{out_path.name}.tmp.mp4"

            # 准备安全字幕临时文件（避免父路径中单引号、空格或特殊字符破坏 ffmpeg -vf 解析语法）
            clean_sub_dir = Path(tempfile.gettempdir()) / "press_sub_cache"
            clean_sub_dir.mkdir(parents=True, exist_ok=True)
            safe_sub = clean_sub_dir / f"sub_{uuid.uuid4().hex[:12]}{s_path.suffix.lower()}"
            try:
                shutil.copyfile(s_path, safe_sub)
            except Exception as e:
                with self._state_lock:
                    item_dict["state"] = "failed"
                    item_dict["error_msg"] = f"字幕预处理失败: {e}"
                self.add_log("ERROR", f"[{v_path.name}] 字幕预处理失败: {e}")
                self._notify_subscribers({"type": "progress", "data": self.get_status()})
                return

            with self._state_lock:
                item_dict["state"] = "processing"
            self._notify_subscribers({"type": "progress", "data": self.get_status()})
            self.add_log("INFO", f"开始压制: {v_path.name} -> {out_path.name}")

            try:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(v_path),
                    "-vf", f"subtitles='{safe_sub}':force_style='{force_style}'",
                    "-c:v", encoder,
                    "-b:v", bitrate,
                    "-c:a", "copy",
                    str(tmp_out)
                ]

                t0 = time.time()
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                dur_sec = round(time.time() - t0, 1)

                # 若硬件加速失败，自动尝试 libx264 兜底
                if res.returncode != 0 and encoder != "libx264":
                    self.add_log("WARN", f"[{v_path.name}] 硬件加速({encoder})失败，尝试切换 libx264 兜底...")
                    cmd[cmd.index("-c:v") + 1] = "libx264"
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if res.returncode != 0:
                    if tmp_out.exists():
                        tmp_out.unlink()
                    err_text = res.stderr.decode("utf-8", errors="ignore")[-200:].strip()
                    with self._state_lock:
                        item_dict["state"] = "failed"
                        item_dict["error_msg"] = err_text
                    self.add_log("ERROR", f"[{v_path.name}] 压制失败: {err_text}")
                    self._notify_subscribers({"type": "progress", "data": self.get_status()})
                    return

                # 校验输出
                probe_cmd = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(tmp_out)
                ]
                probe = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    out_dur = float(probe.stdout.decode().strip())
                    if out_dur <= 0:
                        raise ValueError("输出时长为0")
                except Exception as e:
                    if tmp_out.exists():
                        tmp_out.unlink()
                    with self._state_lock:
                        item_dict["state"] = "failed"
                        item_dict["error_msg"] = f"文件完整性校验失败: {e}"
                    self.add_log("ERROR", f"[{v_path.name}] 校验失败: {e}")
                    self._notify_subscribers({"type": "progress", "data": self.get_status()})
                    return

                # 成功替换
                tmp_out.replace(out_path)
                size_mb = round(out_path.stat().st_size / (1024 * 1024), 1)

                # 同步覆盖源文件
                if sync_overwrite and out_path != v_path:
                    try:
                        shutil.copy2(out_path, v_path)
                    except Exception as e:
                        self.add_log("WARN", f"[{v_path.name}] 同步覆盖源文件失败: {e}")

                with self._state_lock:
                    item_dict["state"] = "completed"
                    item_dict["duration_sec"] = dur_sec
                    item_dict["output_size_mb"] = size_mb

                self.add_log("INFO", f"✓ [{v_path.name}] 压制完成 (耗时 {dur_sec}s, 大小 {size_mb}MB)")
                self._notify_subscribers({"type": "progress", "data": self.get_status()})

            finally:
                if safe_sub.exists():
                    try:
                        safe_sub.unlink()
                    except OSError:
                        pass

        # 使用线程池并发调度
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(process_one, it) for it in target_items]
            for f in futures:
                f.result()

        with self._state_lock:
            self.is_running = False
            self.end_time = time.time()
            total_elapsed = round(self.end_time - self.start_time, 1)

        status = self.get_status()
        self.add_log("INFO", f"全部任务结束！总用时: {total_elapsed}秒 (成功: {status['completed']}, 失败: {status['failed']})")
        self._notify_subscribers({"type": "finish", "data": status})
