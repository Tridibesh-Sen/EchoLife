import os
import io
import json
import base64
import hashlib
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from backend.config import VAULT_SALT, DEFAULT_PASSPHRASE, PROFILES_DIR

def _derive_key(passphrase: str = DEFAULT_PASSPHRASE) -> bytes:
    """Derives a 256-bit AES key using PBKDF2HMAC with SHA-256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=VAULT_SALT,
        iterations=100_000,
    )
    return kdf.derive(passphrase.encode("utf-8"))

def encrypt_and_save_profile(profile_data: dict, profile_name: str, passphrase: str = DEFAULT_PASSPHRASE) -> Path:
    """
    Encrypts a voice identity profile (including latents/embeddings) using AES-256-GCM
    and stores it as an encrypted `.echovox` file in the local storage directory.
    """
    key = _derive_key(passphrase)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM

    # Serialize payload to binary using torch / pickle
    import pickle
    raw_payload = pickle.dumps(profile_data)

    # Encrypt (ciphertext includes 128-bit authentication tag)
    ciphertext = aesgcm.encrypt(nonce, raw_payload, associated_data=profile_name.encode("utf-8"))

    # File format: [12 bytes nonce] + [ciphertext + tag]
    output_path = PROFILES_DIR / f"{profile_name}.echovox"
    with open(output_path, "wb") as f:
        f.write(nonce)
        f.write(ciphertext)

    return output_path

def load_and_decrypt_profile(profile_name: str, passphrase: str = DEFAULT_PASSPHRASE) -> dict:
    """
    Reads and decrypts a `.echovox` profile from the local storage directory.
    Returns the deserialized voice identity dictionary.
    """
    import pickle

    file_path = PROFILES_DIR / f"{profile_name}.echovox"
    if not file_path.exists():
        # Check without extra extension
        alt_path = PROFILES_DIR / profile_name
        if alt_path.exists():
            file_path = alt_path
        else:
            raise FileNotFoundError(f"Voice profile '{profile_name}' not found in vault.")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    if len(file_bytes) < 28:
        raise ValueError("Corrupted profile: file size too small.")

    nonce = file_bytes[:12]
    ciphertext = file_bytes[12:]

    key = _derive_key(passphrase)
    aesgcm = AESGCM(key)

    # Decrypt and verify tag
    name_for_aad = file_path.stem
    raw_payload = aesgcm.decrypt(nonce, ciphertext, associated_data=name_for_aad.encode("utf-8"))
    profile_data = pickle.loads(raw_payload)
    return profile_data

def list_vault_profiles() -> list:
    """Lists all available encrypted voice identities in the local vault."""
    profiles = []
    for f in PROFILES_DIR.glob("*.echovox"):
        stat = f.stat()
        profiles.append({
            "name": f.stem,
            "filename": f.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    return profiles
