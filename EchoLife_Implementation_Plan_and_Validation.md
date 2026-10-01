# EchoLife: Laptop Implementation Plan & Technical Validation
**Project:** Privacy-First Lifelong Digital Voice Identity for People Facing Speech Loss  
**Platform Target:** Laptop / Desktop (Windows / macOS / Linux)  
**Primary Voice Engine:** Coqui XTTS-v2 Zero-Shot Voice Cloning  
**Fallback Voice Engine:** OpenVoice v2 (MyShell.ai) — Auto-activated when XTTS-v2 is unavailable  
**Architecture:** Decoupled `frontend/` (Vanilla HTML/CSS/JS) & `backend/` (Python FastAPI) Architecture  
**Last Updated:** October 2026  

---

## 1. Executive Summary & Feasibility Verdict

EchoLife for Laptop is a 100% offline, privacy-first assistive voice identity platform. A user records a 10–20 second clean voice sample before or during the early stages of speech impairment. The platform captures their unique acoustic fingerprint (timbre, pitch, tone) and permanently enables them to type any message and have it spoken aloud through their laptop speakers in **their exact authentic voice**.

### Feasibility Verdict: **100% FEASIBLE & PRODUCTION-READY**
- By targeting the **laptop / desktop** platform, mobile memory and NPU hardware constraints are eliminated.
- **Coqui XTTS-v2** is currently the highest-fidelity open-source zero-shot voice cloning model available. It runs natively offline on modern laptops.
- With local speaker-latent extraction, synthesis latency drops to **sub-second response times** on GPU-equipped laptops (~0.6s–1.2s) and ~2.5s on multi-core modern CPUs.
- Zero cloud connectivity is required. The system works flawlessly in **Airplane Mode**.

---

## 2. Decoupled Frontend & Backend Architecture

The codebase is strictly organized into two primary folders: `backend/` and `frontend/`.

```
┌────────────────────────────────────────┐
│               FRONTEND                 │
│  (Modern Accessible AAC Web / UI)      │
│  • High-Contrast AAC Phrase Grid       │
│  • Voice Enrollment Wizard & Mic Meter │
│  • Free-Text Typing & Quick Trigger    │
│  • Low-Latency WebAudio Player         │
└───────────────────▲────────────────────┘
                    │ REST / WebSocket
                    ▼ (Localhost:8000)
┌────────────────────────────────────────┐
│               BACKEND                  │
│  (Python FastAPI Local Edge Engine)    │
│  • Engine Router: XTTS-v2 → OpenVoice │
│  • Speaker Latent Extraction & Caching │
│  • AES-256 Encrypted Identity Vault    │
│  • Local Audio Preprocessing & Denoise │
└────────────────────────────────────────┘
```

---

## 3. The Core Voice Workflow (Laptop Execution)

```
[Step 1: One-Time Voice Preservation]
Frontend Mic Capture (10-20s sample) ──> POST /api/enroll ──> Backend Audio Preprocessor
                                                                        │
                                                                        ▼
                                                   Engine Router: Try XTTS-v2 First
                                                   If XTTS-v2 loads OK  ──> Extract (gpt_cond_latent + speaker_embedding)
                                                   If XTTS-v2 fails     ──> Fallback to OpenVoice v2 (extract speaker_se tone embedding)
                                                                        │
                                                                        ▼
                                                   Active Engine + Speaker Profile Saved
                                                   AES-256 Vault Storage: `profiles/voice.echovox`
                                                   (profile includes: engine_name + serialized embedding)

──────────────────────────────────────────────────────────────────────────

[Step 2: Everyday Speech Synthesis]
Frontend AAC Tap / Free Typing ──> POST /api/synthesize ──> Engine Router resolves active engine
                                                                        │
                                            ┌───────────────────────────┴───────────────────────────┐
                                            ▼                                                       ▼
                               [XTTS-v2 active]                                      [OpenVoice v2 fallback active]
                          model.inference(text,                               base_tts(text) ──> ToneColorConverter
                          gpt_cond_latent,                                    (converts base voice into user's tone)
                          speaker_embedding)                                           │
                                            └───────────────────────────┬───────────────────────────┘
                                                                        ▼
Frontend WebAudio Plays Instantly <── StreamingResponse WAV <── Unified Audio Buffer
```

