import os
from pathlib import Path

# Base Paths
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
STORAGE_DIR = BACKEND_DIR / "storage"
PROFILES_DIR = STORAGE_DIR / "profiles"
CACHE_DIR = STORAGE_DIR / "cache"
TEMP_DIR = STORAGE_DIR / "temp"
DATA_DIR = BACKEND_DIR / "data"

# Ensure directories exist
for folder in [STORAGE_DIR, PROFILES_DIR, CACHE_DIR, TEMP_DIR, DATA_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Audio Configuration
SAMPLE_RATE = 22050  # Standard XTTS-v2 sample rate
CHANNELS = 1         # Mono
DEFAULT_LANGUAGE = "en"
MIN_AUDIO_DURATION_SEC = 5.0
MAX_AUDIO_DURATION_SEC = 35.0

# Master Vault Encryption Key (Derivation salt & defaults)
VAULT_SALT = b"EchoLife_Lifelong_Voice_Vault_v1_2026"
DEFAULT_PASSPHRASE = "echolife-device-bound-secure-key"

# Hardware / Device Selection
# Automatically checked at runtime in engines
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "null"  # Allows opening frontend directly via file://
]
