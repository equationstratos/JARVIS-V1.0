"""
JARVIS — Serveur TTS Voxtral (Mistral AI)
Port : 8001
Endpoint : POST /v1/audio/speech

Utilise httpx directement (pas le SDK mistralai) pour compatibilité Python 3.14+
Compatible avec le même format que Kokoro (port 8000) :
  {"text": "...", "voice": "fr_female|fr_male", "speed": 1.0}

Nécessite : MISTRAL_API_KEY dans .env
"""
import io
import os
import logging

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
load_dotenv(os.path.join(_ROOT, ".env"))

# ── Configuration ──────────────────────────────────────────────
PORT  = int(os.getenv("TTS_VOXTRAL_PORT", "8001"))
HOST  = os.getenv("TTS_VOXTRAL_HOST", "0.0.0.0")
# Modèles Mistral TTS connus : voxtral-mini-2507, mistral-tts-latest
VOXTRAL_MODEL = os.getenv("VOXTRAL_MODEL", "voxtral-mini-tts-latest")
MISTRAL_TTS_URL = "https://api.mistral.ai/v1/audio/speech"

VOICE_MAP = {"fr_female": "fr_female", "fr_male": "fr_male"}
DEFAULT_VOICE = "fr_female"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("voxtral_server")

app = FastAPI(title="JARVIS Voxtral TTS", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class SpeechRequest(BaseModel):
    text: str
    voice: str = "fr_female"
    speed: float = 1.0


def _get_key() -> str:
    load_dotenv(os.path.join(_ROOT, ".env"), override=True)
    return os.getenv("MISTRAL_API_KEY", "")


@app.get("/health")
async def health():
    key = _get_key()
    return {
        "status": "ok" if key else "degraded",
        "engine": "voxtral",
        "model": VOXTRAL_MODEL,
        "api_key_configured": bool(key),
        "port": PORT,
    }


@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest):
    api_key = _get_key()
    if not api_key:
        return JSONResponse(
            {"error": "MISTRAL_API_KEY non configurée. Ajoutez-la dans Paramètres → API"},
            status_code=503,
        )

    text = req.text.strip()
    if not text:
        return JSONResponse({"error": "Texte vide"}, status_code=400)

    voice = VOICE_MAP.get(req.voice, DEFAULT_VOICE)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                MISTRAL_TTS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": VOXTRAL_MODEL, "input": text, "voice": voice},
            )

        if resp.status_code == 401:
            return JSONResponse({"error": "Clé API Mistral invalide"}, status_code=401)
        if resp.status_code == 404:
            return JSONResponse(
                {"error": f"Modèle '{VOXTRAL_MODEL}' introuvable. Vérifiez VOXTRAL_MODEL dans .env"},
                status_code=404,
            )
        if resp.status_code != 200:
            return JSONResponse({"error": f"Mistral API erreur {resp.status_code}: {resp.text}"}, status_code=502)

        content_type = resp.headers.get("content-type", "audio/mpeg")
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={"X-TTS-Engine": "voxtral", "X-Voice": voice},
        )

    except httpx.TimeoutException:
        return JSONResponse({"error": "Timeout Mistral API (>30s)"}, status_code=504)
    except Exception as e:
        logger.error(f"Voxtral TTS error: {e}")
        return JSONResponse({"error": f"Erreur: {str(e)}"}, status_code=500)


if __name__ == "__main__":
    key = _get_key()
    if not key:
        print("⚠  AVERTISSEMENT: MISTRAL_API_KEY non configurée dans .env")
    print(f"  Voxtral TTS Server démarré sur http://{HOST}:{PORT}")
    print(f"  Modèle : {VOXTRAL_MODEL}")
    print(f"  Voix : {list(VOICE_MAP.keys())}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
