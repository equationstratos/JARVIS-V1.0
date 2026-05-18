#!/usr/bin/env bash
# ==============================================================
# JARVIS-V1.0 — Installateur complet
#
# Usage (one-liner) :
#   curl -sSL https://raw.githubusercontent.com/equationstratos/jarvis-v1.0/main/install-JARVIS-V1.0.sh | bash
#
# Ou localement :
#   bash install-JARVIS-V1.0.sh
# ==============================================================
set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Bannière ──────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
cat << 'EOF'
     _   _    _   _____  __   __ ___ ____
    | | / \  | | |  __ \ \ \ / /|_ _/ ___|
 _  | |/ _ \ | | | |__) | \ V /  | |\___ \
| |_| / ___ \| |___  _ <   | |   | | ___) |
 \___/_/   \_\_____|_| \_\  |_|  |___|____/

  Modular Agentic AI Ecosystem — Installer v1.0
EOF
echo -e "${NC}"

# ── Détection OS ──────────────────────────────────────────────
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if grep -qi microsoft /proc/version 2>/dev/null; then
            OS="WSL"
        else
            OS="Linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
    else
        die "OS non supporté: $OSTYPE. Utilisez Linux, macOS ou WSL2."
    fi
    info "OS détecté: $OS"
}

# ── Vérification d'une commande ───────────────────────────────
has_cmd() { command -v "$1" &>/dev/null; }

# ── Dépendances système ───────────────────────────────────────
install_system_deps() {
    info "Vérification des dépendances système..."

    local missing=()
    for cmd in python3 curl git; do
        has_cmd "$cmd" || missing+=("$cmd")
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Manquant: ${missing[*]}"
        if [[ "$OS" == "Linux" || "$OS" == "WSL" ]]; then
            sudo apt-get update -qq
            for pkg in "${missing[@]}"; do
                case "$pkg" in
                    python3) sudo apt-get install -y python3 python3-venv python3-pip ;;
                    curl)    sudo apt-get install -y curl ;;
                    git)     sudo apt-get install -y git ;;
                esac
            done
        elif [[ "$OS" == "macOS" ]]; then
            has_cmd brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            for pkg in "${missing[@]}"; do
                case "$pkg" in
                    python3) brew install python3 ;;
                    curl)    brew install curl ;;
                    git)     brew install git ;;
                esac
            done
        fi
    fi

    # Toujours s'assurer que python3-venv est installé (Ubuntu peut avoir python3 sans venv)
    if [[ "$OS" == "Linux" || "$OS" == "WSL" ]]; then
        PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        sudo apt-get install -y -qq "python3.${PY_VER##*.}-venv" python3-venv python3-pip 2>/dev/null \
            || sudo apt-get install -y -qq python3-venv python3-pip 2>/dev/null || true
    fi

    # Python >= 3.10
    local py_ver
    py_ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local py_major py_minor
    py_major=$(echo "$py_ver" | cut -d. -f1)
    py_minor=$(echo "$py_ver" | cut -d. -f2)
    if [[ "$py_major" -lt 3 || ("$py_major" -eq 3 && "$py_minor" -lt 10) ]]; then
        die "Python 3.10+ requis. Trouvé: $py_ver"
    fi
    success "Python $py_ver"

    # Node.js (optionnel, pour l'app mobile)
    if ! has_cmd node; then
        warn "Node.js non trouvé. Installation (requis pour l'app mobile)..."
        if [[ "$OS" == "Linux" || "$OS" == "WSL" ]]; then
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - 2>/dev/null
            sudo apt-get install -y nodejs
        elif [[ "$OS" == "macOS" ]]; then
            brew install node
        fi
    fi
    has_cmd node && success "Node.js $(node --version)" || warn "Node.js non disponible (app mobile désactivée)"
    success "Dépendances système OK"
}

# ── Dossier du repo ───────────────────────────────────────────
setup_repo_dir() {
    # Si on est déjà dans le repo
    if [[ -f "./main.py" && -f "./config.py" && -f "./requirements.txt" ]]; then
        REPO_DIR="$(pwd)"
        info "Repo détecté dans le dossier courant: $REPO_DIR"
    else
        REPO_DIR="$HOME/JARVIS-V1.0"
        if [[ -d "$REPO_DIR/.git" ]]; then
            info "Repo existant trouvé, mise à jour..."
            git -C "$REPO_DIR" pull origin main 2>/dev/null || git -C "$REPO_DIR" pull 2>/dev/null || true
        else
            info "Clonage du repo..."
            git clone https://github.com/equationstratos/jarvis-v1.0.git "$REPO_DIR"
        fi
    fi

    cd "$REPO_DIR"
    success "Répertoire: $REPO_DIR"
}

