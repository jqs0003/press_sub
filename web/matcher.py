#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能集数与字幕自动配对引擎 (matcher.py)
支持视频与字幕同目录（根目录同放）、各自分目录、子母目录等各种结构。
"""

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".ts", ".m4v", ".webm", ".avi", ".flv"}
SUB_EXTS = {".vtt", ".srt", ".ass", ".ssa"}

# 常见字幕目录候选名
SUB_FOLDER_CANDIDATES = [
    "en", "eng", "subtitles", "subtitle", "subs", "sub",
    "zh", "zho", "cn", "chs", "es", "spa", "id", "ind"
]


def extract_episode_num(name_or_path: str) -> Optional[int]:
    """
    智能提取集数编号。
    1. 优先匹配结尾明确的集数，如 _01, -01, .01 (如 The_Lion_King_01.mp4, 01.en.srt)
    2. 匹配带明确前缀的集数，如 EP01, Ep_01, Episode 01, 第01集, S01E05
       (需考虑单词边界，避免将 Mate_40028 中的 e 误当作 ep 标记)
    3. 模式提取数字块，优先取末尾符合常规集数区间 (1~500) 的数字
    """
    stem = Path(name_or_path).stem.strip()
    
    # 模式 1: 结尾明确的集数，如 _01, -01, .01 (最稳妥)
    m = re.search(r"[_-]\s*(\d+)(?:\.[a-zA-Z]{2,4})?$", stem)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 500:
            return num

    # 模式 2: S01E05 或 EP05, EP_05, Episode 05, 第05集
    # 必须有单词边界或非字母前缀，避免与单词结尾字母混淆
    m = re.search(r"(?:S\d+)?(?:\b|(?<=[^a-zA-Z]))(?:ep|episode|第)\s*[-_]?\s*(\d+)", stem, re.IGNORECASE)
    if m:
        return int(m.group(1))

    m = re.search(r"(?:S\d+)?(?:\b|(?<=[^a-zA-Z]))e\s*[-_]?\s*(\d+)", stem, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # 模式 3: 提取所有数字块
    nums = re.findall(r"\d+", stem)
    if nums:
        if len(nums) == 1:
            return int(nums[0])
        # 多组数字时，优先看末尾数字（一般剧集标号在末尾，如 Drama_40028_01）
        last_num = int(nums[-1])
        if 1 <= last_num <= 500:
            return last_num
        for n in reversed(nums):
            val = int(n)
            if 1 <= val <= 500:
                return val
        return int(nums[-1])
        
    return None


def scan_media_files(folder: Path, extensions: set) -> List[Path]:
    """
    扫描指定目录下满足扩展名的文件。
    排除 macOS 隐藏文件（如 ._01.mp4）与临时处理文件（*.tmp.mp4）。
    """
    if not folder.exists() or not folder.is_dir():
        return []
    
    files = []
    try:
        for entry in folder.iterdir():
            if (entry.is_file() 
                and not entry.name.startswith(".") 
                and not entry.name.endswith(".tmp.mp4")
                and entry.suffix.lower() in extensions):
                files.append(entry)
    except PermissionError:
        pass
        
    # 按提取的集数或文件名排序
    files.sort(key=lambda p: (extract_episode_num(p.name) or 999999, p.name))
    return files


def auto_detect_drama_structure(root_dir: Path) -> Dict[str, Any]:
    """
    智能探测短剧目录结构。
    支持：
    1. 根目录同放模式：root_dir 本身就直接包含 .mp4 视频与 .srt/.vtt 字幕
    2. 根目录视频 + 字幕子目录：root_dir 含视频，字幕在 en/ 等子目录
    3. 子目录各自存放模式：视频在 Drama_Name/，字幕在 en/
    4. 子目录内部同放模式：视频与字幕都在某个子目录内部
    """
    if not root_dir.exists() or not root_dir.is_dir():
        return {"video_dir": None, "sub_dir": None, "output_dir": None, "drama_name": ""}
    
    root_videos = scan_media_files(root_dir, VIDEO_EXTS)
    root_subs = scan_media_files(root_dir, SUB_EXTS)
    
    candidate_video_dir: Optional[Path] = None
    candidate_sub_dir: Optional[Path] = None
    drama_name = root_dir.name
    
    # 1. 确定视频目录
    if len(root_videos) > 0:
        candidate_video_dir = root_dir
    else:
        # 扫描子目录，寻找包含视频数量最多的子文件夹
        max_videos = 0
        for sub in root_dir.iterdir():
            if sub.is_dir() and not sub.name.startswith(".") and sub.name != "output":
                v_count = len(scan_media_files(sub, VIDEO_EXTS))
                if v_count > max_videos:
                    max_videos = v_count
                    candidate_video_dir = sub
                    drama_name = sub.name

    # 2. 确定字幕目录
    # 规则 2.1: 若视频目录本身就直接包含字幕文件 (视频与字幕同在根目录，或同在子目录)
    if candidate_video_dir:
        vdir_subs = scan_media_files(candidate_video_dir, SUB_EXTS)
        if len(vdir_subs) > 0:
            candidate_sub_dir = candidate_video_dir

    # 规则 2.2: 若 root_dir 本身直接包含字幕文件
    if not candidate_sub_dir and len(root_subs) > 0:
        candidate_sub_dir = root_dir

    # 规则 2.3: 在 candidate_video_dir 或 root_dir 下查找常见命名字幕子目录 (en, subtitles, etc.)
    if not candidate_sub_dir:
        search_bases = []
        if candidate_video_dir and candidate_video_dir not in search_bases:
            search_bases.append(candidate_video_dir)
        if root_dir not in search_bases:
            search_bases.append(root_dir)
            
        for base in search_bases:
            # 常见候选名
            for name in SUB_FOLDER_CANDIDATES:
                p = base / name
                if p.exists() and p.is_dir():
                    s_count = len(scan_media_files(p, SUB_EXTS))
                    if s_count > 0:
                        candidate_sub_dir = p
                        break
            if candidate_sub_dir:
                break
                
            # 其它任意包含字幕的子目录
            for sub in base.iterdir():
                if sub.is_dir() and sub != candidate_video_dir and not sub.name.startswith(".") and sub.name != "output":
                    s_count = len(scan_media_files(sub, SUB_EXTS))
                    if s_count > 0:
                        candidate_sub_dir = sub
                        break
            if candidate_sub_dir:
                break

    # 3. 确定默认输出目录
    out_dir = root_dir / "output"
    if candidate_video_dir and candidate_video_dir != root_dir:
        out_dir = out_dir / candidate_video_dir.name

    return {
        "video_dir": str(candidate_video_dir) if candidate_video_dir else None,
        "sub_dir": str(candidate_sub_dir) if candidate_sub_dir else None,
        "output_dir": str(out_dir),
        "drama_name": drama_name
    }


def match_episodes(video_dir_str: str, sub_dir_str: str, output_dir_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    匹配视频目录与字幕目录下的分集。
    无论视频与字幕是在同一目录还是不同目录，均能进行精准配对。
    """
    video_dir = Path(video_dir_str)
    sub_dir = Path(sub_dir_str)
    
    if output_dir_str:
        output_dir = Path(output_dir_str)
    elif video_dir == sub_dir:
        output_dir = video_dir / "output"
    else:
        output_dir = video_dir.parent / "output" / video_dir.name
    
    videos = scan_media_files(video_dir, VIDEO_EXTS)
    subtitles = scan_media_files(sub_dir, SUB_EXTS)
    
    # 建立多维度字幕索引
    sub_exact: Dict[str, Path] = {}      # 主文件名完全一致 (stem.lower -> Path)
    sub_by_ep: Dict[int, List[Path]] = {} # 集数 -> List[Path]
    
    for s in subtitles:
        stem_lower = s.stem.lower()
        sub_exact[stem_lower] = s
        ep = extract_episode_num(s.name)
        if ep is not None:
            sub_by_ep.setdefault(ep, []).append(s)
            
    matched_results: List[Dict[str, Any]] = []
    used_subs = set()
    
    for v in videos:
        ep = extract_episode_num(v.name)
        v_stem_lower = v.stem.lower()
        matched_sub = None
        
        # 优先级 1: 主文件名完全匹配 (仅扩展名不同，如 01.mp4 与 01.srt, Episode_01.mp4 与 Episode_01.vtt)
        if v_stem_lower in sub_exact and sub_exact[v_stem_lower] not in used_subs:
            matched_sub = sub_exact[v_stem_lower]
            
        # 优先级 2: 字幕名包含完整视频主文件名 (如 01.mp4 与 01.en.srt, 01_en.vtt)
        if not matched_sub:
            candidates = [
                s for s in subtitles 
                if s not in used_subs and (
                    s.stem.lower().startswith(v_stem_lower + ".") or 
                    s.stem.lower().startswith(v_stem_lower + "_") or 
                    s.stem.lower().startswith(v_stem_lower + "-")
                )
            ]
            if candidates:
                # 优先选用带 en 标记的字幕，其次按名字最短排序
                candidates.sort(key=lambda s: (0 if any(k in s.name.lower() for k in [".en", "_en", "-en"]) else 1, len(s.name)))
                matched_sub = candidates[0]
                
        # 优先级 3: 按提取到的集数匹配
        if not matched_sub and ep is not None and ep in sub_by_ep:
            avail = [s for s in sub_by_ep[ep] if s not in used_subs]
            if avail:
                avail.sort(key=lambda s: (0 if any(k in s.name.lower() for k in [".en", "_en", "-en"]) else 1, len(s.name)))
                matched_sub = avail[0]
            
        out_path = output_dir / v.name
        
        if matched_sub:
            used_subs.add(matched_sub)
            matched_results.append({
                "episode": ep if ep is not None else 0,
                "video_name": v.name,
                "video_path": str(v),
                "video_size_mb": round(v.stat().st_size / (1024 * 1024), 2),
                "sub_name": matched_sub.name,
                "sub_path": str(matched_sub),
                "status": "matched",
                "output_name": v.name,
                "output_path": str(out_path),
                "selected": True
            })
        else:
            matched_results.append({
                "episode": ep if ep is not None else 0,
                "video_name": v.name,
                "video_path": str(v),
                "video_size_mb": round(v.stat().st_size / (1024 * 1024), 2),
                "sub_name": "",
                "sub_path": "",
                "status": "missing_sub",
                "output_name": v.name,
                "output_path": str(out_path),
                "selected": False
            })
            
    # 排序：集数正序
    matched_results.sort(key=lambda item: (item["episode"] if item["episode"] > 0 else 999999, item["video_name"]))
    return matched_results
