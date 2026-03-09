# STTS - Speech to Text to Speech

VRChatや一般用途向けのリアルタイム音声翻訳・コミュニケーションツール。

**[STTS-Setup.exe (v1.0.0) をダウンロード](https://github.com/DanielCirry/STTS/releases/download/v1.0.0/STTS-Setup.exe)**
> WindowsのSmartScreen警告が表示される場合があります。「詳細情報」>「実行」をクリックしてください。

**[English](../README.md)** | **[中文](README.zh.md)** | **[한국어](README.ko.md)** | **[Espanol](README.es.md)**

---

## クイックスタート

1. `STTS-Setup.exe` をダウンロードして実行
2. STTSを起動し、**Settings > Install Features** で音声認識、翻訳などをダウンロード
3. **Settings > Audio** でマイクとオーディオデバイスを設定
4. マイクボタンをクリックして話し始める

---

## メニューバーコントロール

メニューバーに全機能のクイック切替があります:

- **STT** — 音声認識の開始/停止。音声が文字起こしされてチャットに表示される
- **TTS** — 音声合成の有効/無効。有効時、テキストが選択した音声で読み上げられる
- **Trans** — 翻訳の有効/無効。設定した言語ペア間で音声が翻訳される
- **Listen** — スピーカーキャプチャの開始/停止。システム/ゲーム音声を聞き取り、文字起こしして翻訳（オプション）
- **AI** — AIアシスタントの有効/無効。起動キーワード（デフォルト: "jarvis"）でAI応答を取得
- **Speak** — AI応答のTTS読み上げを切り替え
- **Emoji** — AI応答の絵文字モードを切り替え
- **Mic→RVC** — マイク出力にリアルタイム音声変換を適用
- **TTS→RVC** — TTS音声を読み込んだRVCボイスモデル経由でルーティング
- **Settings**（歯車アイコン） — 設定パネルを開く
- **Quit**（電源アイコン） — STTSをシャットダウンしてアプリを終了

言語ペアボタンはサイドバーに表示されます — タップで編集、スワップ矢印で方向を反転。複数ペアを保存して切り替え可能。

---

## チャットビュー

メインエリアに全メッセージを表示:

- **あなたの音声** — リアルタイムで文字起こしされた内容
- **翻訳** — 音声の翻訳版
- **AI応答** — AIアシスタントからの返答
- **スピーカーテキスト** — スピーカーキャプチャからの文字起こし（翻訳オプション付き）

下部のテキストボックスに入力してテキストを手動送信。このテキストも翻訳されVRChatに送信される（機能が有効な場合）。

---

## 設定

### AI Models
STTモデルサイズを選択（tinyが最速、mediumが最も正確）。CPUまたはCUDAを選択。モデルのダウンロードと削除。

### Translation
翻訳の有効/無効。プロバイダーを選択: **Free**（オンライン、キー不要）、**Local**（NLLB、オフライン）、**DeepL**、**Google Cloud**。言語はサイドバーの言語ペアボタンで設定。

### Text-to-Speech
- **Engine** — 選択: **Piper**（高速、オフライン）、**Edge TTS**（Microsoft音声、インターネット必要）、**Windows SAPI**（内蔵）、**VOICEVOX**（日本語アニメ音声）
- **Voice** — ドロップダウンから音声を選択
- **Speed / Pitch** — 速度と音の高低を調整
- **"Test Voice"** — 現在の音声のサンプルを再生

### AI Assistant
- **Provider** — **Free** はAPIキー不要。他: Local LLM、Groq、Google、OpenAI、Anthropic
- **Keyword** — AIを起動するフレーズ（デフォルト: "jarvis"）。マイクとスピーカーキャプチャの両方から動作
- **フォールバックチェーン** — プライマリプロバイダーが失敗した場合、STTSは自動的に次の利用可能なプロバイダーを試行

### Voice Conversion (RVC)
- **Browse** — `.pth` ボイスモデルファイルを読み込み（対応する `.index` ファイルを自動検出）
- **Pitch / Index Ratio** — 音声変換を調整
- **Test Voice** — 3秒録音して変換版を再生
- **Mic RVC** — マイクにリアルタイムで音声変換を適用（別の出力デバイスを設定可能）
- **TTS RVC** — 全TTS出力をRVCモデル経由でルーティング

### VR Overlay
SteamVRが起動し、ヘッドセットが接続されている必要があります。2つのオーバーレイパネル:

- **通知オーバーレイ** — 最新メッセージをポップアップ表示。フェードイン/アウト、自動非表示タイマー、頭部追従を設定可能
- **メッセージログオーバーレイ** — 最近のメッセージのスクロール履歴を表示。最大メッセージ数とスクロール方向を設定可能

両方のオーバーレイに独立した設定:
- **位置**（X、Y、距離） — VR空間内の任意の場所に配置
- **サイズ**（幅、高さ） — お好みにリサイズ
- **フォントサイズ / 色** — テキストの外観をカスタマイズ
- **背景色 / 不透明度** — パネルの透明度を調整
- **コンテンツフィルター** — 表示するテキストタイプを選択（音声、翻訳、AI応答、スピーカーキャプチャ）

設定の**キャンバスエディター**でオーバーレイを視覚的にドラッグ＆リサイズ可能。

### Audio Devices
入力用マイクと出力用スピーカーを選択。スピーカーキャプチャソースも設定。

### Output Routing
テキストと音声を複数の送信先に同時送信。
- **Add Profile** — 新規出力プロファイルを作成（最大5つ）
- 各プロファイルに: 音声出力デバイス、TTS/RVCオーディオ切替、OSC IP/ポート、テキスト切替（オリジナル、翻訳、AI、リッスン）
- Profile 1はデフォルトで削除不可

### API Credentials
クラウドサービス（OpenAI、Anthropic、Google、Groq、DeepL）のAPIキーを入力。これらのプロバイダー使用時のみ必要。**Free** プロバイダーはキー不要。

### Install Features
基本インストーラーは小さめ。追加機能はオンデマンドでダウンロード:

| 機能 | 内容 | サイズ |
|------|------|--------|
| **Speech-to-Text (Whisper)** | ローカル音声認識 | 約300 MB |
| **PyTorch** | 翻訳とRVCに必要（CPUまたはCUDA選択） | 約200-2000 MB |
| **Translation (NLLB)** | オフライン翻訳、200以上の言語 | 約50 MB |
| **Local LLM** | PCでAIモデルを実行 | 約50 MB |
| **RVC Voice Conversion** | リアルタイムボイスチェンジ | 約100 MB |
| **Piper TTS** | オフライン音声合成 | 約150 MB |
| **VOICEVOX Engine** | 日本語アニメ音声合成（DirectMLまたはCPU） | 約1.75 GB |

各項目の横にある **Install** をクリック。緑 = インストール済み。

---

## VRChat

1. VRChat内: **Action Menu > Options > OSC > Enable**
2. STTSはデフォルトで `127.0.0.1:9000` に送信（標準VRChat OSCポート）
3. 音声と翻訳がVRChatチャットボックスに自動表示
4. STTS処理中はタイピングインジケーターが表示

---

## ソースから実行

### 必要なもの
- Python 3.10.x — [python.org](https://www.python.org/downloads/)（"Add Python to PATH" にチェック）
- Node.js 20+ — [nodejs.org](https://nodejs.org/)

### セットアップと実行

```bash
git clone https://github.com/DanielCirry/STTS.git
cd STTS

# オプションA: 自動
setup.bat          # venv作成、依存関係インストール、フロントエンドビルド
Start-STTS.bat     # バックエンド起動 + ブラウザを開く

# オプションB: 手動
npm install
npx vite build
cd python
python -m venv venv
venv\Scripts\pip install -r requirements-base.txt
venv\Scripts\python.exe main.py
```

オプションPythonパッケージ（必要なものをインストール）:
```bash
cd python
venv\Scripts\pip install -r requirements-stt.txt           # Whisper
venv\Scripts\pip install -r requirements-translation.txt   # 翻訳
venv\Scripts\pip install -r requirements-tts-extra.txt     # Piper TTS
venv\Scripts\pip install -r requirements-rvc.txt           # RVC
venv\Scripts\pip install -r requirements-local-llm.txt     # ローカルLLM
# CUDA用:
venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

開発時にホットリロードを使う場合は、`npx vite`（フロントエンド）と `python main.py`（バックエンド）を別々のターミナルで実行。

### インストーラーのビルド

```bash
npx vite build
cd python && venv\Scripts\python.exe -m PyInstaller stts-lite.spec --noconfirm
"C:\Program Files (x86)\NSIS\makensis.exe" installer\stts-installer.nsi
# 出力: STTS-Setup.exe
```

---

## システム要件

- Windows 10/11（64ビット）
- RAM 4 GB最低、ローカルAIには8 GB以上推奨
- NVIDIA CUDA対応GPU（オプション、処理高速化）
- SteamVR（オプション、VRオーバーレイ用）
- インターネット（オプション、Edge TTSとクラウドAI用 — コア機能はオフライン動作）

## ライセンス

MIT
