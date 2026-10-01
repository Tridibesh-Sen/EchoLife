import os
import io
import torch
import soundfile as sf
import numpy as np
from pathlib import Path

class XTTSEngine:
    def __init__(self, use_gpu: bool = None):
        """
        Initializes the XTTS-v2 engine with CUDA acceleration if available.
        """
        if use_gpu is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"

        print(f"[EchoLife XTTS-v2] Initializing on device: {self.device}...")
        self.model = None
        self.tts = None
        self._load_model()

    def _load_model(self):
        """Loads XTTS-v2 using Coqui TTS manager to ensure automatic weight resolution."""
        try:
            from TTS.api import TTS
            # Loading via TTS manages download and checkpoint placement cleanly
            is_gpu = (self.device == "cuda")
            self.tts = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=False,
                gpu=is_gpu
            )
            # Reference the underlying Xtts model instance
            self.model = self.tts.synthesizer.tts_model
            print(f"[EchoLife XTTS-v2] ✅ Successfully loaded XTTS-v2 on {self.device}!")
        except Exception as e:
            # Fallback to direct Xtts class if manual checkpoint path exists
            print(f"[EchoLife XTTS-v2] Standard loader error: {e}. Trying direct Xtts import...")
            from TTS.tts.configs.xtts_config import XttsConfig
            from TTS.tts.models.xtts import Xtts
            from TTS.utils.manage import ModelManager

            manager = ModelManager()
            model_path, config_path, _ = manager.download_model("tts_models/multilingual/multi-dataset/xtts_v2")
            config = XttsConfig()
            config.load_json(config_path)
            self.model = Xtts.init_from_config(config)
            self.model.load_checkpoint(config, checkpoint_dir=model_path, eval=True)
            if self.device == "cuda":
                self.model.cuda()
            else:
                self.model.cpu()
            print(f"[EchoLife XTTS-v2] ✅ Loaded via direct Xtts checkpoint on {self.device}!")

    def extract_profile(self, wav_path: Path) -> dict:
        """
        Extracts speaker conditioning latents (gpt_cond_latent and speaker_embedding)
        from a clean 22050Hz mono WAV reference file.
        """
        if self.model is None:
            raise RuntimeError("XTTS-v2 model is not loaded.")

        # Read audio length to use maximum reference conditioning
        info = sf.info(str(wav_path))
        cond_len = min(30, max(12, int(info.duration)))

        with torch.no_grad():
            gpt_cond_latent, speaker_embedding = self.model.get_conditioning_latents(
                audio_path=[str(wav_path)],
                max_ref_length=30,
                gpt_cond_len=cond_len,
                gpt_cond_chunk_len=6,
                sound_norm_refs=True
            )

        # Move to CPU for serialization / saving in vault
        return {
            "engine": "xtts_v2",
            "gpt_cond_latent": gpt_cond_latent.detach().cpu(),
            "speaker_embedding": speaker_embedding.detach().cpu(),
            "device_created": self.device
        }

    def synthesize(self, text: str, profile_data: dict, language: str = "en") -> io.BytesIO:
        """
        Synthesizes text into high-fidelity speech using precomputed speaker latents.
        Returns a BytesIO buffer containing the standard 24000Hz 16-bit PCM WAV.
        """
        if self.model is None:
            raise RuntimeError("XTTS-v2 model is not loaded.")

        gpt_cond_latent = profile_data["gpt_cond_latent"].to(self.device)
        speaker_embedding = profile_data["speaker_embedding"].to(self.device)

        with torch.no_grad():
            out = self.model.inference(
                text=text,
                language=language,
                gpt_cond_latent=gpt_cond_latent,
                speaker_embedding=speaker_embedding,
                temperature=0.25,        # Low temperature strictly preserves user timbre & accent
                length_penalty=1.0,
                repetition_penalty=5.0,  # Prevents robotic stuttering and noise
                top_k=50,
                top_p=0.85,
                enable_text_splitting=True
            )

        audio_np = out["wav"]
        # Convert to 16-bit PCM WAV in memory
        wav_io = io.BytesIO()
        sf.write(wav_io, audio_np, 24000, format="WAV", subtype="PCM_16")
        wav_io.seek(0)
        return wav_io
