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

# ── Spinner animé ─────────────────────────────────────────────
SPINNER_PID=0
spinner_start() {
    local msg="$1"
    (
        local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
        local i=0
        while true; do
            printf "\r  ${CYAN}%s${NC}  %s          " "${frames[$i]}" "$msg"
            i=$(( (i+1) % 10 ))
            sleep 0.1
        done
    ) &
    SPINNER_PID=$!
}
spinner_stop() {
    if [[ $SPINNER_PID -gt 0 ]]; then
        kill "$SPINNER_PID" 2>/dev/null || true
        wait "$SPINNER_PID" 2>/dev/null || true
        SPINNER_PID=0
    fi
    printf "\r%-72s\r" " "
}
# Arrêter le spinner proprement si le script est interrompu
trap 'spinner_stop' EXIT INT TERM

# ── Bannière ──────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
cat << 'EOF'

::::::::::: :::     :::::::::  :::     ::: ::::::::::: ::::::::
    :+:   :+: :+:   :+:    :+: :+:     :+:     :+:    :+:    :+:
    +:+  +:+   +:+  +:+    +:+ +:+     +:+     +:+    +:+
    +#+ +#++:++#++: +#++:++#:  +#+     +:+     +#+    +#++:++#++
    +#+ +#+     +#+ +#+    +#+  +#+   +#+      +#+           +#+
#+# #+# #+#     #+# #+#    #+#   #+#+#+#       #+#    #+#    #+#
 #####  ###     ### ###    ###     ###     ########### ########

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

# ── Détection Hardware ────────────────────────────────────────
detect_hardware() {
    info "Détection du matériel..."

    # RAM totale en MB
    if [[ "$OSTYPE" == "darwin"* ]]; then
        TOTAL_RAM_MB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 4294967296) / 1024 / 1024 ))
    else
        TOTAL_RAM_MB=$(awk '/MemTotal/ { print int($2/1024) }' /proc/meminfo 2>/dev/null || echo 4096)
    fi
    TOTAL_RAM_GB=$(( TOTAL_RAM_MB / 1024 ))
    [[ $TOTAL_RAM_GB -lt 1 ]] && TOTAL_RAM_GB=1

    # VRAM GPU — détection optionnelle (nvidia)
    VRAM_GB=0
    if has_cmd nvidia-smi; then
        local vram_mb
        vram_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
        [[ "$vram_mb" =~ ^[0-9]+$ ]] && VRAM_GB=$(( vram_mb / 1024 ))
    fi

    # Espace disque libre dans le répertoire courant (en GB)
    DISK_FREE_GB=$(df -BG "${HOME}" 2>/dev/null | awk 'NR==2{gsub("G",""); print int($4)}' || echo 20)
    [[ $DISK_FREE_GB -lt 1 ]] && DISK_FREE_GB=1

    info "  RAM totale   : ${TOTAL_RAM_GB} GB"
    [[ $VRAM_GB -gt 0 ]] && info "  VRAM GPU     : ${VRAM_GB} GB"
    info "  Disque libre : ${DISK_FREE_GB} GB"
}

