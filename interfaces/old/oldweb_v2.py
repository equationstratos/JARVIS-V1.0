"""
JARVIS Web Server V14 — version avec endpoints système et benchmarks

Ajouts par rapport à la version précédente :
- /api/system/stats : CPU, RAM, disque, réseau, uptime via psutil
- /api/agents : liste détaillée des agents disponibles
- /api/agent/{name} : config d'un agent spécifique
- /api/benchmark/llm : benchmark de modèles LLM (multi-test, métriques temps réel)
- /api/benchmark/agent : test d'efficacité d'un agent
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
    FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, HTTPException,
)
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import httpx
from dotenv import load_dotenv
import litellm

# psutil pour les stats système (à installer : pip install psutil)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("⚠ psutil non installé — stats système indisponibles. Lancer: pip install psutil")

from core.orchestrator import Orchestrator
from utils.shell_utils import execute_shell_async

load_dotenv(os.path.join(project_root, ".env"))


# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=50,
                         keepalive_expiry=60)
    timeout = httpx.Timeout(60.0, connect=10.0)
    app.state.http_client = httpx.AsyncClient(limits=limits, timeout=timeout, http2=False)
    try:
        litellm.aclient_session = app.state.http_client
    except Exception:
        pass

    agents_dir = os.path.join(project_root, "agents/configs")
    app.state.orchestrator = Orchestrator(agents_dir)
    app.state.chat_history = []
    app.state.startup_time = time.time()

    print(f"✓ JARVIS ready · {len(app.state.orchestrator.agents)} agents loaded")
    yield

    await app.state.http_client.aclose()
    print("✓ JARVIS shutdown clean")


app = FastAPI(title="JARVIS AI Ecosystem v14", lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(project_root, "interfaces/static"))


# ═══════════════════════════════════════════════════════════════
# ROUTES PRINCIPALES (existantes — gardées telles quelles)
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    orch = request.app.state.orchestrator
    response = templates.TemplateResponse(
        request, "index.html", {"agents": list(orch.agents.keys())}
    )
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@app.get("/health")
async def health(request: Request):
    orch = request.app.state.orchestrator
    return {
        "status": "ok",
        "agents": list(orch.agents.keys()),
        "history_size": len(request.app.state.chat_history),
        "uptime": time.time() - request.app.state.startup_time,
    }


async def _read_file_safe(file: UploadFile) -> str:
    if not (hasattr(file, "filename") and file.filename):
        return ""
    try:
        content = await file.read()
        if len(content) > 1_000_000:
            return f"\n\n--- FICHIER {file.filename} (trop volumineux) ---"
        decoded = content.decode("utf-8", errors="replace")
        return f"\n\n--- FICHIER: {file.filename} ---\n{decoded}\n---"
    except Exception as e:
        return f"\n\n--- FICHIER ERREUR: {file.filename} ({e}) ---"


@app.post("/chat")
async def chat(request: Request):
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
    history = request.app.state.chat_history
    response = await orch.route(user_query, list(history))
    history.append({"role": "user", "content": effective_query})
    history.append({"role": "assistant", "content": response})
    return JSONResponse({"response": response, "latency": f"{time.time() - t0:.2f}s"})


@app.post("/chat/stream")
async def chat_stream(request: Request):
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
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                if event.get("type") == "token":
                    full_response.append(event["data"])
                elif event.get("type") == "done":
                    final_text = event.get("data") or "".join(full_response)
                    request.app.state.chat_history.append({"role": "user", "content": effective_query})
                    request.app.state.chat_history.append({"role": "assistant", "content": final_text})
                    latency = f"{time.time() - t0:.2f}s"
                    yield f"data: {json.dumps({'type': 'meta', 'data': {'latency': latency}})}\n\n"
        except Exception as e:
            err = json.dumps({"type": "error", "data": str(e)})
            yield f"data: {err}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/clear")
async def clear_chat(request: Request):
    request.app.state.chat_history = []
    return JSONResponse({"status": "cleared"})


# ═══════════════════════════════════════════════════════════════
# NOUVEAUX ENDPOINTS — STATS SYSTÈME
# ═══════════════════════════════════════════════════════════════

# Cache pour les stats système (évite de hammer psutil)
_stats_cache = {"data": None, "ts": 0}
_STATS_CACHE_TTL = 1.5  # secondes


@app.get("/api/system/stats")
async def system_stats():
    """Retourne les métriques système temps réel via psutil."""
    if not HAS_PSUTIL:
        raise HTTPException(503, "psutil non installé sur le serveur")

    now = time.time()
    if _stats_cache["data"] and (now - _stats_cache["ts"]) < _STATS_CACHE_TTL:
        return JSONResponse(_stats_cache["data"])

    try:
        # CPU : global + par cœur
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_count = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()

        # RAM
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disque (partition racine)
        disk = psutil.disk_usage("/")
        try:
            disk_io = psutil.disk_io_counters()
            disk_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0
            disk_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0
        except Exception:
            disk_read_mb = disk_write_mb = 0

        # Réseau (cumul depuis boot)
        try:
            net = psutil.net_io_counters()
            net_sent_mb = net.bytes_sent / (1024 * 1024)
            net_recv_mb = net.bytes_recv / (1024 * 1024)
        except Exception:
            net_sent_mb = net_recv_mb = 0

        # Uptime système
        boot_time = psutil.boot_time()
        uptime_seconds = now - boot_time

        # Processus JARVIS
        try:
            this_proc = psutil.Process(os.getpid())
            proc_mem_mb = this_proc.memory_info().rss / (1024 * 1024)
            proc_cpu = this_proc.cpu_percent(interval=0.1)
            proc_threads = this_proc.num_threads()
        except Exception:
            proc_mem_mb = proc_cpu = proc_threads = 0

        # Load average (Unix only)
        try:
            load_avg = list(os.getloadavg())
        except Exception:
            load_avg = None

        data = {
            "timestamp": now,
            "cpu": {
                "percent": round(cpu_percent, 1),
                "per_core": [round(c, 1) for c in cpu_per_core],
                "count": cpu_count,
                "freq_mhz": round(cpu_freq.current) if cpu_freq else None,
                "freq_max_mhz": round(cpu_freq.max) if cpu_freq and cpu_freq.max else None,
                "load_avg": load_avg,
            },
            "memory": {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "percent": round(mem.percent, 1),
                "swap_used_gb": round(swap.used / (1024 ** 3), 2),
                "swap_total_gb": round(swap.total / (1024 ** 3), 2),
            },
            "disk": {
                "total_gb": round(disk.total / (1024 ** 3), 1),
                "used_gb": round(disk.used / (1024 ** 3), 1),
                "free_gb": round(disk.free / (1024 ** 3), 1),
                "percent": round(disk.percent, 1),
                "read_mb_total": round(disk_read_mb, 1),
                "write_mb_total": round(disk_write_mb, 1),
            },
            "network": {
                "sent_mb_total": round(net_sent_mb, 1),
                "recv_mb_total": round(net_recv_mb, 1),
            },
            "system": {
                "uptime_seconds": round(uptime_seconds),
                "boot_time": boot_time,
                "platform": sys.platform,
                "python_version": sys.version.split()[0],
            },
            "jarvis": {
                "memory_mb": round(proc_mem_mb, 1),
                "cpu_percent": round(proc_cpu, 1),
                "threads": proc_threads,
                "uptime_seconds": round(now - app.state.startup_time),
                "history_size": len(app.state.chat_history),
                "agents_count": len(app.state.orchestrator.agents),
            },
        }
        _stats_cache["data"] = data
        _stats_cache["ts"] = now
        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(500, f"Erreur stats: {e}")


# ═══════════════════════════════════════════════════════════════
# NOUVEAUX ENDPOINTS — GESTION DES AGENTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/agents")
async def list_agents(request: Request):
    """Liste tous les agents avec leurs configs."""
    orch = request.app.state.orchestrator
    agents = []
    for name, agent in orch.agents.items():
        agents.append({
            "name": name,
            "description": agent.config.get("description", ""),
            "model": agent.config.get("model", ""),
            "skills": agent.config.get("skills", []),
            "history_limit": agent.config.get("history_limit", 10),
            "system_prompt_preview": agent.config.get("system_prompt", "")[:200],
        })
    return JSONResponse({"agents": agents, "count": len(agents)})


@app.get("/api/agent/{name}")
async def get_agent(name: str, request: Request):
    """Config détaillée d'un agent."""
    orch = request.app.state.orchestrator
    if name not in orch.agents:
        raise HTTPException(404, f"Agent '{name}' inconnu")
    agent = orch.agents[name]
    return JSONResponse({
        "name": name,
        "config": agent.config,
    })