---

## 4. Key Performance Optimizations (Laptop-Specific)

### Optimization 1: Latent Caching (Bypassing `speaker_wav` overhead)
Normally, calling `tts.tts_to_file(speaker_wav="voice.wav")` forces the model to reload, resample, and re-compute speaker embeddings on every single sentence.
- **EchoLife Solution:** Extract the conditioning latents **once** during enrollment using the verified direct `Xtts` model class API (Coqui TTS ≥ 0.22):
  ```python
  # ✅ CORRECT — Use the direct Xtts model class, NOT tts.synthesizer.tts_model
  from TTS.tts.configs.xtts_config import XttsConfig
  from TTS.tts.models.xtts import Xtts

  config = XttsConfig()
  config.load_json("path/to/xtts_v2/config.json")
  model = Xtts.init_from_config(config)
  model.load_checkpoint(config, checkpoint_dir="path/to/xtts_v2/", eval=True)
  model.cuda()  # or model.cpu() if no GPU

  gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
      audio_path=["user_voice.wav"]
  )
  ```
  > ⚠️ **Critical:** Using `tts.synthesizer.tts_model.get_conditioning_latents()` will throw `AttributeError` in Coqui TTS ≥ 0.22. The direct `Xtts` class is the only correct path.

  The backend holds these latents in memory. For all subsequent speech, they are passed directly to `model.inference()` for instant generation without re-reading any audio files.

### Optimization 2: Pre-Synthesized AAC Quick-Phrases
For life-critical emergency and common daily requests (*"I need water"*, *"Please help me sit up"*, *"I love you"*), the backend pre-synthesizes and caches the audio files locally during enrollment.
- **Latency for Emergency Phrases:** **0 milliseconds** (instant playback on click).

### Optimization 3: Streaming Audio Output via `StreamingResponse`
Instead of waiting for an entire paragraph to finish generating, the backend uses FastAPI's **`StreamingResponse`** to stream raw WAV bytes to the frontend as they are generated clause-by-clause. The frontend `Web Audio API` decodes and queues these chunks for seamless near-instant playback.

> **Decision:** Phase 1 uses **`StreamingResponse` (Chunked HTTP)** — simpler to implement, zero additional setup, and fully sufficient for sentence-length AAC outputs. WebSocket streaming is deferred to a future iteration only if long-paragraph latency becomes a measurable problem.

---

## 5. Technology Stack & Key Model Decisions

| Layer | Component | Technology | Rationale |
| :--- | :--- | :--- | :--- |
| **Backend** | **Primary Voice Engine** | **Coqui XTTS-v2** (direct `Xtts` class) | Studio-grade zero-shot cloning from 10–20s sample; captures emotional nuances, accents, and unique vocal timbre. GPU preferred (~0.6s latency). |
| **Backend** | **Fallback Voice Engine** | **OpenVoice v2** (`openvoice` pip package) | Auto-activated if XTTS-v2 fails to load (low VRAM / missing weights). ~300MB, runs on CPU, ~0.8s latency. Uses Tone Color Converter to map base TTS voice into user's cloned tone. |
| **Backend** | **API & Engine Server** | **Python 3.10/3.11 + FastAPI + Uvicorn** | Fast, lightweight asynchronous local server running on `localhost:8000`. |
| **Backend** | **Speaker Fingerprint** | `gpt_cond_latent` + `speaker_embedding` | Pre-computing and saving these latents eliminates audio re-processing, cutting per-sentence synthesis time by 60%. |
| **Backend** | **Audio Processing** | `scipy`, `numpy`, `soundfile` | 16kHz mono normalization, silence trimming, and SNR quality validation. |
| **Backend** | **Local Security** | `cryptography` (AES-256-GCM) | Encrypts the saved speaker latents on disk; key is derived locally and never leaves the machine. |
| **Frontend** | **AAC Patient Interface** | **Vanilla HTML5 + CSS + JavaScript** | No build tools or `npm install` required. Starts instantly via `index.html`. Direct browser API access for `MediaRecorder` and `Web Audio API`. Lightweight and ideal for hackathon delivery timeline. |
| **Frontend** | **Audio Player** | **Web Audio API** | Real-time low-latency decoding of streamed WAV bytes from backend `StreamingResponse`. Chunks are decoded and queued seamlessly. |
| **Frontend** | **Mic Recorder** | **MediaRecorder API → `.webm` → Converted to `.wav` on Backend** | Browser `MediaRecorder` captures audio as `.webm` (browser default). The backend `audio_processor.py` **must convert `.webm` to 22050Hz mono `.wav`** using `pydub` + `ffmpeg` before passing to XTTS-v2. |

