# EchoLife — Privacy-First Lifelong Digital Voice Identity

EchoLife is a 100% offline, privacy-first assistive voice identity platform designed for people facing progressive speech loss (ALS, stroke, Parkinson's, laryngeal cancer). 

It captures a short 10–20 second voice sample, extracts a permanent digital voice identity (pitch, timbre, resonance), encrypts it locally with **AES-256**, and allows the user to type or tap AAC phrases to speak in their **authentic original voice** forever.

---

## 📁 Project Architecture

The codebase is organized into two primary folders:

```
d:/Echolife/
├── start.bat                                  # One-click Windows launcher
├── EchoLife_Complete_Proposal.pdf             # Original competition proposal
├── EchoLife_Implementation_Plan_and_Validation.md # Master plan & technical validation
│
├── backend/                                   # All AI, ML, Audio & Security Services
│   ├── requirements.txt                       # Python dependencies
│   ├── config.py                              # Audio configs, directory paths, encryption salt
│   ├── main.py                                # FastAPI app & REST endpoints
│   ├── services/
│   │   ├── voice_engine.py                    # Master Router: XTTS-v2 primary + OpenVoice fallback
│   │   ├── xtts_engine.py                     # Coqui XTTS-v2 zero-shot cloning & latent inference
│   │   ├── openvoice_engine.py                # OpenVoice v2 ToneColorConverter fallback
│   │   ├── audio_processor.py                 # Resampling, 22050Hz mono, silence trimming, SNR
│   │   └── security_vault.py                  # AES-256-GCM hardware-bound profile encryption
│   ├── storage/
│   │   ├── profiles/                          # Encrypted .echovox voice vaults
│   │   ├── cache/                             # Pre-synthesized emergency phrase WAVs
│   │   └── temp/                              # Temporary audio conversion buffers
│   └── data/
│       └── default_phrases.json               # AAC categories (Emergency, Daily Needs, Family)
│
└── frontend/                                  # Calm, Uncluttered Light Beige AAC Interface
    ├── index.html                             # Single-page accessible AAC dashboard
    ├── styles/
    │   └── main.css                           # Serene beige palette (#FAF7F2), terracotta accents
    └── js/
        ├── audio.js                           # 16-bit PCM WAV recorder & WebAudio player
        ├── api.js                             # Localhost:8000 REST client
        └── app.js                             # AAC phrase cards, free typing, voice wizard
```

---

## 🚀 Quick Start (Windows)

### Option A: One-Click Launch
Double-click `start.bat` in the root folder. It will verify Python 3.11, launch the FastAPI server, and open the web dashboard at `http://127.0.0.1:8000`.

### Option B: Manual Terminal Launch
1. **Install Core Dependencies:**
   ```bash
   py -3.11 -m pip install -r backend/requirements.txt
   ```
2. **For NVIDIA RTX 4050 GPU Acceleration:**
   ```bash
   py -3.11 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
3. **Run Server:**
   ```bash
   py -3.11 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
4. **Open Browser:** Visit `http://127.0.0.1:8000`.

---

## 🎙 How It Works in 3 Steps
1. **Voice Banking:** Click **"🎙 Preserve New Voice"**, read the 15-second guided rainbow passage, and click **"Lock into Vault & Activate"**.
2. **AAC Quick Taps:** Click any phrase card (*"I need water"*, *"I love you so much"*, *"I need help"*) to immediately speak aloud.
3. **Free Text:** Type any custom message into the bottom bar and press **Enter** to speak in your authentic cloned voice.
