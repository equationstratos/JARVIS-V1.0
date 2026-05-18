"""
JARVIS Web Server V14 — version avec studio d'agents (CRUD complet)

Ajouts par rapport à la version précédente :
- POST /api/agents              → créer un agent
- PUT /api/agent/{name}         → modifier
- DELETE /api/agent/{name}      → supprimer (Manager protégé)
- POST /api/agent/{name}/test   → tester l'agent en live
- GET /api/agents/skills        → liste des skills disponibles
- GET /api/agents/templates     → templates de démarrage
- GET /api/agents/backups       → historique des modifications
- POST /api/agents/reload       → reload tous les agents à chaud

Conserve aussi : /api/system/stats, /api/benchmark/llm, /api/benchmark/agent
"""
import os
import sys
import json
import time
import asyncio
import chromadb
from chromadb.utils import embedding_functions
import subprocess
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
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel  # <-- NOUVEAU
import uvicorn
import httpx
from dotenv import load_dotenv, set_key  # <-- NOUVEAU (ajout de set_key)
import litellm

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("⚠ psutil non installé. Lancer: pip install psutil")

from core.orchestrator import Orchestrator
from core.agent_manager import (
    AgentManager, AgentValidationError, AGENT_TEMPLATES,
    discover_skills, PROTECTED_AGENTS,
)
from utils.shell_utils import execute_shell_async
from utils.observability import ObservabilityManager

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
    app.state.agents_dir = agents_dir
    app.state.orchestrator = Orchestrator(agents_dir)
    app.state.agent_manager = AgentManager(agents_dir)
    app.state.chat_history = []
    app.state.startup_time = time.time()
    app.state.observability = ObservabilityManager(enabled=True)  # Metrics tracking

    # Cleanup vieux backups au démarrage
    app.state.agent_manager.cleanup_old_backups()

    print(f"✓ JARVIS ready · {len(app.state.orchestrator.agents)} agents loaded")
    yield

    await app.state.http_client.aclose()
    print("✓ JARVIS shutdown clean")


app = FastAPI(title="JARVIS AI Ecosystem v14 — Agent Studio", lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(project_root, "interfaces/static"))

# ── Serve static images folder ──
app.mount("/images", StaticFiles(directory=os.path.join(project_root, "interfaces/static/images")), name="images")

# ==========================================
# SÉCURITÉ : BLOCAGE IP (WHITELIST)
# ==========================================

# Mets ici les adresses IP qui ont le droit de se connecter.
# "127.0.0.1" permet au serveur de se parler à lui-même (très important).
# Ajoute l'IP de ton ordinateur ou de ton téléphone (ex: "82.123.45.67" ou "192.168.1.50").
ALLOWED_IPS = {"127.0.0.1", "82.225.219.196"} 

@app.middleware("http")
async def restrict_ip_middleware(request: Request, call_next):
    # Récupère l'IP de la personne qui se connecte
    client_ip = request.client.host
    
    # Si tu utilises un proxy comme Nginx, l'IP réelle est souvent ici :
    # client_ip = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()

    if client_ip not in ALLOWED_IPS:
        print(f"⚠️ TENTATIVE D'INTRUSION BLOQUÉE - IP : {client_ip}")
        return JSONResponse(status_code=403, content={"erreur": "Accès refusé. IP non autorisée."})
    
    # Si l'IP est bonne, on laisse passer la requête
    response = await call_next(request)
    return response

# ═══════════════════════════════════════════════════════════════
# ROUTES PRINCIPALES (existantes)
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

# ═══════════════════════════════════════════════════════════════
# GESTION DES CLÉS API (.env)
# ═══════════════════════════════════════════════════════════════

class APIKeysPayload(BaseModel):
    mistral: str = ""
    openai: str = ""
    anthropic: str = ""
    google: str = ""
    groq: str = ""

class SuggestionsPayload(BaseModel):
    lastMessage: str
    count: int = 5