# ═══════════════════════════════════════════════════════════════
# NOUVEAUX ENDPOINTS — BENCHMARKS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/benchmark/llm")
async def benchmark_llm(request: Request):
    """
    Benchmark vitesse d'un modèle LLM.
    Body JSON : {"model": "...", "prompt": "..."}
    Retourne TTFB, tok/s, latence totale, texte de sortie.
    """
    body = await request.json()
    model = body.get("model")
    prompt = body.get("prompt", "Explique le big bang en 80 mots.")
    if not model:
        raise HTTPException(400, "model requis")

    t0 = time.time()
    ttfb = None
    token_count = 0
    full_text = []

    try:
        stream = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            timeout=60,
            max_tokens=300,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and getattr(delta, "content", None):
                if ttfb is None:
                    ttfb = time.time() - t0
                full_text.append(delta.content)
                token_count += 1
        total = time.time() - t0
        text = "".join(full_text)
        score = _compute_speed_score(ttfb or 0, token_count, total)
        return JSONResponse({
            "model": model,
            "ttfb_ms": round((ttfb or 0) * 1000),
            "total_seconds": round(total, 2),
            "token_count": token_count,
            "tokens_per_second": round(token_count / total, 1) if total > 0 else 0,
            "score": score,
            "grade": _score_to_grade(score),
            "preview": text[:200],
            "text_length": len(text),
        })
    except Exception as e:
        return JSONResponse({
            "model": model,
            "error": str(e),
            "score": 0,
            "grade": "F",
        }, status_code=200)  # 200 pour que le frontend puisse afficher l'erreur


