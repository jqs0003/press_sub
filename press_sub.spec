# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil

block_cipher = None

# 自动发现并全量打包系统内置的 ffmpeg 与 ffprobe（连同其所有依赖动态库 dylib）
# 确保拷贝到任何全新 Mac（无需安装 Homebrew / ffmpeg）都能直接压制运行
extra_binaries = []
ffmpeg_path = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
ffprobe_path = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

if Path(ffmpeg_path).is_file():
    extra_binaries.append((ffmpeg_path, '.'))
if Path(ffprobe_path).is_file():
    extra_binaries.append((ffprobe_path, '.'))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=extra_binaries,
    datas=[
        ('static', 'static'),
        ('web', 'web'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='短剧字幕批量压制工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
