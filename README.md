# 短剧字幕批量压制工作台 (Video Subtitle Burning Tool)

一款专为短剧、分集视频批量烧录字幕设计的可视化 Web 工具，支持智能集数与字幕自动配对、跨平台硬件加速压制（Mac VideoToolbox / Windows NVENC / CPU libx264）、参数实时配置与在线成片预览。

![Web 工作台界面](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-green)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Hardware%20Accelerated-orange)
![Standalone](https://img.shields.io/badge/Standalone-Zero%20Dependency-brightgreen)

---

## 🌟 核心特性

- **🚀 零依赖开箱即用**：
  - 内置独立可执行程序（打包了完整 Python 运行时与 FastAPI 服务），无需安装 Python、pip 或任何额外依赖库，双击即用。
  - 底层 FFmpeg 智能自动检索（支持程序同级目录、嵌入环境以及系统 PATH 自动识别）。
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

## 🚀 快速启动（开箱即用）

### 🍎 macOS 用户（两种方式，任选其一）

#### 方式 1：一键脚本（自动优先运行已打包的独立程序）
```bash
git clone https://github.com/jqs0003/press_sub.git
cd press_sub
./run_web.sh
```

#### 方式 2：直接双击运行独立程序
直接双击项目中的 `bin/短剧字幕批量压制工具` 即可直接启动，系统将自动在默认浏览器中打开控制台：`http://127.0.0.1:8765`。
> 💡 完全不需要安装 Python 或执行 pip install！

---

### 🪟 Windows 用户
1. 双击运行项目根目录下的 **`run_windows.bat`**：
   - 若检测到 `bin\短剧字幕批量压制工具.exe`，将直接秒开独立程序；
   - 否则会自动配置 Python 虚拟环境并启动。
2. **FFmpeg 配置**：如系统未安装 FFmpeg，可下载 Windows 版 `ffmpeg.exe` 并直接放置在本项目根目录下，程序会自动加载识别。

---

## 📦 独立可执行程序打包构建

项目提供全套一键打包脚本与 GitHub Actions 云编译工作流：

### 1. macOS 本地一键打包
```bash
./build_macos.sh
```
打包生成的可执行程序将自动整理到 `bin/短剧字幕批量压制工具`。

### 2. Windows 本地一键打包
在 Windows 电脑上双击运行 **`build_exe.bat`**，即可自动生成 `bin\短剧字幕批量压制工具.exe`。

### 3. GitHub Actions 自动云端编译（多端 Release）
在 GitHub 仓库页面进入 **Actions** -> 选择 **Build Standalone Executables (Windows & macOS)** -> 点击 **Run workflow**，即可免费云端编译并下载 Windows (`.exe` 带 FFmpeg 打包) 与 macOS 架构的免安装便携版。

---

## 📂 项目结构

```text
├── app.py                      # Web 主程序入口
├── run_web.sh                  # macOS 一键启动脚本（优先使用独立程序）
├── run_windows.bat             # Windows 一键启动脚本（优先使用独立程序）
├── build_macos.sh              # macOS 独立程序一键打包脚本
├── build_exe.bat               # Windows EXE 一键打包脚本
├── press_sub.spec              # PyInstaller 多端打包规范配置
├── requirements.txt            # Python 核心依赖（仅源码运行/打包时需要）
├── batch_press_sub.py          # 纯 CLI 备用批量压制脚本
├── bin/                        # 开箱即用独立可执行程序目录
│   └── 短剧字幕批量压制工具      # macOS 独立可执行程序（免 Python 环境）
├── web/
│   ├── app.py                  # FastAPI 后端服务与路由定义
│   ├── matcher.py              # 智能集数提取与字幕自动配对引擎
│   └── presser.py              # 并发压制调度管理与 FFmpeg 智能查找调用
├── static/
│   └── index.html              # 现代化响应式控制台前端页面
└── .github/workflows/
    └── build_releases.yml      # Windows & macOS 多端云端自动打包工作流
```

---

## 📄 License
MIT License.
