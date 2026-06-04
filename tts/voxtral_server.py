"""
JARVIS — Serveur TTS Voxtral (Mistral AI)
Port : 8001
Endpoint : POST /v1/audio/speech

Compatible avec le même format que Kokoro (port 8000) :
  {"text": "...", "voice": "fr_female|fr_male", "speed": 1.0}

Nécessite : MISTRAL_API_KEY dans .env
Installer  : pip install mistralai
"""
import io
import os
import sys
import logging

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

# Charger .env depuis la racine du projet (parent du dossier tts/)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
load_dotenv(os.path.join(_ROOT, ".env"))

# ── Configuration ──────────────────────────────────────────────
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
PORT = int(os.getenv("TTS_VOXTRAL_PORT", "8001"))
HOST = os.getenv("TTS_VOXTRAL_HOST", "0.0.0.0")

# Modèle Mistral Voxtral TTS
VOXTRAL_MODEL = os.getenv("VOXTRAL_MODEL", "voxtral-v0-2")

# Mapping nom de voix JARVIS → ID voix Mistral
# Voxtral supporte les voix françaises nativement
VOICE_MAP: dict[str, str] = {
    "fr_female": "fr_female",
    "fr_male":   "fr_male",
}
DEFAULT_VOICE = "fr_female"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("voxtral_server")

# ── App ────────────────────────────────────────────────────────
app = FastAPI(title="JARVIS Voxtral TTS", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpeechRequest(BaseModel):
    text: str
    voice: str = DEFAULT_VOICE
    speed: float = 1.0


@app.get("/health")
async def health():
    has_key = bool(MISTRAL_API_KEY)
    return {
        "status": "ok" if has_key else "degraded",
        "engine": "voxtral",
        "model": VOXTRAL_MODEL,
        "api_key_configured": has_key,
        "port": PORT,
    }


@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest):
    """Synthétise du texte en audio WAV via l'API Mistral Voxtral."""
    # Relire la clé depuis .env à chaque requête pour prendre en compte
    # les mises à jour faites via l'interface sans redémarrer le serveur
    load_dotenv(os.path.join(_ROOT, ".env"), override=True)
    api_key = os.getenv("MISTRAL_API_KEY", "")
    if not api_key:
        return JSONResponse(
            {"error": "MISTRAL_API_KEY non configurée. Ajoutez-la dans Paramètres → API"},
            status_code=503,
        )

    text = req.text.strip()
    if not text:
        return JSONResponse({"error": "Texte vide"}, status_code=400)

    voice = VOICE_MAP.get(req.voice, DEFAULT_VOICE)
    speed = max(0.5, min(2.0, req.speed))

    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)

        # Appel API Mistral TTS (Voxtral)
        response = client.audio.speech(
            model=VOXTRAL_MODEL,
            input=text,
            voice=voice,
        )

        # L'API retourne des bytes audio (WAV ou MP3)
        audio_bytes: bytes
        if hasattr(response, "read"):
            audio_bytes = response.read()
        elif hasattr(response, "content"):
            audio_bytes = response.content
        elif isinstance(response, bytes):
            audio_bytes = response
        else:
            # Stream iterator
            buf = io.BytesIO()
            for chunk in response:
                buf.write(chunk)
            audio_bytes = buf.getvalue()

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"X-TTS-Engine": "voxtral", "X-Voice": voice},
        )

    except ImportError:
        return JSONResponse(
            {"error": "Package mistralai manquant. Installez : pip install mistralai"},
            status_code=503,
        )
    except Exception as e:
        err = str(e)
        logger.error(f"Voxtral TTS error: {err}")
        if "401" in err or "Unauthorized" in err or "api_key" in err.lower():
            return JSONResponse(
                {"error": "Clé API Mistral invalide. Vérifiez MISTRAL_API_KEY dans .env"},
                status_code=401,
            )
        if "404" in err or "model" in err.lower():
            return JSONResponse(
                {"error": f"Modèle '{VOXTRAL_MODEL}' non trouvé. Vérifiez VOXTRAL_MODEL dans .env"},
                status_code=404,
            )
        return JSONResponse({"error": f"Erreur Voxtral: {err}"}, status_code=500)


if __name__ == "__main__":
    if not MISTRAL_API_KEY:
        print("⚠  AVERTISSEMENT: MISTRAL_API_KEY non configurée dans .env")
        print("   Voxtral TTS ne fonctionnera pas sans clé API Mistral.")
        print("   Ajoutez dans .env : MISTRAL_API_KEY=votre-cle")
        print()

    print(f"  Voxtral TTS Server démarré sur http://{HOST}:{PORT}")
    print(f"  Modèle : {VOXTRAL_MODEL}")
    print(f"  Voix disponibles : {list(VOICE_MAP.keys())}")
    print(f"  Endpoint : POST /v1/audio/speech")

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",
    )