# ── Environnement virtuel Python ──────────────────────────────
setup_venv() {
    info "Configuration de l'environnement Python..."
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        success "Environnement virtuel créé"
    else
        info "Environnement virtuel déjà présent, réutilisation"
    fi

    # shellcheck source=/dev/null
    source venv/bin/activate
    pip install --upgrade pip --quiet
    success "Environnement virtuel activé"
}

# ── Dépendances Python ────────────────────────────────────────
install_python_deps() {
    info "Installation des dépendances Python (peut prendre quelques minutes)..."
    pip install -r requirements.txt --quiet
    # chromadb est utilisé par web_v2.py mais pas encore dans requirements.txt
    pip install chromadb --quiet 2>/dev/null || warn "chromadb non installé (mémoire vectorielle désactivée)"
    # mistralai est requis pour le serveur TTS Voxtral
    pip install mistralai --quiet 2>/dev/null || warn "mistralai non installé (TTS Voxtral désactivé)"
    success "Dépendances Python installées"
}

# ── Ollama ────────────────────────────────────────────────────
install_ollama() {
    info "Vérification d'Ollama..."
    if has_cmd ollama; then
        success "Ollama déjà installé: $(ollama --version 2>/dev/null || echo 'version inconnue')"
    else
        info "Installation d'Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh
        success "Ollama installé"
    fi

    # Démarrer ollama serve si pas actif
    if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
        info "Démarrage du serveur Ollama..."
        ollama serve &>/dev/null &
        OLLAMA_BG_PID=$!
        local waited=0
        while ! curl -s http://localhost:11434/api/tags &>/dev/null; do
            sleep 1
            waited=$((waited + 1))
            [[ $waited -ge 30 ]] && { warn "Ollama ne répond pas après 30s. Lancez 'ollama serve' manuellement."; return; }
        done
        success "Serveur Ollama démarré (PID $OLLAMA_BG_PID)"
    else
        info "Serveur Ollama déjà en cours d'exécution"
    fi
}

# ── Modèles Ollama ────────────────────────────────────────────
pull_ollama_models() {
    info "Téléchargement des modèles Ollama (peut prendre du temps, ~5-8 GB)..."

    pull_model() {
        local model="$1"
        if ollama list 2>/dev/null | grep -q "^${model}"; then
            success "Modèle $model déjà présent"
        else
            info "Téléchargement de $model..."
            if ollama pull "$model"; then
                success "Modèle $model téléchargé"
            else
                warn "Échec du téléchargement de $model. Réessayez: ollama pull $model"
            fi
        fi
    }

    pull_model "mistral-small3.2"
    pull_model "llama3"
}

# ── Fichier .env ──────────────────────────────────────────────
setup_env() {
    info "Configuration du fichier .env..."
    if [[ -f ".env" ]]; then
        warn ".env déjà présent. Paramètres existants conservés."
        return
    fi

    cp .env.example .env

    # Defaults Ollama (local, gratuit, sans clé API)
    if [[ "$OS" == "macOS" ]]; then
        sed -i '' \
            -e 's|^JARVIS_DEFAULT_MODEL=.*|JARVIS_DEFAULT_MODEL=ollama/mistral-small3.2|' \
            -e 's|^JARVIS_ROUTING_MODEL=.*|JARVIS_ROUTING_MODEL=ollama/mistral-small3.2|' \
            -e 's|^JARVIS_FALLBACK_MODEL=.*|JARVIS_FALLBACK_MODEL=ollama/llama3|' \
            .env
    else
        sed -i \
            -e 's|^JARVIS_DEFAULT_MODEL=.*|JARVIS_DEFAULT_MODEL=ollama/mistral-small3.2|' \
            -e 's|^JARVIS_ROUTING_MODEL=.*|JARVIS_ROUTING_MODEL=ollama/mistral-small3.2|' \
            -e 's|^JARVIS_FALLBACK_MODEL=.*|JARVIS_FALLBACK_MODEL=ollama/llama3|' \
            .env
    fi

    success ".env créé avec les defaults Ollama"
    echo ""
    info "  (Optionnel) Ajoutez vos clés cloud dans .env :"
    info "    ANTHROPIC_API_KEY=sk-ant-...   (Claude)"
    info "    GOOGLE_API_KEY=...             (Gemini)"
    info "    MISTRAL_API_KEY=...            (Voxtral TTS)"
}