@app.get("/api/keys")
async def get_keys():
    """Récupère les clés actuelles en les masquant partiellement pour la sécurité."""
    def mask_key(key_name):
        val = os.getenv(key_name, "")
        if len(val) > 8:
            return val[:4] + "..." + val[-4:]
        return val

    return {
        "mistral": mask_key("MISTRAL_API_KEY"),
        "openai": mask_key("OPENAI_API_KEY"),
        "anthropic": mask_key("ANTHROPIC_API_KEY"),
        "google": mask_key("GOOGLE_API_KEY"),
        "groq": mask_key("GROQ_API_KEY")
    }

@app.post("/api/keys")
async def update_keys(keys: APIKeysPayload):
    env_file = os.path.join(project_root, ".env")
    
    mapping = {
        "mistral": ("MISTRAL_API_KEY", keys.mistral),
        "openai": ("OPENAI_API_KEY", keys.openai),
        "anthropic": ("ANTHROPIC_API_KEY", keys.anthropic),
        "google": ("GOOGLE_API_KEY", keys.google), # litellm cherche GOOGLE_API_KEY
        "groq": ("GROQ_API_KEY", keys.groq)
    }

    for key_name, (env_var, value) in mapping.items():
        # IMPORTANT : On ignore les clés vides ou masquées (les "...") 
        # pour ne pas écraser une bonne clé par du vide
        if value and "..." not in value:
            # 1. Mise à jour INSTANTANÉE en mémoire vive (RAM)
            # C'est cette ligne qui évite le redémarrage !
            os.environ[env_var] = value 
            
            # 2. Mise à jour persistante dans le fichier .env
            set_key(env_file, env_var, value)

    return {"status": "success"}
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

    # Resolve agent to track which one was used
    agent = await orch._resolve_agent(user_query)
    response = await agent.execute(user_query, list(history), orch.blackboard, model_override=orch.override_model)

    history.append({"role": "user", "content": effective_query})
    history.append({"role": "assistant", "content": response})

    # Record metrics
    latency_ms = (time.time() - t0) * 1000
    prompt_tokens = len(user_query.split()) // 4 + 10
    completion_tokens = len(response.split()) // 4 + 10
    request.app.state.observability.record_agent_execution(
        agent_name=agent.name,
        model_name=agent.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        tools_used=0,
        confidence_score=0.8,
        cache_hit=False,
        validation_passed=True,
    )

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
        agent_name = "Unknown"
        agent_model = "unknown"
        try:
            async for event in orch.route_stream(user_query, history):
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                if event.get("type") == "agent":
                    agent_name = event.get("data", "Unknown")
                    if agent_name in orch.agents:
                        agent_model = orch.agents[agent_name].model
                elif event.get("type") == "token":
                    full_response.append(event["data"])
                elif event.get("type") == "done":
                    final_text = event.get("data") or "".join(full_response)
                    request.app.state.chat_history.append({"role": "user", "content": effective_query})
                    request.app.state.chat_history.append({"role": "assistant", "content": final_text})
                    latency_ms = (time.time() - t0) * 1000
                    latency = f"{time.time() - t0:.2f}s"

                    # Record metrics
                    prompt_tokens = len(user_query.split()) // 4 + 10
                    completion_tokens = len(final_text.split()) // 4 + 10
                    request.app.state.observability.record_agent_execution(
                        agent_name=agent_name,
                        model_name=agent_model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        latency_ms=latency_ms,
                        tools_used=0,
                        confidence_score=0.8,
                        cache_hit=False,
                        validation_passed=True,
                    )

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


