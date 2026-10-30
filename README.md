# 短剧字幕批量压制工作台 (Video Subtitle Burning Tool)

一款专为短剧、分集视频批量烧录字幕设计的可视化 Web 工具，支持智能集数与字幕自动配对、跨平台硬件加速压制（Mac VideoToolbox / Windows NVENC / CPU libx264）、参数实时配置与在线成片预览。

![Web 工作台界面](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-green)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Hardware%20Accelerated-orange)

---

## 🌟 核心特性

- **📁 智能目录探测与配对**：
  - **根目录同放模式**：视频与字幕都在同一个根目录下，自动精准识别成对配对。
  - **分目录存放模式**：支持视频在子目录、字幕在 `en/` 或独立子目录的经典结构。
  - **多规则对齐**：支持完全同名匹配、语言前缀匹配（如 `01.mp4` 与 `01.en.srt`）、集数编号提取对齐（兼容 `EP01`、`第01集`、`Show_40028_01` 等）。
- **⚡ 极速硬件加速编码**：
  - **macOS**：Apple Silicon 原生 `h264_videotoolbox` 硬件加速，单集压制仅需几秒，极低功耗。
  - **Windows**：支持 NVIDIA 显卡 `h264_nvenc` 硬件加速。
  - **容错回退**：硬件加速失败时自动无缝降级至 `libx264` CPU 软解，压制 100% 成功率。
- **🎨 灵活字幕参数控制**：
  - 自定义字号大小（默认 18px）。
  - 自定义距底比例（默认 20%，避开移动端短剧底栏交互区域）。
  - 支持对齐方式选择（底部居中、正中等）。
  - 支持并发压制数控制（默认 2 并发）。
  - 支持压制完成后同步覆盖源视频或保留在 `output/`。
- **🖥️ 友好交互与监控**：
  - 本地文件系统弹窗选择（支持 macOS Finder 原生选择与 Windows PowerShell 窗口选择）。
  - 实时 SSE 进度流推送，每集状态徽章（待压制 / 压制中 / 已完成 / 失败）。
  - 实时终端运行日志查看。
  - 成片一键在线弹窗点播播放与 Finder / 文件管理器直达。

---

## 🚀 快速启动

### 前置要求
- **Python** 3.9 或更高版本。
- **FFmpeg**：确保系统安装了 `ffmpeg` 并已加入系统环境变量 PATH（Mac 上可通过 `brew install ffmpeg` 安装）。

### 🍎 macOS 用户
克隆项目后，在终端执行一键启动脚本：
```bash
git clone https://github.com/jqs0003/press_sub.git
cd press_sub
./run_web.sh
```
服务启动后将自动在默认浏览器中打开控制台：`http://127.0.0.1:8765`。

---

### 🪟 Windows 用户
1. 双击运行项目根目录下的 **`run_windows.bat`**：
   - 脚本会自动检测 Python 环境，创建专用 `venv_win` 虚拟环境；
   - 自动安装依赖包并打开默认浏览器访问控制台。
2. **FFmpeg 配置**：如系统未安装 FFmpeg，可下载 Windows 版 `ffmpeg.exe` 并直接放置在本项目根目录下即可自动识别。

---

## 📦 Windows EXE 独立打包

项目已配置好 PyInstaller 规范与 GitHub Actions 自动化打包：

### 方式 1：Windows 本机打包
在 Windows 电脑上双击运行 **`build_exe.bat`**，即可在 `dist/` 目录下生成独立的 `短剧字幕批量压制工具.exe`。

### 方式 2：GitHub Actions 自动云编译（Mac 用户适用）
无需 Windows 电脑，只需在 GitHub 仓库中进入 **Actions** -> 选择 **Build Windows EXE** -> 点击 **Run workflow**，云端 Windows 机器将自动编译生成包含 FFmpeg 的 `.zip` 压缩包供直接下载使用。

---

## 📂 项目结构

```text
├── app.py                      # Web 主程序入口
├── run_web.sh                  # macOS 一键启动脚本
├── run_windows.bat             # Windows 一键启动脚本
├── build_exe.bat               # Windows EXE 打包脚本
├── press_sub.spec              # PyInstaller 打包配置
├── requirements.txt            # Python 核心依赖
├── batch_press_sub.py          # 纯 CLI 备用批量压制脚本
├── web/
│   ├── app.py                  # FastAPI 后端服务与路由定义
│   ├── matcher.py              # 智能集数提取与字幕自动配对引擎
│   └── presser.py              # 并发压制调度管理与 FFmpeg 命令封装
├── static/
│   └── index.html              # 现代化响应式控制台前端页面
└── .github/workflows/
    └── build_windows_exe.yml   # Windows EXE 云端自动打包工作流
```

---

## 📄 License
MIT License.
