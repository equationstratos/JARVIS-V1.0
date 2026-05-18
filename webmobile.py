#!/usr/bin/env python3
"""
JARVIS Mobile Web Server
Simple proxy that provides clean, conversational responses in natural language
"""

import os
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn
import httpx
from dotenv import load_dotenv, set_key

# Load environment
load_dotenv()

app = FastAPI(title="JARVIS Mobile Web")

# ── CORS Configuration ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
JARVIS_BACKEND = os.getenv("JARVIS_BACKEND", "http://127.0.0.1:8501")
TTS_BACKEND = os.getenv("TTS_BACKEND", "http://127.0.0.1:8000")

def find_config_file():
    """Search for models_config.json in multiple common locations."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "interfaces" / "models_config.json",
        here.parent / "interfaces" / "models_config.json",
        here / "models_config.json",
        Path.cwd() / "interfaces" / "models_config.json",
        Path.cwd() / "models_config.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

def find_mobile_dir():
    """Search for the mobile directory containing HTML files."""
    here = Path(__file__).resolve().parent
    candidates = [here / "mobile", here.parent / "mobile", here, Path.cwd() / "mobile"]
    for c in candidates:
        if c.exists() and any(c.glob("index*.html")):
            return c
    return here / "mobile"

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = find_config_file()
ENV_FILE = PROJECT_ROOT / ".env"
MOBILE_DIR = find_mobile_dir()

print(f"📁 Project root: {PROJECT_ROOT}")
print(f"📄 Config: {CONFIG_FILE} {'✓' if CONFIG_FILE.exists() else '✗ NOT FOUND'}")
print(f"📱 Mobile: {MOBILE_DIR} {'✓' if MOBILE_DIR.exists() else '✗ NOT FOUND'}")

def load_models_config():
    """Load models from config file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Could not load models config: {e}")
        return {"models": {}, "api_keys": {}}


class JarvisProxy:
    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        self.client = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=90.0)
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    def _clean_response(self, raw_response: str) -> str:
        """Clean and format the response for natural language"""
        try:
            # Try to parse as JSON first
            if raw_response.startswith('{'):
                data = json.loads(raw_response)
                # Extract answer from various possible formats
                if isinstance(data, dict):
                    # If it's {"name": "...", "answer": "..."} format
                    if "answer" in data:
                        return data["answer"]
                    # If it's {"response": "..."} format
                    if "response" in data:
                        response = data["response"]
                        # If response is also JSON, parse it
                        if isinstance(response, str) and response.startswith('{'):
                            try:
                                parsed = json.loads(response)
                                return parsed.get("answer", response)
                            except:
                                return response
                        return response
                    # Return the whole dict as string if nothing matches
                    return json.dumps(data, ensure_ascii=False)
        except json.JSONDecodeError:
            pass

        # If not JSON, return as-is (it's already natural language)
        return raw_response

    async def chat(self, query: str, model: str = "ollama/llama3") -> dict:
        """Send chat request to JARVIS backend"""
        try:
            form_data = {
                "query": query,
                "model": model,
            }

            response = await self.client.post(
                f"{self.backend_url}/chat",
                data=form_data,
                timeout=90.0
            )

            if response.status_code == 200:
                data = response.json()
                clean_response = self._clean_response(data.get("response", "No response"))
                return {
                    "success": True,
                    "response": clean_response,
                    "latency": data.get("latency", "Unknown"),
                    "model": model,
                }
            else:
                return {
                    "success": False,
                    "response": f"Server error: {response.status_code}",
                    "model": model,
                }
        except Exception as e:
            return {
                "success": False,
                "response": f"Connection error: {str(e)}",
                "model": model,
            }

    async def chat_stream(self, query: str, model: str = "ollama/llama3"):
        """Stream chat response from JARVIS backend"""
        try:
            form_data = {
                "query": query,
                "model": model,
            }

            async with self.client.stream(
                "POST",
                f"{self.backend_url}/chat/stream",
                data=form_data,
                timeout=90.0
            ) as response:
                if response.status_code == 200:
                    full_text = ""
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if data.get("type") == "token":
                                    token = data.get("data", "")
                                    full_text += token
                                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
                                elif data.get("type") == "done":
                                    clean = self._clean_response(full_text)
                                    yield f"data: {json.dumps({'type': 'done', 'data': clean})}\n\n"
                                    return
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"


# ── Routes ──