@app.post("/api/generate-suggestions")
async def generate_suggestions(request: Request, payload: SuggestionsPayload):
    """
    Generate AI-powered contextual response suggestions based on the last message.

    Endpoint: POST /api/generate-suggestions
    Body: {
        "lastMessage": "string",
        "count": 5
    }
    """
    try:
        last_msg = payload.lastMessage.strip()
        count = min(max(payload.count, 1), 10)  # Clamp between 1-10

        if not last_msg:
            return JSONResponse({"error": "lastMessage cannot be empty"}, status_code=400)

        orch = request.app.state.orchestrator

        # Create a prompt to generate suggestions
        suggestion_prompt = f"""Based on this message:
"{last_msg}"

Generate {count} short, diverse, and contextual response suggestions (in French).
Each suggestion should be a complete, natural response.
Format: Return ONLY a JSON array of strings, nothing else.

Example output:
["Suggestion 1", "Suggestion 2", "Suggestion 3"]

Now generate the suggestions:"""

        # Use the orchestrator to generate suggestions
        # Get the current model or default
        model = orch.override_model or "gemini/gemini-2.0-flash"

        try:
            response = await orch.route(suggestion_prompt, request.app.state.chat_history)

            # Try to parse the response as JSON
            import re
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)

            if json_match:
                suggestions = json.loads(json_match.group())
                # Ensure it's a list of strings
                suggestions = [str(s).strip() for s in suggestions if s][:count]
            else:
                # Fallback: split by newlines or sentences if no JSON found
                suggestions = [s.strip() for s in response.split('\n') if s.strip()][:count]

            # Record metrics
            request.app.state.observability.record_agent_execution(
                agent_name="suggestion_generator",
                model_name=model,
                prompt_tokens=len(suggestion_prompt.split()) // 4 + 10,
                completion_tokens=len(response.split()) // 4 + 10,
                latency_ms=(time.time() - time.time()) * 1000,
                tools_used=0,
                confidence_score=0.85,
                cache_hit=False,
                validation_passed=True,
            )

            return JSONResponse({"suggestions": suggestions})

        except Exception as e:
            print(f"Error generating suggestions: {e}")
            # Provide fallback suggestions if LLM fails
            fallback = [
                "Peux-tu me donner plus de détails ?",
                "Que veux-tu dire exactement ?",
                "Comment je peux t'aider davantage ?",
                "Y a-t-il d'autres informations pertinentes ?",
                "Qu'en est-il des implications ?"
            ]
            return JSONResponse({"suggestions": fallback[:count]})

    except Exception as e:
        print(f"Unexpected error in /api/generate-suggestions: {e}")
        return JSONResponse(
            {"error": f"Failed to generate suggestions: {str(e)}"},
            status_code=500
        )

# 1. Configuration de la base de données (en local sur ton VPS)
chroma_client = chromadb.PersistentClient(path="./memoire_ia")
# Utilise un modèle d'embedding léger pour transformer le texte en vecteurs
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = chroma_client.get_or_create_collection(name="experience_agent", embedding_function=sentence_transformer_ef)

def se_souvenir(requete_actuelle):
    """Recherche dans le passé les 2 souvenirs les plus proches."""
    resultats = collection.query(
        query_texts=[requete_actuelle],
        n_results=2
    )
    if resultats['documents'][0]:
        return "\n".join(resultats['documents'][0])
    return "Aucun souvenir similaire."

def enregistrer_experience(tache, resultat, lecon):
    """Sauvegarde le succès ou l'échec dans la mémoire."""
    identifiant = f"exp_{collection.count() + 1}"
    contenu = f"Tâche: {tache} | Résultat: {resultat} | Leçon: {lecon}"
    collection.add(
        documents=[contenu],
        ids=[identifiant]
    )

# --- EXEMPLE D'UTILISATION DANS TON WORKFLOW ---
# 1. L'utilisateur demande quelque chose
user_input = "Crée un dossier 'test' et un fichier dedans"

# 2. L'IA consulte son passé
souvenirs = se_souvenir(user_input)
print(f"L'IA se rappelle : {souvenirs}")

# 3. Tu envoies 'user_input' + 'souvenirs' au modèle Ollama...
# (Supposons que l'IA exécute et génère un log)

# 4. Archivage après exécution (exemple d'échec)
enregistrer_experience(user_input, "Échec", "Le shell a refusé car le dossier existait déjà. Utiliser 'mkdir -p'.")
# ═══════════════════════════════════════════════════════════════
# SYSTEM STATS (psutil)
# ═══════════════════════════════════════════════════════════════
_stats_cache = {"data": None, "ts": 0}
_STATS_CACHE_TTL = 1.5


