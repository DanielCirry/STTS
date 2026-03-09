# STTS - Speech to Text to Speech

VRChat 및 일반 용도를 위한 실시간 음성 번역 및 커뮤니케이션 도구.

**[STTS-Setup.exe (v1.0.0) 다운로드](https://github.com/DanielCirry/STTS/releases/download/v1.0.0/STTS-Setup.exe)**
> Windows에서 SmartScreen 경고가 표시될 수 있습니다. "추가 정보" > "실행"을 클릭하세요.

**[English](../README.md)** | **[日本語](README.ja.md)** | **[中文](README.zh.md)** | **[Espanol](README.es.md)**

---

## 빠른 시작

1. `STTS-Setup.exe`를 다운로드하고 실행
2. STTS를 실행하고 **Settings > Install Features**에서 음성 인식, 번역 등을 다운로드
3. **Settings > Audio**에서 마이크와 오디오 장치를 설정
4. 마이크 버튼을 클릭하고 말하기 시작

---

## 메뉴 바 컨트롤

메뉴 바에 모든 기능의 빠른 토글이 있습니다:

- **STT** — 음성 인식 시작/중지. 음성이 텍스트로 변환되어 채팅에 표시됨
- **TTS** — 텍스트 음성 변환 켜기/끄기. 켜면 텍스트가 선택한 음성으로 읽힘
- **Trans** — 번역 켜기/끄기. 설정된 언어 쌍 간에 음성이 번역됨
- **Listen** — 스피커 캡처 시작/중지. 시스템/게임 오디오를 듣고 텍스트로 변환하고 선택적으로 번역
- **AI** — AI 어시스턴트 켜기/끄기. 활성화 키워드(기본값: "jarvis")를 말하여 AI 응답을 받음
- **Speak** — AI 응답의 TTS 읽기 토글
- **Emoji** — AI 응답의 이모지 모드 토글
- **Mic→RVC** — 마이크 출력에 실시간 음성 변환 적용
- **TTS→RVC** — TTS 오디오를 로드된 RVC 음성 모델을 통해 라우팅
- **Settings**(톱니바퀴 아이콘) — 설정 패널 열기
- **Quit**(전원 아이콘) — STTS를 종료하고 앱을 닫기

언어 쌍 버튼은 사이드바에 표시됩니다 — 탭하여 편집, 스왑 화살표로 방향 반전. 여러 쌍을 저장하고 전환 가능.

---

## 채팅 뷰

메인 영역에 모든 메시지 표시:

- **내 음성** — 실시간으로 텍스트 변환된 내용
- **번역** — 음성의 번역 버전
- **AI 응답** — AI 어시스턴트의 답변
- **스피커 텍스트** — 스피커 캡처에서 변환된 텍스트(선택적 번역 포함)

하단 텍스트 박스에 입력하여 수동으로 텍스트 전송. 해당 기능이 켜져 있으면 이 텍스트도 번역되어 VRChat에 전송됨.

---

## 설정

### AI Models
STT 모델 크기 선택(tiny가 가장 빠르고, medium이 가장 정확). CPU 또는 CUDA 선택. 모델 다운로드 또는 삭제.

### Translation
번역 켜기/끄기. 제공자 선택: **Free**(온라인, 키 불필요), **Local**(NLLB, 오프라인), **DeepL** 또는 **Google Cloud**. 언어는 언어 쌍 버튼으로 설정.

### Text-to-Speech
- **Engine** — 선택: **Piper**(빠름, 오프라인), **Edge TTS**(Microsoft 음성, 인터넷 필요), **Windows SAPI**(내장), **VOICEVOX**(일본어 애니메이션 음성)
- **Voice** — 드롭다운에서 음성 선택
- **Speed / Pitch** — 속도와 음높이 조절
- **"Test Voice"** — 현재 음성의 샘플 재생

### AI Assistant
- **Provider** — **Free**는 API 키 불필요. 기타: Local LLM, Groq, Google, OpenAI, Anthropic
- **Keyword** — AI를 활성화하는 문구(기본값: "jarvis"). 마이크와 스피커 캡처 모두에서 작동
- **폴백 체인** — 기본 제공자가 실패하면 STTS가 자동으로 다음 사용 가능한 제공자를 시도

### Voice Conversion (RVC)
- **Browse** — `.pth` 음성 모델 파일 로드(일치하는 `.index` 파일 자동 감지)
- **Pitch / Index Ratio** — 음성 변환 조정
- **Test Voice** — 3초 오디오를 녹음하고 변환된 버전 재생
- **Mic RVC** — 마이크에 실시간 음성 변환 적용(별도 출력 장치 설정 가능)
- **TTS RVC** — 모든 TTS 출력을 RVC 모델을 통해 라우팅

### VR Overlay
SteamVR이 실행 중이고 헤드셋이 연결되어 있어야 합니다. 두 개의 오버레이 패널:

- **알림 오버레이** — 최신 메시지를 팝업으로 표시. 페이드 인/아웃, 자동 숨김 타이머, 머리 추적 설정 가능
- **메시지 로그 오버레이** — 최근 메시지의 스크롤 히스토리 표시. 최대 메시지 수와 스크롤 방향 설정 가능

두 오버레이 모두 독립적인 설정:
- **위치**(X, Y, 거리) — VR 공간 내 원하는 곳에 배치
- **크기**(너비, 높이) — 원하는 대로 크기 조정
- **글꼴 크기 / 색상** — 텍스트 외관 커스터마이즈
- **배경 색상 / 불투명도** — 패널 투명도 조정
- **콘텐츠 필터** — 표시할 텍스트 유형 선택(음성, 번역, AI 응답, 스피커 캡처)

설정의 **캔버스 에디터**로 오버레이를 시각적으로 드래그하고 크기 조정 가능.

### Audio Devices
입력 마이크와 출력 스피커 선택. 스피커 캡처 소스 설정.

### Output Routing
텍스트와 오디오를 여러 대상에 동시 전송.
- **Add Profile** — 새 출력 프로필 생성(최대 5개)
- 각 프로필: 오디오 출력 장치, TTS/RVC 오디오 토글, OSC IP/포트, 텍스트 토글(원본, 번역, AI, 리슨)
- Profile 1은 기본이며 삭제 불가

### API Credentials
클라우드 서비스(OpenAI, Anthropic, Google, Groq, DeepL)의 API 키 입력. 해당 서비스 사용 시에만 필요. **Free**는 키 불필요.

### Install Features
기본 설치 프로그램은 작음. 추가 기능은 필요에 따라 다운로드:

| 기능 | 내용 | 크기 |
|------|------|------|
| **Speech-to-Text (Whisper)** | 로컬 음성 인식 | 약 300 MB |
| **PyTorch** | 번역과 RVC에 필요(CPU 또는 CUDA 선택) | 약 200-2000 MB |
| **Translation (NLLB)** | 오프라인 번역, 200+ 언어 | 약 50 MB |
| **Local LLM** | PC에서 AI 모델 실행 | 약 50 MB |
| **RVC Voice Conversion** | 실시간 보이스 체인지 | 약 100 MB |
| **Piper TTS** | 오프라인 텍스트 음성 변환 | 약 150 MB |
| **VOICEVOX Engine** | 일본어 애니메이션 음성 합성(DirectML 또는 CPU) | 약 1.75 GB |

각 항목 옆의 **Install**을 클릭. 녹색 = 이미 설치됨.

---

## VRChat

1. VRChat에서: **Action Menu > Options > OSC > Enable**
2. STTS는 기본적으로 `127.0.0.1:9000`으로 전송(표준 VRChat OSC 포트)
3. 음성과 번역이 VRChat 채팅박스에 자동 표시
4. STTS 처리 중 타이핑 인디케이터 표시

---

## 소스에서 실행

### 필요 사항
- Python 3.10.x — [python.org](https://www.python.org/downloads/) ("Add Python to PATH" 체크)
- Node.js 20+ — [nodejs.org](https://nodejs.org/)

### 설정 및 실행

```bash
git clone https://github.com/DanielCirry/STTS.git
cd STTS

# 옵션 A: 자동
setup.bat          # venv 생성, 의존성 설치, 프론트엔드 빌드
Start-STTS.bat     # 백엔드 시작 + 브라우저 열기

# 옵션 B: 수동
npm install
npx vite build
cd python
python -m venv venv
venv\Scripts\pip install -r requirements-base.txt
venv\Scripts\python.exe main.py
```

선택적 Python 패키지(필요한 것 설치):
```bash
cd python
venv\Scripts\pip install -r requirements-stt.txt           # Whisper
venv\Scripts\pip install -r requirements-translation.txt   # 번역
venv\Scripts\pip install -r requirements-tts-extra.txt     # Piper TTS
venv\Scripts\pip install -r requirements-rvc.txt           # RVC
venv\Scripts\pip install -r requirements-local-llm.txt     # 로컬 LLM
# CUDA:
venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

개발 시 핫 리로드를 사용하려면 별도 터미널에서 `npx vite`(프론트엔드)와 `python main.py`(백엔드)를 실행.

### 설치 프로그램 빌드

```bash
npx vite build
cd python && venv\Scripts\python.exe -m PyInstaller stts-lite.spec --noconfirm
"C:\Program Files (x86)\NSIS\makensis.exe" installer\stts-installer.nsi
# 출력: STTS-Setup.exe
```

---

## 시스템 요구 사항

- Windows 10/11 (64비트)
- RAM 최소 4 GB, 로컬 AI는 8 GB 이상 권장
- NVIDIA CUDA GPU (선택 사항, 처리 가속)
- SteamVR (선택 사항, VR 오버레이용)
- 인터넷 (선택 사항, Edge TTS 및 클라우드 AI용 — 핵심 기능은 오프라인 작동)

## 라이선스

MIT
