#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# JARVIS V14 — Lanceur unifié (web + TTS)
# ─────────────────────────────────────────────────────────────────

# Couleurs pour le log
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# Aller au dossier du script (= racine du projet V14)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Chemins (à adapter si la structure change)
JARVIS_DIR="$SCRIPT_DIR"
TTS_DIR="$(cd "$SCRIPT_DIR/../jarvis-voice" 2>/dev/null && pwd)"

echo -e "${CYAN}🚀 JARVIS V14 — Démarrage${NC}"
echo -e "   Projet : $JARVIS_DIR"
echo -e "   TTS    : ${TTS_DIR:-non trouvé}"
echo ""

# ── 1. Tuer les anciens processus ──
echo -e "${YELLOW}🛑 Nettoyage des processus existants...${NC}"
pkill -f "tts_server4.py" 2>/dev/null && echo "   - ancien TTS arrêté"
pkill -f "web_v2.py" 2>/dev/null && echo "   - ancien web arrêté"
pkill -f "main.py --web" 2>/dev/null && echo "   - ancien main.py arrêté"
sleep 1

# ── 2. Activer le venv ──
if [ ! -f "$JARVIS_DIR/venv/bin/activate" ]; then
    echo -e "${RED}❌ venv introuvable dans $JARVIS_DIR/venv${NC}"
    echo "   Crée-le avec : python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
source "$JARVIS_DIR/venv/bin/activate"
echo -e "${GREEN}✓ venv activé : $(which python)${NC}"

# ── 3. Démarrer le serveur TTS (Kokoro) ──
TTS_PID=""
if [ -n "$TTS_DIR" ] && [ -f "$TTS_DIR/tts_server4.py" ]; then
    echo -e "${YELLOW}🔊 Démarrage TTS Kokoro...${NC}"
    cd "$TTS_DIR"
    if [ -f "venv/bin/activate" ]; then
        # Lance dans un sous-shell pour ne pas désactiver notre venv
        (source venv/bin/activate && python3 tts_server4.py) > "$JARVIS_DIR/tts.log" 2>&1 &
    else
        python3 tts_server4.py > "$JARVIS_DIR/tts.log" 2>&1 &
    fi
    TTS_PID=$!
    cd "$JARVIS_DIR"
    echo -e "${GREEN}✓ TTS lancé (PID $TTS_PID) → log : tts.log${NC}"
    # Attend que le port 8000 soit ouvert (max 30s)
    for i in {1..30}; do
        if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then
            echo -e "${GREEN}✓ TTS prêt sur :8000${NC}"
            break
        fi
        sleep 1
    done
else
    echo -e "${YELLOW}⚠ TTS Kokoro non trouvé, mode texte uniquement${NC}"
fi

# ── 4. Démarrer le serveur principal JARVIS ──
echo -e "${YELLOW}🤖 Démarrage JARVIS Web (V14)...${NC}"
python "$JARVIS_DIR/main.py" --web &
MAIN_PID=$!
echo -e "${GREEN}✓ JARVIS Web lancé (PID $MAIN_PID)${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo -e "${CYAN}  JARVIS V14 prêt sur :${NC}"
echo -e "${CYAN}    → http://localhost:8501${NC}"
if [ -n "$TTS_PID" ]; then
    echo -e "${CYAN}    → TTS Kokoro sur :8000${NC}"
fi
echo -e "${CYAN}  Ctrl+C pour tout arrêter${NC}"
echo -e "${CYAN}═══════════════════════════════════════════${NC}"

# ── 5. Cleanup propre sur Ctrl+C ──
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Arrêt en cours...${NC}"
    [ -n "$MAIN_PID" ] && kill $MAIN_PID 2>/dev/null
    [ -n "$TTS_PID" ] && kill $TTS_PID 2>/dev/null
    sleep 1
    # Force-kill si encore vivants
    pkill -f "tts_server4.py" 2>/dev/null
    pkill -f "main.py --web" 2>/dev/null
    pkill -f "web_v2.py" 2>/dev/null
    echo -e "${GREEN}✓ Tous les services arrêtés${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Attend la fin du processus principal
wait $MAIN_PID
cleanup
