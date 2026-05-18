#!/usr/bin/env bash
# ==============================================================
# JARVIS-V1.0 — Lancement de tous les serveurs
#
# Ports :
#   :8000  TTS Kokoro     (optionnel — ../jarvis-voice/)
#   :8501  Backend        (FastAPI — interfaces/web_v2.py)
#   :3001  Mobile proxy   (FastAPI — webmobile.py)
#
# Usage : bash launch-JARVIS.sh
# ==============================================================
set -uo pipefail

# ── Couleurs ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[JARVIS]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Dossier du script (= racine du repo) ──────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BOLD}${CYAN}"
echo "  JARVIS-V1.0 — Démarrage des services"
echo -e "${NC}"

# ── Vérification venv ─────────────────────────────────────────
if [[ ! -f "$SCRIPT_DIR/venv/bin/activate" ]]; then
    error "Environnement virtuel introuvable. Lancez d'abord l'installateur :"
    error "  bash install-JARVIS-V1.0.sh"
    exit 1
fi
# shellcheck source=/dev/null
source "$SCRIPT_DIR/venv/bin/activate"
success "Environnement virtuel: $(which python)"

# ── Arrêt des anciens processus ───────────────────────────────
info "Nettoyage des processus existants..."
pkill -f "tts_server4.py" 2>/dev/null && echo "  Arrêt ancien serveur TTS" || true
pkill -f "main.py --web"  2>/dev/null && echo "  Arrêt ancien backend" || true
pkill -f "webmobile.py"   2>/dev/null && echo "  Arrêt ancien proxy mobile" || true
sleep 0.5

# ── Logs ──────────────────────────────────────────────────────
LOG_DIR="$SCRIPT_DIR/Logs"
mkdir -p "$LOG_DIR"

TTS_PID=""
BACKEND_PID=""
MOBILE_PID=""

# ── Attente port ouvert ───────────────────────────────────────
wait_for_port() {
    local port="$1" name="$2" max_wait=30
    local i=0
    while ! (echo > /dev/tcp/127.0.0.1/"$port") 2>/dev/null; do
        sleep 1
        i=$((i + 1))
        [[ $i -ge $max_wait ]] && { warn "$name n'a pas répondu sur :$port après ${max_wait}s"; return 1; }
    done
    return 0
}

# ── 1. TTS Kokoro (optionnel) ─────────────────────────────────
TTS_SCRIPT=""
for candidate in \
    "$SCRIPT_DIR/../jarvis-voice/tts_server4.py" \
    "$HOME/jarvis-voice/tts_server4.py"; do
    [[ -f "$candidate" ]] && TTS_SCRIPT="$(realpath "$candidate")" && break
done

if [[ -n "$TTS_SCRIPT" ]]; then
    info "Démarrage du serveur TTS (Kokoro)..."
    TTS_DIR="$(dirname "$TTS_SCRIPT")"
    if [[ -f "$TTS_DIR/venv/bin/activate" ]]; then
        (source "$TTS_DIR/venv/bin/activate" && python3 "$TTS_SCRIPT") \
            >"$LOG_DIR/tts.log" 2>&1 &
    else
        python3 "$TTS_SCRIPT" >"$LOG_DIR/tts.log" 2>&1 &
    fi
    TTS_PID=$!
    if wait_for_port 8000 "TTS"; then
        success "TTS prêt sur :8000 (PID $TTS_PID)"
    else
        warn "TTS non disponible — mode texte uniquement"
        TTS_PID=""
    fi
else
    warn "Serveur TTS non trouvé (../jarvis-voice/tts_server4.py)"
    warn "Mode texte uniquement. Consultez README.md pour l'installation du TTS."
fi

# ── 2. Backend :8501 ──────────────────────────────────────────
info "Démarrage du backend JARVIS..."
python "$SCRIPT_DIR/main.py" --web >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

if wait_for_port 8501 "Backend"; then
    success "Backend prêt sur :8501 (PID $BACKEND_PID)"
else
    error "Le backend n'a pas démarré. Consultez: $LOG_DIR/backend.log"
    cat "$LOG_DIR/backend.log" | tail -20
fi

# ── 3. Mobile proxy :3001 ─────────────────────────────────────
info "Démarrage du proxy mobile..."
python "$SCRIPT_DIR/webmobile.py" >"$LOG_DIR/mobile.log" 2>&1 &
MOBILE_PID=$!

if wait_for_port 3001 "Mobile"; then
    success "Proxy mobile prêt sur :3001 (PID $MOBILE_PID)"
else
    warn "Proxy mobile non disponible. Consultez: $LOG_DIR/mobile.log"
fi

# ── Statut ────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${CYAN}${BOLD}  JARVIS-V1.0 en cours d'exécution${NC}"
echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "  Interface Web    →  ${BOLD}http://localhost:8501${NC}"
echo -e "  Interface Mobile →  ${BOLD}http://localhost:3001${NC}"
[[ -n "$TTS_PID" ]] && echo -e "  TTS (Kokoro)     →  ${BOLD}http://localhost:8000${NC}"
echo -e "  Logs             →  ${BOLD}$LOG_DIR/${NC}"
echo ""
echo -e "  Appuyez sur ${BOLD}Ctrl+C${NC} pour tout arrêter"
echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}"
echo ""

# ── Arrêt propre ──────────────────────────────────────────────
cleanup() {
    echo ""
    info "Arrêt de tous les services..."
    [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null && echo "  Backend arrêté" || true
    [[ -n "${MOBILE_PID:-}"  ]] && kill "$MOBILE_PID"  2>/dev/null && echo "  Proxy mobile arrêté" || true
    [[ -n "${TTS_PID:-}"     ]] && kill "$TTS_PID"     2>/dev/null && echo "  TTS arrêté" || true
    sleep 0.5
    pkill -f "main.py --web"  2>/dev/null || true
    pkill -f "webmobile.py"   2>/dev/null || true
    pkill -f "tts_server4.py" 2>/dev/null || true
    success "Services arrêtés. À bientôt."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Attendre le processus principal (backend)
wait "${BACKEND_PID}" 2>/dev/null || true
cleanup
