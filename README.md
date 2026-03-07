# STTS - Speech to Text to Speech

Real-time speech translation and communication tool for VRChat and general use.

**[Download STTS-Setup.exe (v1.0.0)](https://github.com/DanielCirry/STTS/releases/download/v1.0.0/STTS-Setup.exe)**
> Windows may show a SmartScreen warning. Click "More info" > "Run anyway".

**[日本語](docs/README.ja.md)** | **[中文](docs/README.zh.md)** | **[한국어](docs/README.ko.md)** | **[Espanol](docs/README.es.md)**

---

## Quick Start

1. Download and run `STTS-Setup.exe`
2. Launch STTS — a setup wizard guides you through microphone, models, and integrations
3. You'll be taken to **Install Features** to download speech recognition, translation, etc.
4. Click the microphone button and start talking

---

## Menu Bar Controls

The menu bar has quick toggles for all features:

- **STT** — Start/stop speech recognition. Your speech is transcribed and shown in the chat.
- **TTS** — Turn text-to-speech on/off. When on, text is read aloud through your selected voice.
- **Trans** — Turn translation on/off. Your speech is translated between your configured language pairs.
- **Listen** — Start/stop speaker capture. Listens to system/game audio, transcribes it, and optionally translates it.
- **AI** — Turn the AI assistant on/off. Say the activation keyword (default: "jarvis") to get an AI response.
- **Speak** — Toggle whether AI responses are read aloud via TTS.
- **Emoji** — Toggle emoji mode for AI responses.
- **Mic→RVC** — Apply real-time voice conversion to your microphone output.
- **TTS→RVC** — Route TTS audio through your loaded RVC voice model.
- **Settings** (gear icon) — Open the full settings panel.
- **Quit** (power icon) — Shut down STTS and close the application.

Language pair buttons appear in the sidebar — tap to edit, use the swap arrow to reverse direction. Save multiple pairs and switch between them.

---

## Chat View

The main area shows all messages:

- **Your speech** — What you said, transcribed in real-time
- **Translations** — Translated versions of your speech
- **AI responses** — Replies from the AI assistant
- **Speaker text** — Transcriptions from speaker capture (with optional translation)

Type in the text box at the bottom to send text manually. This text also gets translated and sent to VRChat if those features are on.

---

## Settings

### AI Models
Choose STT model size (tiny is fastest, medium is most accurate). Select CPU or CUDA. Download or delete models.

### Translation
Turn translation on/off. Choose provider: **Free** (online, no key needed), **Local** (NLLB, offline), **DeepL**, or **Google Cloud**. The actual languages are set via the language pair buttons.

### Text-to-Speech
- **Engine** — Pick one: **Piper** (fast, offline), **Edge TTS** (Microsoft voices, needs internet), **Windows SAPI** (built-in), **VOICEVOX** (Japanese anime voices)
- **Voice** — Pick a voice from the dropdown
- **Speed / Pitch** — Adjust how fast and high/low the voice sounds
- **"Test Voice"** — Play a sample to hear the current voice

### AI Assistant
- **Provider** — **Free** works without any API key. Other options: Local LLM, Groq, Google, OpenAI, Anthropic
- **Keyword** — The phrase that activates the AI (default: "jarvis"). Works from both microphone and speaker capture.
- **Fallback chain** — If your primary provider fails, STTS automatically tries the next available one

### Voice Conversion (RVC)
- **Browse** — Load a `.pth` voice model file (auto-detects matching `.index` file)
- **Pitch / Index Ratio** — Tune the voice conversion
- **Test Voice** — Records 3 seconds of audio and plays back the converted version
- **Mic RVC** — Apply voice conversion to your microphone in real-time (separate output device configurable)
- **TTS RVC** — Route all TTS output through the RVC model

### VR Overlay
Requires SteamVR running with a connected headset. Two overlay panels:

- **Notification overlay** — Shows the latest message as a pop-up. Configurable fade in/out, auto-hide timer, and head tracking.
- **Message log overlay** — Shows a scrolling history of recent messages. Configurable max messages and scroll direction.

Both overlays have independent settings for:
- **Position** (X, Y, distance) — Place anywhere in your VR space
- **Size** (width, height) — Resize to your preference
- **Font size / color** — Customize text appearance
- **Background color / opacity** — Adjust panel transparency
- **Content filters** — Choose which text types appear (speech, translations, AI responses, speaker capture)

Use the **canvas editor** in settings to visually drag and resize overlays.

### Audio Devices
Select which microphone to use for input and which speaker for output. Also configure speaker capture source.

### Output Routing
Send your text and audio to multiple destinations at once.
- **Add Profile** — Create a new output profile (up to 5)
- Each profile has its own: audio output device, TTS/RVC audio toggles, OSC IP/port, and text toggles (original, translated, AI, listen)
- Profile 1 is the default and can't be deleted

### API Credentials
Enter API keys for cloud services (OpenAI, Anthropic, Google, Groq, DeepL). Only needed if you use those providers. The **Free** provider needs no key.

### Install Features
The base installer is small. Extra features are downloaded on demand:

| Feature | What it does | Size |
|---------|-------------|------|
| **Speech-to-Text (Whisper)** | Local speech recognition | ~300 MB |
| **PyTorch** | Required for Translation & RVC (pick CPU or CUDA) | ~200-2000 MB |
| **Translation (NLLB)** | Offline translation, 200+ languages | ~50 MB |
| **Local LLM** | Run AI models on your PC | ~50 MB |
| **RVC Voice Conversion** | Real-time voice changing | ~100 MB |
| **Piper TTS** | Offline text-to-speech | ~150 MB |
| **VOICEVOX Engine** | Japanese anime voice synthesis (DirectML or CPU) | ~1.75 GB |

Click **Install** next to each. Green = installed.

---

## VRChat

1. In VRChat: **Action Menu > Options > OSC > Enable**
2. STTS sends to `127.0.0.1:9000` by default (standard VRChat OSC port)
3. Your speech and translations appear in the VRChat chatbox automatically
4. A typing indicator shows while STTS is processing

---

## Running from Source

### Requirements
- Python 3.10.x — [python.org](https://www.python.org/downloads/) (check "Add Python to PATH")
- Node.js 20+ — [nodejs.org](https://nodejs.org/)

### Setup and Run

```bash
git clone https://github.com/DanielCirry/STTS.git
cd STTS

# Option A: automatic
setup.bat          # creates venv, installs deps, builds frontend
Start-STTS.bat     # starts backend + opens browser

# Option B: manual
npm install
npx vite build
cd python
python -m venv venv
venv\Scripts\pip install -r requirements-base.txt
venv\Scripts\python.exe main.py
```

Optional Python packages (install any you need):
```bash
cd python
venv\Scripts\pip install -r requirements-stt.txt           # Whisper
venv\Scripts\pip install -r requirements-translation.txt   # Translation
venv\Scripts\pip install -r requirements-tts-extra.txt     # Piper TTS
venv\Scripts\pip install -r requirements-rvc.txt           # RVC
venv\Scripts\pip install -r requirements-local-llm.txt     # Local LLM
# For CUDA:
venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

For development with hot reload, run `npx vite` (frontend) and `python main.py` (backend) in separate terminals.

### Building the Installer

```bash
npx vite build
cd python && venv\Scripts\python.exe -m PyInstaller stts-lite.spec --noconfirm
"C:\Program Files (x86)\NSIS\makensis.exe" installer\stts-installer.nsi
# Output: STTS-Setup.exe
```

---

## System Requirements

- Windows 10/11 (64-bit)
- 4 GB RAM minimum, 8 GB+ recommended for local AI
- NVIDIA GPU with CUDA (optional, for faster processing)
- SteamVR (optional, for VR overlay)
- Internet (optional, for Edge TTS and cloud AI — core features work offline)

## License

MIT
