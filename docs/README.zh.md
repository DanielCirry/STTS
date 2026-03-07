# STTS - Speech to Text to Speech

适用于VRChat及通用场景的实时语音翻译与通讯工具。

**[下载 STTS-Setup.exe (v1.0.0)](https://github.com/DanielCirry/STTS/releases/download/v1.0.0/STTS-Setup.exe)**
> Windows可能会显示SmartScreen警告。点击"更多信息">"仍要运行"。

**[English](../README.md)** | **[日本語](README.ja.md)** | **[한국어](README.ko.md)** | **[Espanol](README.es.md)**

---

## 快速开始

1. 下载并运行 `STTS-Setup.exe`
2. 启动STTS — 设置向导引导你完成麦克风、模型和集成配置
3. 进入 **Install Features** 下载语音识别、翻译等功能
4. 点击麦克风按钮开始说话

---

## 菜单栏控制

菜单栏提供所有功能的快捷开关:

- **STT** — 开始/停止语音识别。你的语音被转录并显示在聊天中
- **TTS** — 开启/关闭文字转语音。开启时，文本通过所选语音朗读
- **Trans** — 开启/关闭翻译。你的语音在配置的语言对之间进行翻译
- **Listen** — 开始/停止扬声器捕获。监听系统/游戏音频，转录并可选翻译
- **AI** — 开启/关闭AI助手。说出激活关键词（默认: "jarvis"）获取AI回复
- **Speak** — 切换AI回复是否通过TTS朗读
- **Emoji** — 切换AI回复的表情模式
- **Mic→RVC** — 对麦克风输出应用实时语音转换
- **TTS→RVC** — 将TTS音频通过已加载的RVC语音模型路由
- **Settings**（齿轮图标） — 打开设置面板
- **Quit**（电源图标） — 关闭STTS并退出应用

语言对按钮显示在侧边栏中 — 点击编辑，使用交换箭头反转方向。可保存多个语言对并切换。

---

## 聊天视图

主区域显示所有消息:

- **你的语音** — 实时转录的内容
- **翻译** — 你语音的翻译版本
- **AI回复** — AI助手的回复
- **扬声器文本** — 扬声器捕获的转录（可选翻译）

在底部文本框中输入可手动发送文本。如果相关功能开启，该文本也会被翻译并发送到VRChat。

---

## 设置

### AI Models
选择STT模型大小（tiny最快，medium最准确）。选择CPU或CUDA。下载或删除模型。

### Translation
开启/关闭翻译。选择提供商: **Free**（在线，无需密钥）、**Local**（NLLB，离线）、**DeepL** 或 **Google Cloud**。语言通过语言对按钮设置。

### Text-to-Speech
- **Engine** — 选择: **Piper**（快速，离线）、**Edge TTS**（微软语音，需要网络）、**Windows SAPI**（内置）、**VOICEVOX**（日语动漫语音）
- **Voice** — 从下拉菜单选择语音
- **Speed / Pitch** — 调整语速和音调
- **"Test Voice"** — 播放当前语音的示例

### AI Assistant
- **Provider** — **Free** 无需API密钥。其他: Local LLM、Groq、Google、OpenAI、Anthropic
- **Keyword** — 激活AI的短语（默认: "jarvis"）。可通过麦克风和扬声器捕获触发
- **回退链** — 如果主要提供商失败，STTS会自动尝试下一个可用的提供商

### Voice Conversion (RVC)
- **Browse** — 加载 `.pth` 语音模型文件（自动检测匹配的 `.index` 文件）
- **Pitch / Index Ratio** — 调整语音转换参数
- **Test Voice** — 录制3秒音频并播放转换后的版本
- **Mic RVC** — 实时对麦克风应用语音转换（可配置独立输出设备）
- **TTS RVC** — 将所有TTS输出通过RVC模型路由

### VR Overlay
需要SteamVR运行并连接头显。两个覆盖层面板:

- **通知覆盖层** — 以弹窗形式显示最新消息。可配置淡入/淡出、自动隐藏计时器和头部追踪
- **消息日志覆盖层** — 显示最近消息的滚动历史。可配置最大消息数和滚动方向

两个覆盖层都有独立设置:
- **位置**（X、Y、距离） — 放置在VR空间的任意位置
- **大小**（宽度、高度） — 按偏好调整大小
- **字体大小 / 颜色** — 自定义文本外观
- **背景颜色 / 不透明度** — 调整面板透明度
- **内容过滤器** — 选择显示哪些文本类型（语音、翻译、AI回复、扬声器捕获）

在设置中使用**画布编辑器**可视化拖拽和调整覆盖层大小。

### Audio Devices
选择输入麦克风和输出扬声器。配置扬声器捕获源。

### Output Routing
将文本和音频同时发送到多个目的地。
- **Add Profile** — 创建新输出配置文件（最多5个）
- 每个配置文件有: 音频输出设备、TTS/RVC音频开关、OSC IP/端口、文本开关（原文、翻译、AI、监听）
- Profile 1为默认，不可删除

### API Credentials
输入云服务（OpenAI、Anthropic、Google、Groq、DeepL）的API密钥。仅在使用这些服务时需要。**Free** 无需密钥。

### Install Features
基础安装包体积小。额外功能按需下载:

| 功能 | 作用 | 大小 |
|------|------|------|
| **Speech-to-Text (Whisper)** | 本地语音识别 | 约300 MB |
| **PyTorch** | 翻译和RVC所需（选CPU或CUDA） | 约200-2000 MB |
| **Translation (NLLB)** | 离线翻译，200+语言 | 约50 MB |
| **Local LLM** | 在本机运行AI模型 | 约50 MB |
| **RVC Voice Conversion** | 实时变声 | 约100 MB |
| **Piper TTS** | 离线文字转语音 | 约150 MB |
| **VOICEVOX Engine** | 日语动漫语音合成（DirectML或CPU） | 约1.75 GB |

点击每项旁边的 **Install**。绿色 = 已安装。

---

## VRChat

1. 在VRChat中: **Action Menu > Options > OSC > Enable**
2. STTS默认发送到 `127.0.0.1:9000`（标准VRChat OSC端口）
3. 你的语音和翻译自动显示在VRChat聊天框中
4. STTS处理时显示打字指示器

---

## 从源码运行

### 需要
- Python 3.10.x — [python.org](https://www.python.org/downloads/)（勾选"Add Python to PATH"）
- Node.js 20+ — [nodejs.org](https://nodejs.org/)

### 设置和运行

```bash
git clone https://github.com/DanielCirry/STTS.git
cd STTS

# 选项A: 自动
setup.bat          # 创建venv，安装依赖，构建前端
Start-STTS.bat     # 启动后端 + 打开浏览器

# 选项B: 手动
npm install
npx vite build
cd python
python -m venv venv
venv\Scripts\pip install -r requirements-base.txt
venv\Scripts\python.exe main.py
```

可选Python包（按需安装）:
```bash
cd python
venv\Scripts\pip install -r requirements-stt.txt           # Whisper
venv\Scripts\pip install -r requirements-translation.txt   # 翻译
venv\Scripts\pip install -r requirements-tts-extra.txt     # Piper TTS
venv\Scripts\pip install -r requirements-rvc.txt           # RVC
venv\Scripts\pip install -r requirements-local-llm.txt     # 本地LLM
# CUDA:
venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

开发时使用热重载，在不同终端分别运行 `npx vite`（前端）和 `python main.py`（后端）。

### 构建安装包

```bash
npx vite build
cd python && venv\Scripts\python.exe -m PyInstaller stts-lite.spec --noconfirm
"C:\Program Files (x86)\NSIS\makensis.exe" installer\stts-installer.nsi
# 输出: STTS-Setup.exe
```

---

## 系统要求

- Windows 10/11（64位）
- 内存最低4 GB，本地AI推荐8 GB以上
- NVIDIA CUDA GPU（可选，加速处理）
- SteamVR（可选，用于VR覆盖层）
- 网络（可选，用于Edge TTS和云AI — 核心功能离线可用）

## 许可证

MIT
