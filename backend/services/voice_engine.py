import os
import io
import time
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from backend.services.security_vault import (
    encrypt_and_save_profile,
    load_and_decrypt_profile,
    list_vault_profiles
)
from backend.config import CACHE_DIR

class VoiceEngineRouter:
    """
    Unified Voice Engine Router.
    Prioritizes Coqui XTTS-v2 (NVIDIA GPU / CPU), with automatic fallback to OpenVoice v2.
    Maintains an in-memory cache of decrypted speaker latents for sub-second synthesis.
    """
    def __init__(self):
        self.active_engine = None
        self.active_engine_name = None
        self.engine_error = None
        self.cached_profiles = {}  # In-memory decrypted latents: {profile_name: profile_data}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._init_engine()

    def _init_engine(self):
        """Attempts to initialize XTTS-v2 first, falling back to OpenVoice v2."""
        # 1. Try XTTS-v2
        try:
            print("[EchoLife Router] Attempting to load primary engine: XTTS-v2...")
            from backend.services.xtts_engine import XTTSEngine
            self.active_engine = XTTSEngine(use_gpu=(self.device == "cuda"))
            self.active_engine_name = "xtts_v2"
            print(f"[EchoLife Router] ✅ Primary engine XTTS-v2 active on {self.device}.")
            return
        except Exception as e:
            print(f"[EchoLife Router] XTTS-v2 initialization skipped/unavailable: {e}")
            self.engine_error = str(e)

        # 2. Try OpenVoice v2
        try:
            print("[EchoLife Router] Attempting to load fallback engine: OpenVoice v2...")
            from backend.services.openvoice_engine import OpenVoiceEngine
            self.active_engine = OpenVoiceEngine(use_gpu=(self.device == "cuda"))
            self.active_engine_name = "openvoice_v2"
            print(f"[EchoLife Router] ✅ Fallback engine OpenVoice v2 active on {self.device}.")
            return
        except Exception as e:
            print(f"[EchoLife Router] OpenVoice v2 unavailable: {e}")

        # 3. Development / Standby Engine (allows testing UI & API before large weights download)
        print("[EchoLife Router] Running in Standby Mock mode (awaiting model weights download).")
        self.active_engine_name = "standby_ready"

    def get_status(self) -> dict:
        """Returns the current system health, hardware status, and active engine."""
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None (CPU Mode)"
        vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024) if torch.cuda.is_available() else 0

        profiles = list_vault_profiles()
        return {
            "status": "ready",
            "active_engine": self.active_engine_name,
            "device": self.device,
            "gpu_name": gpu_name,
            "vram_mb": vram_mb,
            "installed_profiles": [p["name"] for p in profiles],
            "cached_profiles_in_memory": list(self.cached_profiles.keys()),
            "last_error": self.engine_error
        }

    def enroll_voice(self, clean_wav_path: Path, profile_name: str = "default_user") -> dict:
        """
        Extracts speaker latents from reference audio, stores them in memory,
        and saves an encrypted `.echovox` profile in the hardware vault.
        """
        start_time = time.time()

        if self.active_engine:
            profile_data = self.active_engine.extract_profile(clean_wav_path)
        else:
            # Standby profile generator
            data, sr = sf.read(str(clean_wav_path), dtype="float32")
            profile_data = {
                "engine": "standby_ready",
                "sample_rate": sr,
                "duration": len(data) / sr,
                "timestamp": time.time()
            }

        # Cache in memory for instant reuse
        self.cached_profiles[profile_name] = profile_data

        # Save encrypted file to vault
        vault_path = encrypt_and_save_profile(profile_data, profile_name)
        elapsed = time.time() - start_time

        return {
            "profile_name": profile_name,
            "engine_used": self.active_engine_name,
            "vault_file": vault_path.name,
            "enrollment_time_sec": round(elapsed, 2)
        }

    def get_or_load_profile(self, profile_name: str = "default_user") -> dict:
        """Returns profile from memory cache, or decrypts it from the vault."""
        if profile_name in self.cached_profiles:
            return self.cached_profiles[profile_name]

        # Decrypt from vault
        profile_data = load_and_decrypt_profile(profile_name)
        self.cached_profiles[profile_name] = profile_data
        return profile_data

    def synthesize(self, text: str, profile_name: str = "default_user", language: str = "en") -> io.BytesIO:
        """
        Synthesizes text using precomputed voice latents.
        Checks emergency phrase cache first for 0ms instant response.
        """
        # 1. Check pre-synthesized emergency cache
        cache_key = f"{profile_name}_{hash(text.strip().lower())}.wav"
        cached_file = CACHE_DIR / cache_key
        if cached_file.exists():
            wav_io = io.BytesIO()
            with open(cached_file, "rb") as f:
                wav_io.write(f.read())
            wav_io.seek(0)
            return wav_io

        # 2. Load voice identity profile
        profile_data = self.get_or_load_profile(profile_name)

        # 3. Synthesize via active engine
        if self.active_engine and hasattr(self.active_engine, "synthesize"):
            return self.active_engine.synthesize(text, profile_data, language=language)

        # 4. Fallback speech tone if weights are in standby
        wav_io = io.BytesIO()
        sample_rate = 22050
        duration = max(1.0, len(text.split()) * 0.4)
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        # Gentle melodic chord to indicate standby speech synthesis
        audio_wave = (0.15 * np.sin(2 * np.pi * 330 * t) + 0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        sf.write(wav_io, audio_wave, sample_rate, format="WAV", subtype="PCM_16")
        wav_io.seek(0)
        return wav_io

# Singleton Router instance
router = VoiceEngineRouter()