# ── Sélection automatique du modèle Ollama adapté au matériel ─
select_ollama_models() {
    # La mémoire effective = VRAM si GPU dispo, sinon RAM système
    local effective_gb=$TOTAL_RAM_GB
    [[ $VRAM_GB -gt $effective_gb ]] && effective_gb=$VRAM_GB

    # Choix du modèle selon la RAM effective
    #   tinyllama:1.1b   ~  638 MB téléchargement,  ~0.8 GB RAM
    #   llama3.2:1b      ~ 1.3 GB téléchargement,   ~1.5 GB RAM
    #   llama3.2:3b      ~ 2.0 GB téléchargement,   ~2.5 GB RAM
    #   mistral-small3.2 ~15.0 GB téléchargement,   ~16  GB RAM
    if [[ $effective_gb -lt 3 ]]; then
        PRIMARY_MODEL="tinyllama:1.1b"
        FALLBACK_MODEL="tinyllama:1.1b"
        MAX_LOADED_MODELS=1
        HW_TIER="minimal (< 3 GB RAM) — tinyllama:1.1b"
        MIN_DISK_GB=2
    elif [[ $effective_gb -lt 6 ]]; then
        PRIMARY_MODEL="llama3.2:1b"
        FALLBACK_MODEL="llama3.2:1b"
        MAX_LOADED_MODELS=1
        HW_TIER="léger (3-6 GB RAM) — llama3.2:1b"
        MIN_DISK_GB=3
    elif [[ $effective_gb -lt 10 ]]; then
        PRIMARY_MODEL="llama3.2:3b"
        FALLBACK_MODEL="llama3.2:3b"
        MAX_LOADED_MODELS=1
        HW_TIER="standard (6-10 GB RAM) — llama3.2:3b"
        MIN_DISK_GB=4
    elif [[ $effective_gb -lt 20 ]]; then
        PRIMARY_MODEL="llama3.2:3b"
        FALLBACK_MODEL="llama3.2:3b"
        MAX_LOADED_MODELS=2
        HW_TIER="confortable (10-20 GB RAM) — llama3.2:3b"
        MIN_DISK_GB=4
    else
        PRIMARY_MODEL="llama3.2:3b"
        FALLBACK_MODEL="mistral-small3.2"
        MAX_LOADED_MODELS=2
        HW_TIER="haute performance (> 20 GB RAM) — llama3.2:3b + mistral-small3.2"
        MIN_DISK_GB=20
    fi

    # Vérification espace disque — rétrograder si insuffisant
    if [[ $DISK_FREE_GB -lt $MIN_DISK_GB ]]; then
        warn "Espace disque insuffisant (${DISK_FREE_GB} GB libre, ~${MIN_DISK_GB} GB requis)"
        PRIMARY_MODEL="tinyllama:1.1b"
        FALLBACK_MODEL="tinyllama:1.1b"
        MAX_LOADED_MODELS=1
        HW_TIER="minimal (disque limité < ${MIN_DISK_GB} GB)"
    fi

    echo ""
    echo -e "${BOLD}${CYAN}┌─ Profil matériel détecté ──────────────────────────────┐${NC}"
    echo -e "${BOLD}${CYAN}│${NC}  ${HW_TIER}"
    echo -e "${BOLD}${CYAN}│${NC}  Modèle principal : ${BOLD}${PRIMARY_MODEL}${NC}"
    [[ "$FALLBACK_MODEL" != "$PRIMARY_MODEL" ]] && \
    echo -e "${BOLD}${CYAN}│${NC}  Modèle fallback  : ${BOLD}${FALLBACK_MODEL}${NC}"
    echo -e "${BOLD}${CYAN}│${NC}  Modèles en RAM   : ${MAX_LOADED_MODELS}"
    echo -e "${BOLD}${CYAN}└────────────────────────────────────────────────────────┘${NC}"
    echo ""
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

    # S'assurer que python3-venv est installé AVANT de créer le venv
    if [[ "$OS" == "Linux" || "$OS" == "WSL" ]]; then
        local PY_VER
        PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        info "Installation de python${PY_VER}-venv..."
        # Essayer le paquet spécifique à la version, puis le générique
        sudo apt-get install -y "python${PY_VER}-venv" python3-venv python3-pip 2>/dev/null \
            || sudo apt-get install -y python3-venv python3-pip 2>/dev/null \
            || { warn "Impossible d'installer python-venv via apt. Tentative pip..."; python3 -m ensurepip --upgrade 2>/dev/null || true; }
    fi

    # Recréer le venv si le dossier existe mais est cassé (activate manquant)
    if [[ -d "venv" && ! -f "venv/bin/activate" ]]; then
        warn "Environnement virtuel corrompu détecté, recréation..."
        rm -rf venv
    fi
    if [[ ! -d "venv" ]]; then
        if ! python3 -m venv venv 2>/dev/null; then
            warn "python3 -m venv a échoué — tentative de réinstallation forcée..."
            local PY_VER
            PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            sudo apt-get install -y --fix-missing "python${PY_VER}-venv" 2>&1 | grep -v "^$" || true
            python3 -m venv venv || die "Impossible de créer l'environnement virtuel. Lancez: sudo apt install python${PY_VER}-venv"
        fi
        success "Environnement virtuel créé"
    else
        info "Environnement virtuel déjà présent, réutilisation"
    fi

    # shellcheck source=/dev/null
    source venv/bin/activate
    # /tmp est souvent un tmpfs limité (~RAM/2) sur Ubuntu — utiliser le disque réel
    mkdir -p "${REPO_DIR}/.pip-tmp"
    export TMPDIR="${REPO_DIR}/.pip-tmp"
    export PIP_NO_CACHE_DIR=1
    pip install --upgrade pip --quiet --no-cache-dir
    success "Environnement virtuel activé"
}