# ── App mobile ────────────────────────────────────────────────
install_mobile_deps() {
    if [[ -d "mobile" && -f "mobile/package.json" ]]; then
        if has_cmd npm; then
            info "Installation des dépendances de l'app mobile..."
            (cd mobile && npm install --silent)
            success "Dépendances mobile installées"
        else
            warn "npm non disponible, installation mobile ignorée"
        fi
    fi
}

# ── PM2 (gestionnaire de services) ───────────────────────────
install_pm2() {
    info "Installation de PM2 (gestionnaire de services)..."
    if has_cmd pm2; then
        success "PM2 déjà installé : $(pm2 --version)"
    else
        if has_cmd npm; then
            npm install -g pm2 --silent
            success "PM2 installé : $(pm2 --version)"
        else
            warn "npm non disponible, PM2 non installé"
            warn "Pour installer PM2 manuellement : npm install -g pm2"
            return
        fi
    fi

    info "Configuration de PM2 pour les services JARVIS..."
    # Démarrer les services une première fois pour les enregistrer dans PM2
    pm2 start "$REPO_DIR/ecosystem.config.js" 2>/dev/null || true
    pm2 save --force 2>/dev/null || true
    success "Services PM2 enregistrés"
    echo ""
    warn "IMPORTANT : Pour activer le redémarrage automatique au boot :"
    warn "  1. Exécutez : pm2 startup"
    warn "  2. Copiez-collez la commande 'sudo env...' qui s'affiche"
    warn "  3. Puis : pm2 save"
}

# ── Validation basique ────────────────────────────────────────
run_validation() {
    info "Validation de l'installation..."
    if python3 TESTS/test_load.py; then
        success "test_load.py OK"
    else
        warn "test_load.py — vérifiez la configuration .env"
    fi
}

# ── Message final ─────────────────────────────────────────────
print_success() {
    echo ""
    echo -e "${GREEN}${BOLD}================================================${NC}"
    echo -e "${GREEN}${BOLD}   JARVIS-V1.0 installé avec succès !${NC}"
    echo -e "${GREEN}${BOLD}================================================${NC}"
    echo ""
    echo -e "${BOLD}Démarrer JARVIS :${NC}"
    echo ""
    echo -e "  ${CYAN}# Avec PM2 (recommandé — auto-restart, démarrage au boot)${NC}"
    echo -e "  ${CYAN}bash ${REPO_DIR}/pm2-manager.sh start${NC}"
    echo ""
    echo -e "  ${CYAN}# Ou directement (session terminal)${NC}"
    echo -e "  ${CYAN}bash ${REPO_DIR}/launch-JARVIS.sh${NC}"
    echo ""
    echo -e "${BOLD}Activer le démarrage automatique au boot (PM2) :${NC}"
    echo -e "  ${CYAN}pm2 startup${NC}  ← coller la commande sudo affichée"
    echo -e "  ${CYAN}pm2 save${NC}"
    echo ""
    echo -e "${BOLD}Services disponibles :${NC}"
    echo -e "  Web UI          →  http://localhost:8501"
    echo -e "  Mobile UI       →  http://localhost:3001"
    echo -e "  TTS Voxtral     →  http://localhost:8001  (si MISTRAL_API_KEY)"
    echo -e "  TTS Kokoro      →  http://localhost:8000  (si ../jarvis-voice/)"
    echo ""
    echo -e "${BOLD}Commandes PM2 utiles :${NC}"
    echo -e "  pm2 status          — état de tous les services"
    echo -e "  pm2 logs            — logs en temps réel"
    echo -e "  pm2 monit           — tableau de bord interactif"
    echo -e "  pm2 restart all     — redémarrer tout"
    echo ""
    echo -e "${BOLD}App mobile native (React Native) :${NC}"
    echo -e "  cd mobile && npx expo start"
    echo ""
    echo -e "${BOLD}Lancer les tests :${NC}"
    echo -e "  source venv/bin/activate"
    echo -e "  python TESTS/test_load.py"
    echo -e "  python TESTS/test_configuration.py"
    echo ""
    echo -e "${BOLD}Documentation :${NC} README.md"
    echo ""
}

# ── Point d'entrée ────────────────────────────────────────────
main() {
    detect_os
    install_system_deps
    setup_repo_dir
    setup_venv
    install_python_deps
    install_ollama
    pull_ollama_models
    setup_env
    install_mobile_deps
    install_pm2
    run_validation
    print_success
}

main