def _compute_speed_score(ttfb: float, tokens: int, total: float) -> int:
    """Score 0-100 basé sur TTFB + débit + total."""
    if total <= 0 or tokens == 0:
        return 0
    # TTFB scoring : 200ms=100, 1s=70, 2s=40, 4s=10
    if ttfb < 0.3:
        ttfb_score = 100
    elif ttfb < 0.6:
        ttfb_score = 90
    elif ttfb < 1.0:
        ttfb_score = 75
    elif ttfb < 2.0:
        ttfb_score = 55
    elif ttfb < 4.0:
        ttfb_score = 30
    else:
        ttfb_score = 10
    # Tokens/sec : 50+/s=100, 30=80, 15=50, 5=20
    tps = tokens / total
    if tps >= 50:
        tps_score = 100
    elif tps >= 35:
        tps_score = 90
    elif tps >= 25:
        tps_score = 75
    elif tps >= 15:
        tps_score = 55
    elif tps >= 8:
        tps_score = 35
    else:
        tps_score = 15
    # Pondération : TTFB 40%, débit 60% (la perception est dominée par le débit)
    return int(0.4 * ttfb_score + 0.6 * tps_score)


def _score_to_grade(score: int) -> str:
    if score >= 90: return "S"
    if score >= 80: return "A"
    if score >= 65: return "B"
    if score >= 50: return "C"
    if score >= 30: return "D"
    return "F"