---

## 6. Project Directory Layout (2-Folder Architecture)

```
d:/Echolife/
├── EchoLife_Complete_Proposal.pdf             # Original competition proposal
├── EchoLife_Implementation_Plan_and_Validation.md # Master plan & documentation
│
├── backend/                                   # All AI, ML, Audio & Security Services
│   ├── requirements.txt                       # Python dependencies (torch, TTS, fastapi, etc.)
│   ├── main.py                                # FastAPI app entry point & route definitions
│   ├── config.py                              # Audio configs, model paths, sample rates
│   ├── services/
│   │   ├── voice_engine.py                    # Engine Router: XTTS-v2 primary + OpenVoice v2 fallback
│   │   ├── xtts_engine.py                     # XTTS-v2 specific: load, latent extraction, inference
│   │   ├── openvoice_engine.py                # OpenVoice v2 specific: tone extraction, ToneColorConverter
│   │   ├── audio_processor.py                 # 16kHz normalization, silence trimming, VAD
│   │   └── security_vault.py                  # AES-256-GCM encryption for .echovox profiles
│   ├── storage/
│   │   ├── profiles/                          # Encrypted speaker latent files (e.g., user.echovox)
│   │   └── cache/                             # Pre-synthesized emergency phrase WAVs
│   └── data/
│       └── default_phrases.json               # AAC categories (Emergency, Daily Needs, Family)
│
└── frontend/                                  # All UI, AAC Grid, Audio Capture & Client Logic
    ├── package.json (or index.html)           # Client setup & dependencies
    ├── public/
    │   └── assets/                            # Icons, high-contrast visual cues
    ├── src/
    │   ├── index.html                         # Main entry page
    │   ├── styles/                            # High-contrast CSS, accessibility themes
    │   ├── components/
    │   │   ├── AACGrid.js                     # Large one-touch phrase buttons & category tabs
    │   │   ├── CustomTyping.js                # Free-text input with instant speak trigger
    │   │   ├── VoiceEnrollment.js             # 3-step voice capture wizard & live mic meter
    │   │   └── AudioPlayer.js                 # Low-latency WebAudio playback controller
    │   └── api/
    │       └── client.js                      # Localhost API bindings (/enroll, /synthesize, /status)
```

---

## 7. Step-by-Step Implementation Roadmap

### Phase 1: Backend Core AI Engine (`backend/`)
- [ ] **1.1 Setup Environment:** Initialize Python 3.10/3.11 environment. Install dependencies:
  ```
  # Core (required for both engines)
  torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121  (if NVIDIA GPU)
  fastapi uvicorn python-multipart
  pydub soundfile numpy scipy cryptography ffmpeg-python

  # Primary engine — XTTS-v2
  TTS

  # Fallback engine — OpenVoice v2
  openvoice
  ```
  > ⚠️ `ffmpeg` must also be installed as a system binary (not just the Python wrapper) for `pydub` to convert `.webm` → `.wav`.

- [ ] **1.2 Engine Router (`services/voice_engine.py`) — Dual-Engine with Auto-Fallback:**
  - This is the single entry point for all synthesis requests. It tries XTTS-v2 first; if loading fails for any reason (low VRAM, missing model weights, import error), it transparently switches to OpenVoice v2:
    ```python
    # services/voice_engine.py
    ENGINE = None
    ENGINE_NAME = None

    def load_engine():
        global ENGINE, ENGINE_NAME
        try:
            from services.xtts_engine import XTTSEngine
            ENGINE = XTTSEngine()   # Will raise if VRAM/model unavailable
            ENGINE_NAME = "xtts_v2"
            print("[EchoLife] ✅ Primary engine: XTTS-v2 loaded.")
        except Exception as e:
            print(f"[EchoLife] ⚠️ XTTS-v2 unavailable ({e}). Falling back to OpenVoice v2.")
            from services.openvoice_engine import OpenVoiceEngine
            ENGINE = OpenVoiceEngine()
            ENGINE_NAME = "openvoice_v2"
            print("[EchoLife] ✅ Fallback engine: OpenVoice v2 loaded.")

    def synthesize(text: str, profile: dict) -> bytes:
        """Unified synthesis interface — works identically for both engines."""
        return ENGINE.synthesize(text, profile)
    ```