# ── Dépendances Python ────────────────────────────────────────
install_python_deps() {
    # Diagnostic inodes avant d'installer
    local inodes_pct
    inodes_pct=$(df -i "$REPO_DIR" 2>/dev/null | awk 'NR==2{gsub("%",""); print $5}' || echo 0)
    if [[ "$inodes_pct" =~ ^[0-9]+$ && $inodes_pct -ge 90 ]]; then
        warn "Inodes utilisés à ${inodes_pct}% — risque d'erreur EDQUOT !"
    fi

    # TMPDIR sur le disque réel (évite le débordement du tmpfs /tmp ~RAM/2 sur Ubuntu)
    mkdir -p "${REPO_DIR}/.pip-tmp"
    export TMPDIR="${REPO_DIR}/.pip-tmp"
    export PIP_NO_CACHE_DIR=1

    local total_pkgs
    total_pkgs=$(grep -cE '^[^#[:space:]]' requirements.txt 2>/dev/null || echo "?")
    info "Installation des dépendances Python — ${total_pkgs} paquets (peut prendre 2-5 min)..."
    echo ""

    # ── requirements.txt ──────────────────────────────────────
    spinner_start "requirements.txt  [${total_pkgs} paquets] ..."
    if pip install -r requirements.txt --no-cache-dir --quiet; then
        spinner_stop
        success "Dépendances principales OK"
    else
        spinner_stop
        die "Échec pip install requirements.txt"
    fi

    # ── chromadb (mémoire vectorielle) ─────────────────────────
    spinner_start "chromadb  [mémoire vectorielle] ..."
    if pip install chromadb --no-cache-dir --quiet 2>/dev/null; then
        spinner_stop
        success "chromadb OK"
    else
        spinner_stop
        warn "chromadb non installé (mémoire vectorielle désactivée)"
    fi

    # ── mistralai (TTS Voxtral) ────────────────────────────────
    spinner_start "mistralai  [TTS Voxtral] ..."
    if pip install mistralai --no-cache-dir --quiet 2>/dev/null; then
        spinner_stop
        success "mistralai OK"
    else
        spinner_stop
        warn "mistralai non installé (TTS Voxtral désactivé)"
    fi

    # Nettoyer le dossier tmp pip
    rm -rf "${REPO_DIR}/.pip-tmp"
    echo ""
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

# ── Performance Ollama ────────────────────────────────────────
configure_ollama_perf() {
    info "Configuration des performances Ollama..."

    # CPU cores pour OLLAMA_NUM_THREAD
    CPU_CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "4")

    # Sur machines < 6 GB RAM : garder 1 seul modèle chargé pour éviter le swap
    local max_loaded="${MAX_LOADED_MODELS:-1}"

    # Créer/patcher le fichier d'environment Ollama
    if [[ "$OS" == "Linux" || "$OS" == "WSL" ]] && systemctl is-active --quiet ollama 2>/dev/null; then
        info "Patchage de /etc/systemd/system/ollama.service..."
        sudo mkdir -p /etc/systemd/system

        # Sauvegarder l'original si présent
        [[ -f /etc/systemd/system/ollama.service ]] && \
            sudo cp /etc/systemd/system/ollama.service /etc/systemd/system/ollama.service.bak

        # Patcher les variables d'environment (supprimer les anciennes entrées d'abord)
        if [[ -f /etc/systemd/system/ollama.service ]]; then
            sudo sed -i '/OLLAMA_KEEP_ALIVE\|OLLAMA_MAX_LOADED\|OLLAMA_NUM_THREAD/d' \
                /etc/systemd/system/ollama.service 2>/dev/null || true
            sudo sed -i '/^\[Service\]/a Environment="OLLAMA_KEEP_ALIVE=-1"' \
                /etc/systemd/system/ollama.service 2>/dev/null || true
            sudo sed -i "/^\[Service\]/a Environment=\"OLLAMA_MAX_LOADED_MODELS=${max_loaded}\"" \
                /etc/systemd/system/ollama.service 2>/dev/null || true
            sudo sed -i "/^\[Service\]/a Environment=\"OLLAMA_NUM_THREAD=${CPU_CORES}\"" \
                /etc/systemd/system/ollama.service 2>/dev/null || true
            sudo systemctl daemon-reload
            sudo systemctl restart ollama
            success "Ollama configuré : KEEP_ALIVE=-1, MAX_LOADED_MODELS=${max_loaded}, NUM_THREAD=${CPU_CORES}"
        fi
    else
        info "Ollama systemd service non trouvé — définissez ces variables dans votre shell :"
        info "  export OLLAMA_KEEP_ALIVE=-1"
        info "  export OLLAMA_MAX_LOADED_MODELS=${max_loaded}"
        info "  export OLLAMA_NUM_THREAD=${CPU_CORES}"
    fi
}