@app.get("/api/system/stats")
async def system_stats():
    if not HAS_PSUTIL:
        raise HTTPException(503, "psutil non installé sur le serveur")
    now = time.time()
    if _stats_cache["data"] and (now - _stats_cache["ts"]) < _STATS_CACHE_TTL:
        return JSONResponse(_stats_cache["data"])
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_count = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage("/")
        try:
            disk_io = psutil.disk_io_counters()
            disk_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0
            disk_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0
        except Exception:
            disk_read_mb = disk_write_mb = 0
        try:
            net = psutil.net_io_counters()
            net_sent_mb = net.bytes_sent / (1024 * 1024)
            net_recv_mb = net.bytes_recv / (1024 * 1024)
        except Exception:
            net_sent_mb = net_recv_mb = 0
        boot_time = psutil.boot_time()
        uptime_seconds = now - boot_time
        try:
            this_proc = psutil.Process(os.getpid())
            proc_mem_mb = this_proc.memory_info().rss / (1024 * 1024)
            proc_cpu = this_proc.cpu_percent(interval=0.1)
            proc_threads = this_proc.num_threads()
        except Exception:
            proc_mem_mb = proc_cpu = proc_threads = 0
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


@app.get("/metrics")
async def metrics(request: Request):
    """Retourne les métriques d'observabilité JARVIS."""
    obs: ObservabilityManager = request.app.state.observability
    try:
        return JSONResponse({
            "global_stats": obs.get_global_stats(),
            "agents": {
                agent_name: obs.get_agent_stats(agent_name)
                for agent_name in obs.get_agent_info()
            },
            "execution_count": len(obs.metrics_history),
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "global_stats": {},
            "agents": {},
            "message": "Metrics not yet available (run some queries first)"
        }, status_code=200)


# ═══════════════════════════════════════════════════════════════
# AGENTS — CRUD COMPLET ⭐ NOUVEAU
# ═══════════════════════════════════════════════════════════════

def _agent_to_dict(name: str, agent_obj, full_data: dict) -> dict:
    """Format unifié pour la réponse API."""
    return {
        "name": name,
        "description": full_data.get("description", ""),
        "model": full_data.get("model", ""),
        "skills": full_data.get("skills", []),
        "history_limit": full_data.get("history_limit", 10),
        "system_prompt": full_data.get("system_prompt", ""),
        "system_prompt_preview": full_data.get("system_prompt", "")[:200],
        "inherit_model": full_data.get("inherit_model", False),
        "is_protected": name in PROTECTED_AGENTS,
    }


def _reload_orchestrator(app):
    """Recharge tous les agents depuis le disque (reload à chaud)."""
    try:
        # Sauvegarder le modèle d'override si existant
        override = getattr(app.state.orchestrator, "_override_model", None)
        # Recharger
        app.state.orchestrator = Orchestrator(app.state.agents_dir)
        if override:
            try:
                app.state.orchestrator.set_override_model(override)
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"⚠ Reload orchestrator failed: {e}")
        return False


@app.get("/api/agents")
async def list_agents(request: Request):
    """Liste tous les agents (lecture disque, pas du runtime)."""
    mgr: AgentManager = request.app.state.agent_manager
    agents = []
    for name in mgr.list_names():
        try:
            data = mgr.read(name)
            agents.append(_agent_to_dict(name, None, data))
        except Exception as e:
            agents.append({"name": name, "error": str(e), "is_protected": name in PROTECTED_AGENTS})
    return JSONResponse({"agents": agents, "count": len(agents)})