@app.get("/health")
async def health():
    """Health check"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{JARVIS_BACKEND}/health", timeout=5.0)
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "backend": JARVIS_BACKEND,
                    "mode": "mobile-proxy",
                }
    except:
        pass

    return {
        "status": "unhealthy",
        "backend": JARVIS_BACKEND,
        "mode": "mobile-proxy",
    }


@app.post("/chat")
async def chat(request: Request):
    """Chat endpoint with natural language responses"""
    form = await request.form()
    query = form.get("query", "").strip()
    model = form.get("model", "ollama/llama3")

    if not query:
        return JSONResponse({"error": "Empty query"}, status_code=400)

    async with JarvisProxy(JARVIS_BACKEND) as proxy:
        result = await proxy.chat(query, model)

        if result["success"]:
            return JSONResponse({
                "response": result["response"],
                "latency": result["latency"],
                "model": model,
            })
        else:
            return JSONResponse(
                {"error": result["response"]},
                status_code=500
            )


@app.post("/chat/stream")
async def chat_stream(request: Request):
    """Streaming chat endpoint"""
    form = await request.form()
    query = form.get("query", "").strip()
    model = form.get("model", "ollama/llama3")

    if not query:
        return JSONResponse({"error": "Empty query"}, status_code=400)

    async def event_generator():
        async with JarvisProxy(JARVIS_BACKEND) as proxy:
            async for event in proxy.chat_stream(query, model):
                yield event
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@app.get("/models")
async def get_models():
    """List available models from config"""
    config = load_models_config()
    return JSONResponse(config.get("models", {}))


@app.get("/api-keys")
async def get_api_keys():
    """Get masked API keys status"""
    config = load_models_config()
    keys_status = {}

    for key_name in config.get("api_keys", {}).keys():
        env_value = os.getenv(key_name, "")
        if env_value:
            # Mask the key
            masked = env_value[:4] + "..." + env_value[-4:] if len(env_value) > 8 else "***"
            keys_status[key_name] = {"configured": True, "value": masked}
        else:
            keys_status[key_name] = {"configured": False, "value": ""}

    return JSONResponse(keys_status)


@app.post("/api-keys")
async def set_api_keys(request: Request):
    """Configure API keys"""
    try:
        body = await request.json()

        # Update .env file
        for key_name, key_value in body.items():
            if key_value and not key_value.startswith("*"):
                # Set in environment
                os.environ[key_name] = key_value
                # Set in .env file
                set_key(str(ENV_FILE), key_name, key_value)

        return JSONResponse({
            "success": True,
            "message": "API keys updated successfully"
        })
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=400
        )


# ── TTS Proxy ──

@app.post("/tts")
async def tts_proxy(request: Request):
    """Proxy TTS requests to the Kokoro server on port 8000."""
    try:
        body = await request.json()
        text = (body.get("text") or "").strip()
        if not text:
            return JSONResponse({"error": "Empty text"}, status_code=400)
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{TTS_BACKEND}/v1/audio/speech",
                json={
                    "text": text,
                    "voice": body.get("voice", "ff_siwis"),
                    "speed": float(body.get("speed", 1.0)),
                },
            )
            if r.status_code == 200:
                return Response(content=r.content, media_type="audio/wav")
            return JSONResponse({"error": f"TTS backend error {r.status_code}: {r.text[:200]}"}, status_code=502)
    except httpx.ConnectError:
        return JSONResponse({"error": f"TTS backend unreachable at {TTS_BACKEND}"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Static file serving (HTML interface) ──

@app.get("/")
async def root():
    """Redirect root to the default UI (Glassmorphism)"""
    return RedirectResponse(url="/app", status_code=302)

@app.get("/app")
async def serve_app():
    """Serve the default web UI (10 themes - Ultra)"""
    for name in ("index-ultra.html", "index-v3.html", "index.html", "index-v2.html", "index-v1.html"):
        f = MOBILE_DIR / name
        if f.exists():
            return FileResponse(f)
    return JSONResponse({"error": "No HTML interface found"}, status_code=404)

@app.get("/v1")
async def serve_v1():
    f = MOBILE_DIR / "index-v1.html"
    if f.exists(): return FileResponse(f)
    return JSONResponse({"error": "index-v1.html not found"}, status_code=404)

@app.get("/v2")
async def serve_v2():
    f = MOBILE_DIR / "index-v2.html"
    if f.exists(): return FileResponse(f)
    return JSONResponse({"error": "index-v2.html not found"}, status_code=404)

@app.get("/v3")
async def serve_v3():
    f = MOBILE_DIR / "index-v3.html"
    if f.exists(): return FileResponse(f)
    return JSONResponse({"error": "index-v3.html not found"}, status_code=404)

@app.get("/ultra")
async def serve_ultra():
    f = MOBILE_DIR / "index-ultra.html"
    if f.exists(): return FileResponse(f)
    return JSONResponse({"error": "index-ultra.html not found"}, status_code=404)

# Mount the entire mobile/ directory for asset serving
if MOBILE_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(MOBILE_DIR)), name="static")


if __name__ == "__main__":
    print(f"🚀 JARVIS Mobile Web Server")
    print(f"📍 Backend: {JARVIS_BACKEND}")
    print(f"🌐 Server: http://0.0.0.0:3001")
    print()
    print("🎨 Web UI (open in browser):")
    print("  http://127.0.0.1:3001/        → default (10 themes with selector)")
    print("  http://127.0.0.1:3001/ultra   → 10 integrated themes")
    print("  http://127.0.0.1:3001/v1      → iOS style")
    print("  http://127.0.0.1:3001/v2      → Material Design 3")
    print("  http://127.0.0.1:3001/v3      → Glassmorphism")
    print()
    print("🔌 API Endpoints:")
    print("  POST /chat         - Send a message")
    print("  POST /chat/stream  - Stream a message")
    print("  POST /tts          - Text-to-speech (proxy to Kokoro :8000)")
    print("  GET  /health       - Check health")
    print("  GET  /models       - List models")
    print("  GET  /api-keys     - Check API keys")
    print("  POST /api-keys     - Set API keys")
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3001,
        log_level="info",
    )
