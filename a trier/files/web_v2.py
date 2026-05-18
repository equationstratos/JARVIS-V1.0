"""
JARVIS Web Server — version optimisée

Optimisations clés :
- Streaming SSE (Server-Sent Events) sur /chat/stream
- Lecture de fichiers en parallèle (asyncio.gather)
- Lifespan FastAPI pour init unique + cleanup propre
- Connexion HTTP keep-alive partagée pour litellm
- Headers de cache statiques pour le frontend
- Endpoint /health pour monitoring
"""
import os
import sys
import json
import time
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional

# Path setup
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import (
    FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import httpx
from dotenv import load_dotenv
import litellm

from core.orchestrator import Orchestrator
from utils.shell_utils import execute_shell_async

load_dotenv(os.path.join(project_root, ".env"))


# ── Lifespan : init/cleanup global ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pool HTTP partagé pour litellm (évite handshake TCP/TLS répété)
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=50,
                         keepalive_expiry=60)
    timeout = httpx.Timeout(60.0, connect=10.0)
    app.state.http_client = httpx.AsyncClient(
        limits=limits, timeout=timeout, http2=True
    )
    # Configurer litellm pour utiliser ce client
    try:
        litellm.aclient_session = app.state.http_client
    except Exception:
        pass

    # Orchestrator
    agents_dir = os.path.join(project_root, "agents/configs")
    app.state.orchestrator = Orchestrator(agents_dir)
    app.state.chat_history = []

    print(f"✓ JARVIS ready · {len(app.state.orchestrator.agents)} agents loaded")
    yield

    # Cleanup
    await app.state.http_client.aclose()
    print("✓ JARVIS shutdown clean")


app = FastAPI(title="JARVIS AI Ecosystem", lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(project_root, "interfaces/static"))


# ── Routes ──
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    orch = request.app.state.orchestrator
    response = templates.TemplateResponse(
        request, "index.html", {"agents": list(orch.agents.keys())}
    )
    # Cache pour ressources statiques
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@app.get("/health")
async def health(request: Request):
    orch = request.app.state.orchestrator
    return {
        "status": "ok",
        "agents": list(orch.agents.keys()),
        "history_size": len(request.app.state.chat_history),
    }


async def _read_file_safe(file: UploadFile) -> str:
    """Lit un fichier uploadé en async, avec gestion d'erreurs."""
    if not (hasattr(file, "filename") and file.filename):
        return ""
    try:
        content = await file.read()
        # Limite de taille (1 MB par fichier pour éviter saturation)
        if len(content) > 1_000_000:
            return f"\n\n--- FICHIER {file.filename} (trop volumineux, ignoré) ---"
        decoded = content.decode("utf-8", errors="replace")
        return f"\n\n--- FICHIER: {file.filename} ---\n{decoded}\n---"
    except Exception as e:
        return f"\n\n--- FICHIER ERREUR: {file.filename} ({e}) ---"


@app.post("/chat")
async def chat(request: Request):
    """Endpoint non-streaming (compatibilité ascendante)."""
    t0 = time.time()
    form = await request.form()
    query = (form.get("query") or "").strip()
    model = form.get("model")
    files = form.getlist("files")

    effective_query = query if query else "Analyse ces fichiers."

    orch = request.app.state.orchestrator
    if model:
        orch.set_override_model(model)

    # Lecture parallèle des fichiers
    file_chunks = await asyncio.gather(*[_read_file_safe(f) for f in files])
    user_query = effective_query + "".join(file_chunks)

    history = request.app.state.chat_history
    response = await orch.route(user_query, list(history))

    history.append({"role": "user", "content": effective_query})
    history.append({"role": "assistant", "content": response})

    return JSONResponse({
        "response": response,
        "latency": f"{time.time() - t0:.2f}s",
    })


@app.post("/chat/stream")
async def chat_stream(request: Request):
    """Endpoint streaming SSE — c'est ÇA qui rend la conversation fluide."""
    t0 = time.time()
    form = await request.form()
    query = (form.get("query") or "").strip()
    model = form.get("model")
    files = form.getlist("files")

    effective_query = query if query else "Analyse ces fichiers."

    orch = request.app.state.orchestrator
    if model:
        orch.set_override_model(model)

    file_chunks = await asyncio.gather(*[_read_file_safe(f) for f in files])
    user_query = effective_query + "".join(file_chunks)

    history = list(request.app.state.chat_history)

    async def event_stream():
        full_response = []
        try:
            async for event in orch.route_stream(user_query, history):
                # Format SSE : "data: {...}\n\n"
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                if event.get("type") == "token":
                    full_response.append(event["data"])
                elif event.get("type") == "done":
                    # event["data"] contient le texte final complet
                    final_text = event.get("data") or "".join(full_response)
                    # Persistance dans l'historique
                    request.app.state.chat_history.append(
                        {"role": "user", "content": effective_query}
                    )
                    request.app.state.chat_history.append(
                        {"role": "assistant", "content": final_text}
                    )
                    latency = f"{time.time() - t0:.2f}s"
                    yield f"data: {json.dumps({'type': 'meta', 'data': {'latency': latency}})}\n\n"
        except Exception as e:
            err = json.dumps({"type": "error", "data": str(e)})
            yield f"data: {err}\n\n"
        # Sentinel pour fin de stream
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # désactive buffering nginx
            "Connection": "keep-alive",
        },
    )


@app.post("/clear")
async def clear_chat(request: Request):
    request.app.state.chat_history = []
    return JSONResponse({"status": "cleared"})


# ── WebSockets : shell + audio ──
@app.websocket("/ws/shell")
async def websocket_shell(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                command = msg.get("command", "")
                if not command:
                    continue
                async for line in execute_shell_async(command):
                    await websocket.send_json({"type": "output", "data": line})
                await websocket.send_json({"type": "done"})
            except Exception as e:
                await websocket.send_json({"type": "output", "data": f"Error: {e}"})
                await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/audio")
async def websocket_audio(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            await websocket.send_bytes(data)
    except WebSocketDisconnect:
        pass


def start_web():
    print("🚀 JARVIS Web (optimisé) → http://localhost:8501")
    # uvicorn avec worker uvloop si dispo (gain ~30% latence event loop)
    try:
        import uvloop
        loop_arg = "uvloop"
    except ImportError:
        loop_arg = "auto"
    uvicorn.run(
        app, host="0.0.0.0", port=8501,
        loop=loop_arg,
        log_level="warning",  # Moins de bruit
        access_log=False,     # Pas de log d'accès (latence I/O)
    )


if __name__ == "__main__":
    start_web()
