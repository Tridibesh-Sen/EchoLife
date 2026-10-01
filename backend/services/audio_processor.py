import os
import io
import wave
import numpy as np
import soundfile as sf
from scipy import signal
from pathlib import Path
from backend.config import SAMPLE_RATE, CHANNELS, TEMP_DIR, MIN_AUDIO_DURATION_SEC

def get_ffmpeg_binary():
    """Finds ffmpeg from imageio_ffmpeg or system PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def convert_to_wav(input_path: Path, output_path: Path, target_sr: int = SAMPLE_RATE) -> Path:
    """
    Converts any audio file (WebM, OGG, MP3, WAV) into a standard 
    target_sr (22050Hz) mono 16-bit PCM WAV file.
    """
    ext = input_path.suffix.lower()

    # If it's already a standard WAV, try reading with soundfile directly
    if ext == ".wav":
        try:
            data, sr = sf.read(str(input_path), dtype="float32")
            return _resample_and_save(data, sr, output_path, target_sr)
        except Exception:
            pass  # Fall through to ffmpeg/pydub conversion

    # Try pydub / imageio_ffmpeg
    try:
        from pydub import AudioSegment
        ffmpeg_bin = get_ffmpeg_binary()
        if os.path.exists(ffmpeg_bin):
            AudioSegment.converter = ffmpeg_bin

        audio = AudioSegment.from_file(str(input_path))
        audio = audio.set_frame_rate(target_sr).set_channels(CHANNELS)
        audio.export(str(output_path), format="wav")
        return output_path
    except Exception as e:
        # Direct fallback via subprocess if imageio_ffmpeg exists
        import subprocess
        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(input_path),
            "-ar", str(target_sr),
            "-ac", str(CHANNELS),
            "-f", "wav",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Audio conversion failed: {result.stderr or e}")
        return output_path

def _resample_and_save(data: np.ndarray, orig_sr: int, output_path: Path, target_sr: int) -> Path:
    """Resamples float32 audio data to target_sr mono using torchaudio bandlimited sinc filters."""
    import torch
    import torchaudio.functional as F

    # Convert stereo to mono if necessary
    if data.ndim > 1:
        data = np.mean(data, axis=1)

    # Studio-grade bandlimited Kaiser sinc resampling (zero FFT noise)
    if orig_sr != target_sr:
        tensor_audio = torch.from_numpy(data).float().unsqueeze(0)
        resampled_tensor = F.resample(tensor_audio, orig_sr, target_sr, lowpass_filter_width=16)
        data = resampled_tensor.squeeze(0).numpy()

    # RMS normalization for clean, clear vocal presence
    rms = np.sqrt(np.mean(data**2))
    target_rms = 0.12  # Clean conversational speech level
    if rms > 1e-4:
        data = data * (target_rms / rms)
    data = np.clip(data, -0.95, 0.95)

    # Trim leading/trailing silence safely
    threshold = 0.015
    non_silent = np.where(np.abs(data) > threshold)[0]
    if len(non_silent) > 0:
        start_idx = int(max(0, int(non_silent[0]) - int(target_sr * 0.1)))
        end_idx = int(min(len(data), int(non_silent[-1]) + int(target_sr * 0.1)))
        data = data[start_idx:end_idx]

    sf.write(str(output_path), data, target_sr, subtype="PCM_16")
    return output_path

def validate_and_clean_audio(input_file_path: Path, output_file_name: str = "cleaned_reference.wav") -> dict:
    """
    Validates audio duration and quality, converting to standard 22050Hz mono WAV.
    Returns: {"clean_wav_path": Path, "duration_sec": float, "valid": bool, "error": str}
    """
    output_path = TEMP_DIR / output_file_name
    convert_to_wav(input_file_path, output_path, target_sr=SAMPLE_RATE)

    # Check resulting duration
    data, sr = sf.read(str(output_path), dtype="float32")
    duration = len(data) / sr

    if duration < MIN_AUDIO_DURATION_SEC:
        return {
            "clean_wav_path": output_path,
            "duration_sec": duration,
            "valid": False,
            "error": f"Recording too short ({duration:.1f}s). Please speak for at least {MIN_AUDIO_DURATION_SEC} seconds."
        }

    return {
        "clean_wav_path": output_path,
        "duration_sec": duration,
        "valid": True,
        "error": None
    }