@app.get("/api/agent/{name}")
async def get_agent(name: str, request: Request):
    """Lecture détaillée d'un agent."""
    mgr: AgentManager = request.app.state.agent_manager
    try:
        data = mgr.read(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Agent '{name}' introuvable")
    return JSONResponse(_agent_to_dict(name, None, data))


@app.post("/api/agents")
async def create_agent(request: Request):
    """Crée un nouvel agent. Body : JSON complet de l'agent."""
    body = await request.json()
    mgr: AgentManager = request.app.state.agent_manager
    try:
        normalized = mgr.create(body)
    except AgentValidationError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur création : {e}")

    reloaded = _reload_orchestrator(request.app)
    return JSONResponse({
        "success": True,
        "agent": _agent_to_dict(normalized["name"], None, normalized),
        "reloaded": reloaded,
    }, status_code=201)


@app.put("/api/agent/{name}")
async def update_agent(name: str, request: Request):
    """Modifie un agent existant."""
    body = await request.json()
    mgr: AgentManager = request.app.state.agent_manager
    try:
        normalized = mgr.update(name, body)
    except FileNotFoundError:
        raise HTTPException(404, f"Agent '{name}' introuvable")
    except AgentValidationError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur modification : {e}")

    reloaded = _reload_orchestrator(request.app)
    return JSONResponse({
        "success": True,
        "agent": _agent_to_dict(normalized["name"], None, normalized),
        "renamed_from": name if name != normalized["name"] else None,
        "reloaded": reloaded,
    })


@app.delete("/api/agent/{name}")
async def delete_agent(name: str, request: Request):
    """Supprime un agent (sauf Manager protégé)."""
    mgr: AgentManager = request.app.state.agent_manager
    try:
        mgr.delete(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Agent '{name}' introuvable")
    except AgentValidationError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur suppression : {e}")

    reloaded = _reload_orchestrator(request.app)
    return JSONResponse({"success": True, "reloaded": reloaded})


@app.post("/api/agent/{name}/test")
async def test_agent(name: str, request: Request):
    """
    Teste un agent avec un prompt simple.
    Body optionnel : {"prompt": "..."}
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    test_prompt = (body.get("prompt") or "Présente-toi en une phrase et liste tes capacités.").strip()

    orch = request.app.state.orchestrator
    if name not in orch.agents:
        raise HTTPException(404, f"Agent '{name}' introuvable dans l'orchestrator")

    agent = orch.agents[name]
    t0 = time.time()
    try:
        response = await agent.execute(test_prompt, [], orch.blackboard)
        return JSONResponse({
            "success": True,
            "agent": name,
            "prompt": test_prompt,
            "response": response,
            "latency_seconds": round(time.time() - t0, 2),
            "response_length": len(response),
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "agent": name,
            "prompt": test_prompt,
            "error": str(e),
            "latency_seconds": round(time.time() - t0, 2),
        }, status_code=200)


@app.get("/api/agents/skills")
async def list_skills():
    """Liste des skills disponibles (pour le sélecteur dans l'éditeur)."""
    skills = discover_skills(project_root)
    return JSONResponse({"skills": skills})


@app.get("/api/agents/templates")
async def list_templates():
    """Liste des templates de démarrage."""
    templates = []
    for tid, tpl in AGENT_TEMPLATES.items():
        templates.append({
            "id": tid,
            "data": tpl,
        })
    return JSONResponse({"templates": templates})


@app.get("/api/agents/backups")
async def list_backups(request: Request, agent: Optional[str] = None):
    """Liste les backups d'agents (filtrable par nom)."""
    mgr: AgentManager = request.app.state.agent_manager
    return JSONResponse({"backups": mgr.list_backups(agent)})


@app.post("/api/agents/reload")
async def reload_agents(request: Request):
    """Force un reload à chaud de tous les agents."""
    success = _reload_orchestrator(request.app)
    return JSONResponse({
        "success": success,
        "agents": list(request.app.state.orchestrator.agents.keys()),
    })


@app.get("/api/images")
async def list_images(request: Request):
    """Liste les images du dossier /images"""
    images_dir = os.path.join(project_root, "interfaces/static/images")
    try:
        files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'))]
        return JSONResponse({"images": files})
    except Exception as e:
        return JSONResponse({"images": [], "error": str(e)})


@app.post("/api/upload")
async def upload_image(request: Request):
    """Upload d'image dans le dossier /images"""
    images_dir = os.path.join(project_root, "interfaces/static/images")
    os.makedirs(images_dir, exist_ok=True)

    try:
        form = await request.form()
        file = form.get("image")

        if not file or not file.filename:
            raise HTTPException(400, "Aucun fichier fourni")

        # Vérifier l'extension
        allowed_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
        file_ext = os.path.splitext(file.filename)[1].lower()

        if file_ext not in allowed_ext:
            raise HTTPException(400, f"Format non autorisé. Acceptés: {', '.join(allowed_ext)}")

        # Lire et sauvegarder le fichier
        content = await file.read()
        file_path = os.path.join(images_dir, file.filename)

        with open(file_path, 'wb') as f:
            f.write(content)

        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "path": f"/images/{file.filename}"
        })
    except Exception as e:
        raise HTTPException(500, f"Erreur upload: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# BENCHMARKS (existants)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/benchmark/llm")
async def benchmark_llm(request: Request):
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
            model=model, messages=[{"role": "user", "content": prompt}],
            stream=True, timeout=60, max_tokens=300,
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
            "response": text, # <-- ON ENVOIE LA RÉPONSE COMPLÈTE
            "text_length": len(text),
        })
    except Exception as e:
        return JSONResponse({"model": model, "error": str(e), "score": 0, "grade": "F"})