@app.post("/api/benchmark/agent")
async def benchmark_agent(request: Request):
    """
    Test d'efficacité d'un agent sur une tâche prédéfinie.
    Body : {"agent": "ShellAgent", "task_type": "shell|code|search"}
    """
    body = await request.json()
    agent_name = body.get("agent")
    task_type = body.get("task_type", "shell")
    orch = request.app.state.orchestrator
    if agent_name not in orch.agents:
        raise HTTPException(404, f"Agent '{agent_name}' inconnu")

    # Tâches standardisées par type
    tasks = {
        "shell": "Liste les 5 plus gros fichiers du répertoire courant en utilisant des commandes shell.",
        "code": "Écris une fonction Python qui retourne les nombres premiers jusqu'à N.",
        "search": "Cherche les dernières news sur l'IA en 2025.",
        "general": "Présente-toi en 50 mots et liste tes capacités.",
    }
    prompt = tasks.get(task_type, tasks["general"])

    agent = orch.agents[agent_name]
    t0 = time.time()
    try:
        response = await agent.execute(prompt, [], orch.blackboard)
        total = time.time() - t0
        # Score basé sur : longueur réponse, présence d'éléments attendus, vitesse
        score = _compute_agent_score(response, task_type, total)
        return JSONResponse({
            "agent": agent_name,
            "task_type": task_type,
            "prompt": prompt,
            "total_seconds": round(total, 2),
            "response_length": len(response),
            "response_preview": response[:300],
            "score": score,
            "grade": _score_to_grade(score),
            "metrics": _agent_metrics(response, task_type, total),
        })
    except Exception as e:
        return JSONResponse({
            "agent": agent_name,
            "error": str(e),
            "score": 0,
            "grade": "F",
        })


def _compute_agent_score(response: str, task_type: str, total: float) -> int:
    """Score 0-100 sur exactitude + vitesse + format."""
    if not response or response.startswith("⚠"):
        return 0
    score = 50  # base

    # Longueur (ni trop court ni trop long)
    L = len(response)
    if 100 <= L <= 2000: score += 15
    elif L < 50: score -= 20

    # Vitesse
    if total < 3: score += 15
    elif total < 8: score += 8
    elif total > 20: score -= 10

    # Format / contenu attendu par type
    keywords = {
        "shell": ["ls", "du", "find", "sort", "head", "$"],
        "code": ["def ", "return", "for ", "if ", "```"],
        "search": ["http", "selon", "récent", "2025", "•", "-"],
    }
    if task_type in keywords:
        found = sum(1 for kw in keywords[task_type] if kw.lower() in response.lower())
        score += min(20, found * 4)

    return max(0, min(100, score))


def _agent_metrics(response: str, task_type: str, total: float) -> dict:
    """Décompose le score en sous-métriques pour le radar chart."""
    L = len(response)
    return {
        "exactitude": min(100, 60 + (15 if 100 <= L <= 2000 else 0) + (20 if "```" in response or "$" in response else 0)),
        "vitesse": max(0, min(100, int(100 - total * 5))),
        "autonomie": 70 if "?" not in response[:200] else 40,
        "gestion_erreur": 80 if not response.startswith("⚠") and "erreur" not in response.lower()[:100] else 30,
        "format": min(100, 50 + (30 if "\n" in response else 0) + (20 if "```" in response or "•" in response or "-" in response else 0)),
    }


# ═══════════════════════════════════════════════════════════════
# WEBSOCKETS (existants)
# ═══════════════════════════════════════════════════════════════

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
    print("🚀 JARVIS Web (v14, menus complets) → http://localhost:8501")
    try:
        import uvloop
        loop_arg = "uvloop"
    except ImportError:
        loop_arg = "auto"
    uvicorn.run(
        app, host="0.0.0.0", port=8501, loop=loop_arg,
        log_level="warning", access_log=False,
    )


if __name__ == "__main__":
    start_web()
