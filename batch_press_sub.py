#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量压制英文字幕到短剧视频中
规范：字号 18px，距离底部 20% (MarginV=58, Alignment=2)，硬件加速 h264_videotoolbox
"""

import os
import sys
import time
import shutil
import tempfile
import uuid
import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent
VIDEO_DIR = BASE_DIR / "The Male Slave is a Girl_ The Lion King's Fated Mate_40028"
SUB_DIR = BASE_DIR / "en"
OUT_DIR = BASE_DIR / "output" / "The Male Slave is a Girl_ The Lion King's Fated Mate_40028"

OUT_DIR.mkdir(parents=True, exist_ok=True)

def process_episode(video_file: Path):
    ep_name = video_file.stem # e.g. "01"
    sub_file = SUB_DIR / f"{ep_name}.vtt"
    
    if not sub_file.exists():
        return False, f"[{video_file.name}] 缺少对应字幕文件: {sub_file.name}"
    
    tmp_out = OUT_DIR / f"{video_file.name}.tmp.mp4"
    final_out = OUT_DIR / video_file.name
    
    clean_sub_dir = Path(tempfile.gettempdir()) / "press_sub_cache"
    clean_sub_dir.mkdir(parents=True, exist_ok=True)
    clean_ext = "".join(c for c in sub_file.suffix.lower() if c.isalnum()) or "srt"
    safe_sub = clean_sub_dir / f"sub_{uuid.uuid4().hex[:12]}.{clean_ext}"
    try:
        shutil.copyfile(sub_file, safe_sub)
    except Exception as e:
        return False, f"[{video_file.name}] 字幕预处理失败: {e}"

    safe_sub_arg = str(safe_sub.as_posix()).replace(":", r"\:").replace("'", r"\'")
    
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_file),
            "-vf", f"subtitles='{safe_sub_arg}':force_style='FontSize=18,Alignment=2,MarginV=58'",
            "-c:v", "h264_videotoolbox",
            "-b:v", "1200k",
            "-c:a", "copy",
            str(tmp_out)
        ]
        
        t0 = time.time()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        duration = time.time() - t0
        
        if res.returncode != 0:
            if tmp_out.exists():
                tmp_out.unlink()
            err_msg = res.stderr.decode('utf-8', errors='ignore')[-300:]
            return False, f"[{video_file.name}] 压制失败: {err_msg}"
        
        # 简单校验
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(tmp_out)
        ]
        probe = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            dur = float(probe.stdout.decode().strip())
            if dur <= 0:
                raise ValueError("Duration is 0")
        except Exception as e:
            if tmp_out.exists():
                tmp_out.unlink()
            return False, f"[{video_file.name}] 校验失败: {e}"
            
        tmp_out.replace(final_out)
        # 同步回原视频目录
        target_in_src = video_file.parent / video_file.name
        try:
            shutil.copy2(final_out, target_in_src)
        except Exception as e:
            print(f"Warning: failed to sync back to src dir: {e}")
            
        size_mb = final_out.stat().st_size / (1024 * 1024)
        return True, f"[{video_file.name}] 压制成功 ({duration:.1f}s, 大小 {size_mb:.1f}MB)"
    finally:
        if safe_sub.exists():
            try:
                safe_sub.unlink()
            except OSError:
                pass

def main():
    # 清理 output 目录下的历史测试文件
    for f in OUT_DIR.glob("01_*.mp4"):
        f.unlink(missing_ok=True)
        
    videos = sorted(list(VIDEO_DIR.glob("*.mp4")), key=lambda p: p.name)
    total = len(videos)
    print(f"找到待处理视频 {total} 个，开始批量压制 (并发数: 2)...")
    
    start_total = time.time()
    success_count = 0
    fail_count = 0
    
    # 使用 2 并发以防过多占用 VideoToolbox 会话
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(process_episode, v): v for v in videos}
        for future in as_completed(futures):
            ok, msg = future.result()
            if ok:
                success_count += 1
                print(f"✓ [{success_count + fail_count}/{total}] {msg}")
            else:
                fail_count += 1
                print(f"✗ [{success_count + fail_count}/{total}] {msg}")
                
    elapsed = time.time() - start_total
    print(f"\n全部处理完毕！总用时: {elapsed:.1f}秒 (成功: {success_count}, 失败: {fail_count})")

if __name__ == "__main__":
    main()
