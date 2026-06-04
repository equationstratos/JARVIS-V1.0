"""
JARVIS — Serveur TTS Voxtral (Mistral AI)
Port : 8001 — utilise httpx directement (Python 3.14 compat)
"""
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

PORT  = int(os.getenv("TTS_VOXTRAL_PORT", "8001"))
HOST  = os.getenv("TTS_VOXTRAL_HOST", "0.0.0.0")
VOXTRAL_MODEL = os.getenv("VOXTRAL_MODEL", "voxtral-mini-tts-latest")
MISTRAL_BASE  = "https://api.mistral.ai/v1"

# Cache des voix chargées depuis l'API
_voices_cache: list = []

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("voxtral_server")

app = FastAPI(title="JARVIS Voxtral TTS", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class SpeechRequest(BaseModel):
    text: str
    voice: str = "en_paul_neutral"
    speed: float = 1.0


def _get_key() -> str:
    load_dotenv(os.path.join(_ROOT, ".env"), override=True)
    return os.getenv("MISTRAL_API_KEY", "")


async def _fetch_all_voices(api_key: str) -> list:
    """Récupère toutes les voix disponibles depuis l'API Mistral."""
    global _voices_cache
    if _voices_cache:
        return _voices_cache
    voices = []
    page = 1
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            r = await client.get(
                f"{MISTRAL_BASE}/audio/voices",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"page": page, "page_size": 50},
            )
            if r.status_code != 200:
                break
            data = r.json()
            items = data.get("items", [])
            voices.extend(items)
            if page >= data.get("total_pages", 1):
                break
            page += 1
    _voices_cache = voices
    return voices


@app.get("/health")
async def health():
    key = _get_key()
    return {"status": "ok" if key else "degraded", "engine": "voxtral",
            "model": VOXTRAL_MODEL, "api_key_configured": bool(key), "port": PORT}


@app.get("/voices")
async def list_voices():
    """Retourne toutes les voix Mistral disponibles."""
    api_key = _get_key()
    if not api_key:
        return JSONResponse({"error": "MISTRAL_API_KEY manquante"}, status_code=503)
    try:
        voices = await _fetch_all_voices(api_key)
        return {"voices": [{"slug": v["slug"], "name": v["name"],
                            "gender": v["gender"], "languages": v["languages"]} for v in voices]}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest):
    api_key = _get_key()
    if not api_key:
        return JSONResponse({"error": "MISTRAL_API_KEY non configurée"}, status_code=503)
    text = req.text.strip()
    if not text:
        return JSONResponse({"error": "Texte vide"}, status_code=400)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{MISTRAL_BASE}/audio/speech",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": VOXTRAL_MODEL, "input": text, "voice_id": req.voice, "response_format": "mp3"},
            )
        if resp.status_code == 401:
            return JSONResponse({"error": "Clé API Mistral invalide"}, status_code=401)
        if resp.status_code != 200:
            return JSONResponse({"error": f"Mistral API {resp.status_code}: {resp.text}"}, status_code=502)

        # L'API Mistral retourne {"audio_data": "<base64>"} au lieu de bytes directs
        import base64, json as _json
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            data = resp.json()
            audio_b64 = data.get("audio_data") or data.get("audio") or data.get("data", "")
            audio_bytes = base64.b64decode(audio_b64)
        else:
            audio_bytes = resp.content

        return Response(content=audio_bytes, media_type="audio/mpeg",
                        headers={"X-TTS-Engine": "voxtral", "X-Voice": req.voice})
    except httpx.TimeoutException:
        return JSONResponse({"error": "Timeout Mistral API"}, status_code=504)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    print(f"  Voxtral TTS Server sur http://{HOST}:{PORT}")
    print(f"  Modèle : {VOXTRAL_MODEL}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