# ── Modèles Ollama ────────────────────────────────────────────
pull_ollama_models() {
    # Construire la liste des modèles à télécharger (dédupliquée)
    local models_to_pull=("$PRIMARY_MODEL")
    [[ "$FALLBACK_MODEL" != "$PRIMARY_MODEL" ]] && models_to_pull+=("$FALLBACK_MODEL")

    # Calculer la taille approximative pour informer l'utilisateur
    local total_size="?"
    case "$PRIMARY_MODEL" in
        tinyllama*)        total_size="~700 MB" ;;
        llama3.2:1b*)      total_size="~1.3 GB" ;;
        llama3.2:3b*)      total_size="~2 GB" ;;
    esac
    [[ "$FALLBACK_MODEL" == "mistral-small3.2" ]] && total_size="~17 GB (llama3.2:3b + mistral-small3.2)"

    info "Téléchargement des modèles Ollama (${total_size})..."

    pull_model() {
        local model="$1"
        # ollama list affiche "nom:tag   ..." — on vérifie le début de ligne
        if ollama list 2>/dev/null | awk '{print $1}' | grep -qx "${model}"; then
            success "Modèle $model déjà présent"
        else
            info "Téléchargement de $model..."
            if ollama pull "$model"; then
                success "Modèle $model téléchargé"
            else
                warn "Échec du téléchargement de $model. Réessayez : ollama pull $model"
            fi
        fi
    }

    for m in "${models_to_pull[@]}"; do
        pull_model "$m"
    done
}

