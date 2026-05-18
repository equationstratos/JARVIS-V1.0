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

        # Si le script est lancé via curl|bash, se réexécuter depuis le repo local
        # pour s'assurer de tourner sur la version mise à jour (évite le cache CDN GitHub)
        local local_script="$REPO_DIR/install-JARVIS-V1.0.sh"
        if [[ -f "$local_script" && "$(realpath "$0" 2>/dev/null || echo "$0")" != "$(realpath "$local_script" 2>/dev/null || echo "$local_script")" ]]; then
            info "Relance depuis le repo local (version à jour)..."
            exec bash "$local_script"
        fi
    fi

    cd "$REPO_DIR"
    success "Répertoire: $REPO_DIR"
}

# ── Environnement virtuel Python ──────────────────────────────
setup_venv() {
    info "Configuration de l'environnement Python..."
    # Recréer le venv si le dossier existe mais est cassé (activate manquant)
    if [[ -d "venv" && ! -f "venv/bin/activate" ]]; then
        warn "Environnement virtuel corrompu détecté, recréation..."
        rm -rf venv
    fi
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

    # ── Whitelist IP (interactive) ──────────────────────────────
    setup_ip_whitelist
}

setup_ip_whitelist() {
    echo ""
    echo -e "${BOLD}Sécurité — Filtrage IP (whitelist)${NC}"
    echo -e "  Par défaut, JARVIS accepte toutes les connexions."
    echo -e "  Vous pouvez restreindre l'accès à certaines IPs seulement."
    echo -e "  (Les IPs locales 192.168.x.x / 10.x.x.x sont toujours autorisées)"
    echo ""

    # Pas de prompt si stdin n'est pas un terminal (ex: curl | bash)
    if [[ ! -t 0 ]]; then
        warn "Mode non-interactif détecté — whitelist IP désactivée par défaut."
        warn "Activez-la manuellement : python main.py --authorize-ip=VOTRE_IP"
        return
    fi

    local enable_whitelist="n"
    read -r -p "$(echo -e "${CYAN}Activer la whitelist IP ? (o/N) :${NC} ")" enable_whitelist
    enable_whitelist="${enable_whitelist,,}"  # lowercase

    if [[ "$enable_whitelist" != "o" && "$enable_whitelist" != "oui" && "$enable_whitelist" != "y" && "$enable_whitelist" != "yes" ]]; then
        info "Whitelist IP désactivée. Tout le monde peut accéder à JARVIS."
        return
    fi

    # Activer dans .env
    if [[ "$OS" == "macOS" ]]; then
        sed -i '' 's|^ENABLE_IP_WHITELIST=.*|ENABLE_IP_WHITELIST=true|' .env
    else
        sed -i 's|^ENABLE_IP_WHITELIST=.*|ENABLE_IP_WHITELIST=true|' .env
    fi

    echo ""
    echo -e "  Entrez les IPs autorisées ${BOLD}séparées par des virgules${NC}"
    echo -e "  Exemple : ${CYAN}82.225.100.200,176.158.10.20${NC}"
    echo -e "  (Laissez vide pour n'autoriser que le réseau local)"
    echo ""
    read -r -p "$(echo -e "${CYAN}IPs autorisées :${NC} ")" ip_input

    if [[ -n "$ip_input" ]]; then
        # Valider et nettoyer les IPs
        local valid_ips=()
        IFS=',' read -ra ip_list <<< "$ip_input"
        for ip in "${ip_list[@]}"; do
            ip="${ip// /}"  # strip spaces
            if python3 -c "import ipaddress; ipaddress.ip_address('$ip')" 2>/dev/null; then
                valid_ips+=("$ip")
            else
                warn "IP ignorée (format invalide) : $ip"
            fi
        done

        if [[ ${#valid_ips[@]} -gt 0 ]]; then
            local ips_joined
            ips_joined=$(IFS=','; echo "${valid_ips[*]}")
            if [[ "$OS" == "macOS" ]]; then
                sed -i '' "s|^ALLOWED_IPS=.*|ALLOWED_IPS=${ips_joined}|" .env
            else
                sed -i "s|^ALLOWED_IPS=.*|ALLOWED_IPS=${ips_joined}|" .env
            fi
            success "Whitelist activée pour : ${ips_joined}"
        fi
    else
        info "Aucune IP externe ajoutée — seul le réseau local a accès."
    fi

    echo ""
    info "Pour ajouter une IP plus tard : ${BOLD}python main.py --authorize-ip=82.1.2.3${NC}"
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

    if ! has_cmd npm; then
        warn "npm non disponible — PM2 non installé (app mobile requise)"
        return
    fi

    # Installer pm2 dans ~/.npm-global (sans sudo, fonctionne partout)
    local NPM_GLOBAL="$HOME/.npm-global"
    mkdir -p "$NPM_GLOBAL"
    npm config set prefix "$NPM_GLOBAL" 2>/dev/null || true
    export PATH="$NPM_GLOBAL/bin:$PATH"

    # Ajouter au PATH de façon permanente dans ~/.bashrc
    if ! grep -q "npm-global" "$HOME/.bashrc" 2>/dev/null; then
        echo "export PATH=\"$NPM_GLOBAL/bin:\$PATH\"" >> "$HOME/.bashrc"
    fi

    local PM2_BIN="$NPM_GLOBAL/bin/pm2"

    if [[ -x "$PM2_BIN" ]]; then
        success "PM2 déjà installé : $("$PM2_BIN" --version 2>/dev/null | tail -1)"
    else
        info "Installation de pm2..."
        npm install -g pm2 2>&1 | grep -E "^(added|npm error)" | head -3 || true

        if [[ ! -x "$PM2_BIN" ]]; then
            warn "PM2 introuvable après installation — vérifiez les logs npm ci-dessus"
            return
        fi
        success "PM2 installé : $("$PM2_BIN" --version 2>/dev/null | tail -1)"
    fi

    # Rendre pm2 disponible immédiatement dans le shell courant via symlink
    sudo ln -sf "$PM2_BIN" /usr/local/bin/pm2 2>/dev/null \
        || ln -sf "$PM2_BIN" "$HOME/.local/bin/pm2" 2>/dev/null || true

    info "Démarrage des services JARVIS via PM2..."
    "$PM2_BIN" start "$REPO_DIR/ecosystem.config.js" 2>/dev/null || true
    "$PM2_BIN" save --force 2>/dev/null || true
    success "Services PM2 démarrés et sauvegardés"

    # Configurer le démarrage automatique au boot (silencieux)
    local startup_cmd
    startup_cmd=$("$PM2_BIN" startup 2>/dev/null | grep "^sudo env" | head -1)
    if [[ -n "$startup_cmd" ]]; then
        info "Activation du démarrage automatique au boot..."
        eval "$startup_cmd" 2>/dev/null && "$PM2_BIN" save --force 2>/dev/null \
            && success "Démarrage automatique au boot activé" \
            || warn "Démarrage auto au boot : exécutez 'pm2 startup' et collez la commande sudo affichée"
    fi
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
    echo -e "${BOLD}JARVIS est démarré via PM2 (auto-restart actif) :${NC}"
    echo ""
    echo -e "  ${CYAN}pm2 status${NC}      — voir l'état des services"
    echo -e "  ${CYAN}pm2 logs${NC}        — logs en temps réel"
    echo -e "  ${CYAN}pm2 restart all${NC} — redémarrer tout"
    echo ""
    echo -e "${BOLD}Si PM2 n'est pas dans votre PATH (nouveau terminal) :${NC}"
    echo -e "  ${CYAN}source ~/.bashrc${NC}  — recharger le PATH"
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