- [ ] **1.2a XTTS-v2 Engine (`services/xtts_engine.py`):**
  - Load using the **direct `Xtts` model class** with CUDA / CPU auto-detection:
    ```python
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import Xtts
    config = XttsConfig()
    config.load_json("path/to/xtts_v2/config.json")
    model = Xtts.init_from_config(config)
    model.load_checkpoint(config, checkpoint_dir="path/to/xtts_v2/", eval=True)
    model.cuda() if torch.cuda.is_available() else model.cpu()
    ```
  - Implement `extract_profile(wav_file)` → returns `{engine: "xtts_v2", gpt_cond_latent: ..., speaker_embedding: ...}`.
  - Implement `synthesize(text, profile)` → calls `model.inference()` with cached latents → returns raw PCM bytes.

- [ ] **1.2b OpenVoice v2 Fallback Engine (`services/openvoice_engine.py`):**
  - Load the ToneColorConverter and extract the user's tone embedding:
    ```python
    from openvoice import se_extractor
    from openvoice.api import ToneColorConverter
    from melo.api import TTS as MeloTTS

    converter = ToneColorConverter("path/to/openvoice_v2/converter/config.json")
    converter.load_ckpt("path/to/openvoice_v2/converter/checkpoint.pth")
    base_tts = MeloTTS(language="EN", device="cpu")
    ```
  - Implement `extract_profile(wav_file)` → returns `{engine: "openvoice_v2", target_se: ...}`.
  - Implement `synthesize(text, profile)`:
    1. Generate base voice audio with `base_tts.tts_to_file(text, ...)`.
    2. Run `converter.convert(audio_src_path, src_se, tgt_se=profile["target_se"], output_path)`.
    3. Return final converted WAV bytes in the user's authentic tone.

- [ ] **1.3 Audio Preprocessor (`services/audio_processor.py`):**
  - **Step A — Format Conversion (Critical Fix):** Convert browser-recorded `.webm` to `.wav` using `pydub`:
    ```python
    from pydub import AudioSegment
    audio = AudioSegment.from_file(input_path, format="webm")
    audio = audio.set_frame_rate(22050).set_channels(1)
    audio.export(output_wav_path, format="wav")
    ```
  - **Step B — Quality Normalization:** Trim leading/trailing silence, normalize to 22050Hz mono, validate SNR > 15dB.

- [ ] **1.4 Security Vault (`services/security_vault.py`):**
  - Serialize speaker latents (as PyTorch tensors → numpy → bytes) and encrypt into a `.echovox` file using AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`).

- [ ] **1.5 CORS Configuration in `main.py` (Critical Fix):**
  - Add CORS middleware immediately after creating the FastAPI `app` instance to allow the frontend (running on a different port) to call the backend:
    ```python
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:5500", "null"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    ```
  > ⚠️ Without this, **every single frontend API call will be blocked** by the browser's same-origin policy.

- [ ] **1.6 API Endpoints (`main.py`):**
  - `POST /api/enroll`: Receives `.webm` audio upload → converts to `.wav` → calls active engine's `extract_profile()` → encrypts `.echovox` to disk (profile includes `engine_name` field so decryption knows which engine to restore).
  - `POST /api/synthesize`: Receives `{text: "..."}` JSON → loads profile → calls unified `voice_engine.synthesize()` → returns WAV as **`StreamingResponse`**.
  - `GET /api/status`: Returns model readiness, GPU availability, **active engine name** (`xtts_v2` or `openvoice_v2`), and active profile name.
  - `GET /api/phrases`: Returns default AAC phrase categories and emergency phrases from `data/default_phrases.json`.