# ── Fichier .env ──────────────────────────────────────────────
setup_env() {
    info "Configuration du fichier .env..."
    if [[ -f ".env" ]]; then
        warn ".env déjà présent. Paramètres existants conservés."
        return
    fi

    cp .env.example .env

    # Modèles sélectionnés automatiquement selon le matériel détecté
    local default_model="ollama/${PRIMARY_MODEL}"
    local fallback_model="ollama/${FALLBACK_MODEL}"

    if [[ "$OS" == "macOS" ]]; then
        sed -i '' \
            -e "s|^JARVIS_DEFAULT_MODEL=.*|JARVIS_DEFAULT_MODEL=${default_model}|" \
            -e "s|^JARVIS_ROUTING_MODEL=.*|JARVIS_ROUTING_MODEL=${default_model}|" \
            -e "s|^JARVIS_FALLBACK_MODEL=.*|JARVIS_FALLBACK_MODEL=${fallback_model}|" \
            .env
    else
        sed -i \
            -e "s|^JARVIS_DEFAULT_MODEL=.*|JARVIS_DEFAULT_MODEL=${default_model}|" \
            -e "s|^JARVIS_ROUTING_MODEL=.*|JARVIS_ROUTING_MODEL=${default_model}|" \
            -e "s|^JARVIS_FALLBACK_MODEL=.*|JARVIS_FALLBACK_MODEL=${fallback_model}|" \
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

    # Résoudre le binaire pm2 (peut être dans un chemin non standard après npm install -g)
    find_pm2() {
        command -v pm2 2>/dev/null \
            || command -v "$(npm root -g 2>/dev/null)/../bin/pm2" 2>/dev/null \
            || echo ""
    }

    PM2_BIN="$(find_pm2)"

    if [[ -n "$PM2_BIN" ]]; then
        success "PM2 déjà installé : $("$PM2_BIN" --version 2>/dev/null || echo 'version inconnue')"
    else
        if ! has_cmd npm; then
            warn "npm non disponible, PM2 non installé"
            warn "Pour installer PM2 manuellement : npm install -g pm2"
            return
        fi

        info "Installation de pm2 via npm..."
        npm install -g pm2 2>&1 | tail -5 || true

        # Chercher pm2 après l'installation (le chemin global npm peut ne pas être dans PATH)
        NPM_GLOBAL_BIN="$(npm bin -g 2>/dev/null || npm root -g 2>/dev/null | sed 's|/node_modules||')"/bin
        export PATH="$NPM_GLOBAL_BIN:$PATH"

        PM2_BIN="$(find_pm2)"
        if [[ -z "$PM2_BIN" ]]; then
            warn "pm2 non trouvé après installation. Chemin npm global : $NPM_GLOBAL_BIN"
            warn "Ajoutez '$NPM_GLOBAL_BIN' à votre PATH, puis : pm2 start $REPO_DIR/ecosystem.config.js"
            return
        fi
        success "PM2 installé : $("$PM2_BIN" --version)"
    fi

    # Utiliser le chemin absolu pour les appels PM2 suivants
    info "Configuration de PM2 pour les services JARVIS..."
    "$PM2_BIN" start "$REPO_DIR/ecosystem.config.js" 2>/dev/null || true
    "$PM2_BIN" save --force 2>/dev/null || true
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
    echo -e "${BOLD}Profil matériel :${NC} ${HW_TIER}"
    echo -e "${BOLD}Modèle LLM      :${NC} ${PRIMARY_MODEL}"
    echo ""
    echo -e "${BOLD}Démarrer JARVIS :${NC}"
    echo ""
    echo -e "  ${CYAN}# Avec PM2 (recommandé — auto-restart, démarrage au boot)${NC}"
    echo -e "  ${CYAN}bash ${REPO_DIR}/pm2-manager.sh start${NC}"
    echo ""
    echo -e "  ${CYAN}# Ou directement (session terminal)${NC}"
    echo -e "  ${CYAN}bash ${REPO_DIR}/launch-JARVIS.sh${NC}"
    echo ""
    echo -e "${BOLD}Si 'pm2: command not found' après l'installation :${NC}"
    echo -e "  ${CYAN}export PATH=\"\$(npm root -g | sed 's|/node_modules||')/bin:\$PATH\"${NC}"
    echo -e "  ${CYAN}echo 'export PATH=\"\$(npm root -g | sed '"'"'s|/node_modules||'"'"')/bin:\$PATH\"' >> ~/.bashrc${NC}"
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
    detect_hardware
    select_ollama_models
    install_system_deps
    setup_repo_dir
    setup_venv
    install_python_deps
    install_ollama
    configure_ollama_perf
    pull_ollama_models
    setup_env
    install_mobile_deps
    install_pm2
    run_validation
    print_success
}

main
