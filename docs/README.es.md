# STTS - Speech to Text to Speech

Herramienta de traduccion de voz en tiempo real y comunicacion para VRChat y uso general.

**[Descargar STTS-Setup.exe (v1.0.0)](https://github.com/DanielCirry/STTS/releases/download/v1.0.0/STTS-Setup.exe)**
> Windows puede mostrar una advertencia de SmartScreen. Haz clic en "Mas informacion" > "Ejecutar de todos modos".

**[English](../README.md)** | **[日本語](README.ja.md)** | **[中文](README.zh.md)** | **[한국어](README.ko.md)**

---

## Inicio rapido

1. Descarga y ejecuta `STTS-Setup.exe`
2. Abre STTS y ve a **Settings > Install Features** para descargar reconocimiento de voz, traduccion, etc.
3. Configura tu microfono y dispositivos de audio en **Settings > Audio**
4. Haz clic en el boton del microfono y empieza a hablar

---

## Controles de la barra de menu

La barra de menu tiene interruptores rapidos para todas las funciones:

- **STT** — Iniciar/detener el reconocimiento de voz. Tu voz se transcribe y se muestra en el chat
- **TTS** — Activar/desactivar texto a voz. Cuando esta activado, el texto se lee en voz alta con la voz seleccionada
- **Trans** — Activar/desactivar traduccion. Tu voz se traduce entre los pares de idiomas configurados
- **Listen** — Iniciar/detener captura de altavoz. Escucha audio del sistema/juego, lo transcribe y opcionalmente lo traduce
- **AI** — Activar/desactivar el asistente de IA. Di la palabra clave de activacion (por defecto: "jarvis") para obtener una respuesta de IA
- **Speak** — Alternar si las respuestas de IA se leen en voz alta por TTS
- **Emoji** — Alternar el modo de emojis para respuestas de IA
- **Mic→RVC** — Aplicar conversion de voz en tiempo real a la salida del microfono
- **TTS→RVC** — Enrutar el audio TTS a traves del modelo de voz RVC cargado
- **Settings** (icono de engranaje) — Abrir el panel de configuracion
- **Quit** (icono de encendido) — Cerrar STTS y salir de la aplicacion

Los botones de par de idiomas aparecen en la barra lateral — toca para editar, usa la flecha de intercambio para invertir la direccion. Guarda multiples pares y alterna entre ellos.

---

## Vista de chat

El area principal muestra todos los mensajes:

- **Tu voz** — Lo que dijiste, transcrito en tiempo real
- **Traducciones** — Versiones traducidas de tu voz
- **Respuestas de IA** — Respuestas del asistente de IA
- **Texto del altavoz** — Transcripciones de la captura de altavoz (con traduccion opcional)

Escribe en el cuadro de texto en la parte inferior para enviar texto manualmente. Este texto tambien se traduce y se envia a VRChat si esas funciones estan activadas.

---

## Configuracion

### AI Models
Elige el tamano del modelo STT (tiny es el mas rapido, medium es el mas preciso). Selecciona CPU o CUDA. Descarga o elimina modelos.

### Translation
Activar/desactivar traduccion. Elegir proveedor: **Free** (en linea, sin clave necesaria), **Local** (NLLB, sin conexion), **DeepL** o **Google Cloud**. Los idiomas se configuran con los botones de par de idiomas.

### Text-to-Speech
- **Engine** — Elige uno: **Piper** (rapido, funciona sin internet), **Edge TTS** (voces de Microsoft, necesita internet), **Windows SAPI** (integrado), **VOICEVOX** (voces de anime japones)
- **Voice** — Elige una voz del desplegable
- **Speed / Pitch** — Ajusta la velocidad y el tono de la voz
- **"Test Voice"** — Reproduce una muestra de la voz actual

### AI Assistant
- **Provider** — **Free** funciona sin clave API. Otros: Local LLM, Groq, Google, OpenAI, Anthropic
- **Keyword** — La frase que activa la IA (por defecto: "jarvis"). Funciona tanto desde el microfono como desde la captura de altavoz
- **Cadena de respaldo** — Si el proveedor principal falla, STTS intenta automaticamente el siguiente proveedor disponible

### Voice Conversion (RVC)
- **Browse** — Cargar un archivo de modelo de voz `.pth` (detecta automaticamente el archivo `.index` correspondiente)
- **Pitch / Index Ratio** — Ajustar la conversion de voz
- **Test Voice** — Graba 3 segundos de audio y reproduce la version convertida
- **Mic RVC** — Aplicar conversion de voz al microfono en tiempo real (dispositivo de salida separado configurable)
- **TTS RVC** — Enrutar toda la salida TTS a traves del modelo RVC

### VR Overlay
Requiere SteamVR en ejecucion con un casco conectado. Dos paneles de superposicion:

- **Superposicion de notificacion** — Muestra el ultimo mensaje como ventana emergente. Configurable: aparicion/desaparicion gradual, temporizador de ocultacion automatica y seguimiento de cabeza
- **Superposicion de registro de mensajes** — Muestra un historial con desplazamiento de mensajes recientes. Configurable: numero maximo de mensajes y direccion de desplazamiento

Ambas superposiciones tienen configuraciones independientes para:
- **Posicion** (X, Y, distancia) — Colocar en cualquier lugar de tu espacio VR
- **Tamano** (ancho, alto) — Redimensionar a tu preferencia
- **Tamano de fuente / color** — Personalizar la apariencia del texto
- **Color de fondo / opacidad** — Ajustar la transparencia del panel
- **Filtros de contenido** — Elegir que tipos de texto aparecen (voz, traducciones, respuestas de IA, captura de altavoz)

Usa el **editor de lienzo** en configuracion para arrastrar y redimensionar superposiciones visualmente.

### Audio Devices
Selecciona que microfono usar para entrada y que altavoz para salida. Configura la fuente de captura de altavoz.

### Output Routing
Envia tu texto y audio a multiples destinos a la vez.
- **Add Profile** — Crear un nuevo perfil de salida (hasta 5)
- Cada perfil tiene: dispositivo de salida de audio, interruptores de audio TTS/RVC, IP/puerto OSC e interruptores de texto (original, traducido, IA, escucha)
- Profile 1 es el predeterminado y no se puede eliminar

### API Credentials
Ingresa claves API para servicios en la nube (OpenAI, Anthropic, Google, Groq, DeepL). Solo necesario si usas esos servicios. **Free** no necesita clave.

### Install Features
El instalador base es pequeno. Las funciones extra se descargan a demanda:

| Funcion | Que hace | Tamano |
|---------|----------|--------|
| **Speech-to-Text (Whisper)** | Reconocimiento de voz local | ~300 MB |
| **PyTorch** | Necesario para Traduccion y RVC (elige CPU o CUDA) | ~200-2000 MB |
| **Translation (NLLB)** | Traduccion sin internet, 200+ idiomas | ~50 MB |
| **Local LLM** | Ejecutar modelos de IA en tu PC | ~50 MB |
| **RVC Voice Conversion** | Cambio de voz en tiempo real | ~100 MB |
| **Piper TTS** | Texto a voz sin internet | ~150 MB |
| **VOICEVOX Engine** | Sintesis de voz anime japones (DirectML o CPU) | ~1.75 GB |

Haz clic en **Install** junto a cada uno. Verde = ya instalado.

---

## VRChat

1. En VRChat: **Action Menu > Options > OSC > Enable**
2. STTS envia a `127.0.0.1:9000` por defecto (puerto OSC estandar de VRChat)
3. Tu voz y traducciones aparecen automaticamente en el chatbox de VRChat
4. Un indicador de escritura se muestra mientras STTS procesa

---

## Ejecutar desde el codigo fuente

### Requisitos
- Python 3.10.x — [python.org](https://www.python.org/downloads/) (marca "Add Python to PATH")
- Node.js 20+ — [nodejs.org](https://nodejs.org/)

### Configuracion y ejecucion

```bash
git clone https://github.com/DanielCirry/STTS.git
cd STTS

# Opcion A: automatico
setup.bat          # crea venv, instala dependencias, construye frontend
Start-STTS.bat     # inicia backend + abre navegador

# Opcion B: manual
npm install
npx vite build
cd python
python -m venv venv
venv\Scripts\pip install -r requirements-base.txt
venv\Scripts\python.exe main.py
```

Paquetes opcionales de Python (instala los que necesites):
```bash
cd python
venv\Scripts\pip install -r requirements-stt.txt           # Whisper
venv\Scripts\pip install -r requirements-translation.txt   # Traduccion
venv\Scripts\pip install -r requirements-tts-extra.txt     # Piper TTS
venv\Scripts\pip install -r requirements-rvc.txt           # RVC
venv\Scripts\pip install -r requirements-local-llm.txt     # LLM local
# CUDA:
venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Para desarrollo con recarga en caliente, ejecuta `npx vite` (frontend) y `python main.py` (backend) en terminales separadas.

### Construir el instalador

```bash
npx vite build
cd python && venv\Scripts\python.exe -m PyInstaller stts-lite.spec --noconfirm
"C:\Program Files (x86)\NSIS\makensis.exe" installer\stts-installer.nsi
# Salida: STTS-Setup.exe
```

---

## Requisitos del sistema

- Windows 10/11 (64 bits)
- RAM minimo 4 GB, 8 GB+ recomendado para IA local
- GPU NVIDIA con CUDA (opcional, para procesamiento mas rapido)
- SteamVR (opcional, para superposicion VR)
- Internet (opcional, para Edge TTS e IA en la nube — las funciones principales funcionan sin internet)

## Licencia

MIT