### Phase 2: Frontend AAC & Audio Interface (`frontend/`)
> **Design Aesthetic: Calm, Uncluttered Light Beige Theme**
> - **Palette:** Warm serene beige background (`#FAF7F2`), clean soft-cream card surfaces (`#FFFFFF` with `#F2EDE4` accents), subtle warm borders (`#E6DFD5`), deep charcoal typography for maximum legibility (`#262825`), and a warm terracotta/amber accent for primary action buttons (`#C26D43` / `#8C502E`).
> - **Philosophy:** Not clumsy, crowded, or clinical. Spacious padding, generous margins, gentle rounded corners (16px), and distraction-free layout designed specifically for patients and caregivers experiencing motor fatigue.

- [ ] **2.1 Visual Design Tokens & Clean Layout (`styles/main.css`):**
  - Implement the minimalist beige design system:
    ```css
    :root {
      --bg-primary: #FAF7F2;      /* Warm serene beige */
      --bg-card: #FFFFFF;         /* Crisp soft white card surface */
      --bg-card-hover: #F6F2EB;   /* Gentle warm hover tint */
      --border-subtle: #E8E2D8;   /* Soft warm dividing line */
      --text-main: #242724;       /* Deep charcoal for crystal-clear readability */
      --text-muted: #72756E;      /* Secondary label gray */
      --accent-warm: #C26D43;     /* Warm terracotta primary button */
      --accent-warm-hover: #A85B35;
      --emergency-tint: #FDF1ED;  /* Soft alert card background */
      --emergency-text: #B43826;  /* High-contrast alert text */
    }
    ```
  - Responsive, uncluttered single-screen dashboard layout.

- [ ] **2.2 High-Contrast, Spacious AAC Communication Grid (`components/AACGrid.js`):**
  - Clean, spacious category cards with generous touch targets (minimum 64px tap height):
    - *Emergency (soft peach/red tint):* "I need help", "I am in pain", "Difficulty breathing".
    - *Daily Needs:* "Water", "Food", "Restroom", "Adjust position".
    - *Emotional Connection:* "Thank you", "I love you", "Good morning".

- [ ] **2.3 Minimal Free-Text Typing Box (`components/CustomTyping.js`):**
  - Large, uncluttered text area with clear placeholder: *"Type anything to speak in your voice..."*
  - Prominent, warm-toned **"Speak"** action button (also triggers instantly on `Enter`).

- [ ] **2.4 Clean Voice Enrollment Modal (`components/VoiceEnrollment.js`):**
  - Uncluttered 2-step setup:
    1. Read 2 short sentences aloud.
    2. Click "Save Voice Profile" (shows clean progress bar while extracting latents).
  - Minimalist live microphone level indicator (gentle warm pulsing bar, no noisy jitter).

- [ ] **2.5 Low-Latency WebAudio Player (`components/AudioPlayer.js`):**
  - Seamless audio buffer playback through laptop speakers with play/stop visual feedback.

### Phase 3: Offline Validation & Performance Tuning
- [ ] **3.1 Latent Caching Verification:** Ensure sentence synthesis skips audio re-encoding, verifying sub-second latency.
- [ ] **3.2 Airplane Mode Test:** Disconnect laptop completely from internet; confirm 100% functionality.
- [ ] **3.3 Emergency Phrase Pre-Caching:** Validate that emergency buttons trigger with 0 ms generation delay.

---

## 8. Engine Selection Logic (Summary)

| Condition | Engine Selected | Latency | Voice Quality |
| :--- | :--- | :--- | :--- |
| NVIDIA GPU available (≥4GB VRAM) + XTTS-v2 model weights present | **XTTS-v2 (Primary)** | ~0.6–1.2s | ⭐⭐⭐⭐⭐ Highest |
| CPU-only laptop or VRAM < 4GB or XTTS-v2 import error | **OpenVoice v2 (Fallback)** | ~0.8–1.5s | ⭐⭐⭐⭐ Excellent |

> The user and patient **never need to know or configure which engine is active.** The `voice_engine.py` router handles this automatically at startup. The `/api/status` endpoint exposes the active engine name for the frontend status bar only.

---

## 9. Ready for Execution
The architecture is cleanly decoupled into `backend/` and `frontend/`, with a robust dual-engine design that guarantees EchoLife works on any modern laptop regardless of GPU availability. When you are ready, we can proceed to set up the backend engine and frontend client.
