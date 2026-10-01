import os
import io
import json
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import CORS_ORIGINS, DATA_DIR, TEMP_DIR, ROOT_DIR
from backend.services.audio_processor import validate_and_clean_audio
from backend.services.security_vault import list_vault_profiles
from backend.services.voice_engine import router

app = FastAPI(
    title="EchoLife Voice Identity API",
    description="Privacy-First Lifelong Digital Voice Identity Engine for Laptop",
    version="1.0.0"
)

# Enable CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
async def get_status():
    """Returns the current engine status, hardware detection, and loaded voice profiles."""
    status_data = router.get_status()
    return JSONResponse(content=status_data)

@app.get("/api/phrases")
async def get_default_phrases():
    """Returns curated AAC phrase categories and emergency phrases."""
    phrases_file = DATA_DIR / "default_phrases.json"
    if not phrases_file.exists():
        raise HTTPException(status_code=404, detail="Default phrases configuration not found.")
    with open(phrases_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(content=data)

@app.get("/api/profiles")
async def get_profiles():
    """Lists all encrypted voice identities in the local vault."""
    profiles = list_vault_profiles()
    return JSONResponse(content={"profiles": profiles})

@app.post("/api/enroll")
async def enroll_voice(
    audio_file: UploadFile = File(...),
    profile_name: str = Form("default_user")
):
    """
    Uploads a 10–30s voice sample, cleans/converts it to 22050Hz mono WAV,
    extracts speaker latents, and saves an AES-256 encrypted .echovox profile.
    """
    clean_profile_name = "".join(c for c in profile_name if c.isalnum() or c in ("_", "-")).strip()
    if not clean_profile_name:
        clean_profile_name = "default_user"

    temp_input_path = TEMP_DIR / f"raw_upload_{clean_profile_name}_{audio_file.filename}"
    with open(temp_input_path, "wb") as f:
        content = await audio_file.read()
        f.write(content)

    try:
        # Validate and convert audio to clean standard WAV
        clean_result = validate_and_clean_audio(temp_input_path, f"clean_{clean_profile_name}.wav")
        if not clean_result["valid"]:
            raise HTTPException(status_code=400, detail=clean_result["error"])

        # Extract latents and save to AES-256 encrypted vault
        enrollment_result = router.enroll_voice(
            clean_wav_path=clean_result["clean_wav_path"],
            profile_name=clean_profile_name
        )

        return JSONResponse(content={
            "success": True,
            "message": f"Voice Identity '{clean_profile_name}' enrolled successfully!",
            "details": enrollment_result
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice enrollment failed: {str(e)}")
    finally:
        # Clean up temporary raw upload file
        if temp_input_path.exists():
            try:
                os.remove(temp_input_path)
            except Exception:
                pass

@app.post("/api/synthesize")
async def synthesize_speech(payload: dict):
    """
    Synthesizes custom text into natural speech in the user's authentic cloned voice.
    Payload: {"text": "...", "profile_name": "default_user", "language": "en"}
    Returns: Streaming audio/wav
    """
    text = payload.get("text", "").strip()
    profile_name = payload.get("profile_name", "default_user")
    language = payload.get("language", "en")

    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        wav_io = router.synthesize(text=text, profile_name=profile_name, language=language)
        return StreamingResponse(
            wav_io,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'inline; filename="echolife_speech.wav"',
                "X-EchoLife-Engine": router.active_engine_name or "standby"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech synthesis error: {str(e)}")

# Mount frontend directory for easy single-command web access
FRONTEND_DIR = ROOT_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    print("[EchoLife] Starting local server at http://127.0.0.1:8000 ...")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