def _compute_speed_score(ttfb: float, tokens: int, total: float) -> int:
    if total <= 0 or tokens == 0: return 0
    if ttfb < 0.3: ttfb_score = 100
    elif ttfb < 0.6: ttfb_score = 90
    elif ttfb < 1.0: ttfb_score = 75
    elif ttfb < 2.0: ttfb_score = 55
    elif ttfb < 4.0: ttfb_score = 30
    else: ttfb_score = 10
    tps = tokens / total
    if tps >= 50: tps_score = 100
    elif tps >= 35: tps_score = 90
    elif tps >= 25: tps_score = 75
    elif tps >= 15: tps_score = 55
    elif tps >= 8: tps_score = 35
    else: tps_score = 15
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
    body = await request.json()
    agent_name = body.get("agent")
    task_type = body.get("task_type", "shell")
    orch = request.app.state.orchestrator
    if agent_name not in orch.agents:
        raise HTTPException(404, f"Agent '{agent_name}' inconnu")
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
        score = _compute_agent_score(response, task_type, total)
        return JSONResponse({
            "agent": agent_name, "task_type": task_type, "prompt": prompt,
            "total_seconds": round(total, 2),
            "response_length": len(response),
            "response": response, # <-- ON ENVOIE LA RÉPONSE COMPLÈTE
            "score": score, "grade": _score_to_grade(score),
            "metrics": _agent_metrics(response, task_type, total),
        })
    except Exception as e:
        return JSONResponse({
            "agent": agent_name, "error": str(e), "score": 0, "grade": "F",
        })


def _compute_agent_score(response: str, task_type: str, total: float) -> int:
    if not response or response.startswith("⚠"): return 0
    score = 50
    L = len(response)
    if 100 <= L <= 2000: score += 15
    elif L < 50: score -= 20
    if total < 3: score += 15
    elif total < 8: score += 8
    elif total > 20: score -= 10
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
    L = len(response)
    return {
        "exactitude": min(100, 60 + (15 if 100 <= L <= 2000 else 0) + (20 if "```" in response or "$" in response else 0)),
        "vitesse": max(0, min(100, int(100 - total * 5))),
        "autonomie": 70 if "?" not in response[:200] else 40,
        "gestion_erreur": 80 if not response.startswith("⚠") and "erreur" not in response.lower()[:100] else 30,
        "format": min(100, 50 + (30 if "\n" in response else 0) + (20 if "```" in response or "•" in response or "-" in response else 0)),
    }

def executer_et_memoriser(commande):
    # 1. On exécute vraiment sur le VPS
    process = subprocess.run(commande, shell=True, capture_output=True, text=True)
    
    # 2. On vérifie la réalité
    reussite_reelle = (process.returncode == 0)
    resultat_brut = process.stdout if reussite_reelle else process.stderr
    
    # 3. On force l'IA à voir la réalité avant d'enregistrer
    # Si le dossier n'existe pas, l'IA recevra "ls: cannot access... No such file"
    # et ne pourra plus mentir dans sa mémoire.
    
    status = "Succès" if reussite_reelle else "Échec"
    
    # On n'enregistre QUE la vérité technique
    lecon = f"Commande: {commande} | Status: {status} | Sortie: {resultat_brut}"
    enregistrer_experience(commande, status, lecon)
    
    return resultat_brut
# ═══════════════════════════════════════════════════════════════
# WEBSOCKETS
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
                if not command: continue
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
    print("🚀 JARVIS Web (v14, Agent Studio) → http://localhost:8501")
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
