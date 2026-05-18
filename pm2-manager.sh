#!/usr/bin/env bash
# ==============================================================
# JARVIS-V1.0 — Gestionnaire PM2
#
# Gère tous les services JARVIS via PM2 (auto-restart, boot, logs)
#
# Usage :
#   bash pm2-manager.sh start    # Démarrer tous les services
#   bash pm2-manager.sh stop     # Arrêter tous les services
#   bash pm2-manager.sh restart  # Redémarrer tous les services
#   bash pm2-manager.sh status   # Voir l'état des services
#   bash pm2-manager.sh logs     # Voir les logs en temps réel
#   bash pm2-manager.sh install  # Installer PM2 + activer au démarrage
# ==============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info()    { echo -e "${CYAN}[JARVIS]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Vérifications ─────────────────────────────────────────────
if ! command -v pm2 &>/dev/null; then
    error "PM2 n'est pas installé."
    echo "Installez-le avec : npm install -g pm2"
    echo "Ou lancez :         bash pm2-manager.sh install"
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/venv/bin/python" ]]; then
    error "Environnement virtuel Python introuvable."
    error "Lancez d'abord l'installateur : bash install-JARVIS-V1.0.sh"
    exit 1
fi

# ── Crée le dossier Logs si besoin ────────────────────────────
mkdir -p "$SCRIPT_DIR/Logs"

# ── Commandes ─────────────────────────────────────────────────
CMD="${1:-status}"

case "$CMD" in

  install)
    info "Installation de PM2..."
    npm install -g pm2
    success "PM2 installé : $(pm2 --version)"

    info "Configuration du démarrage automatique au boot..."
    echo ""
    echo -e "${YELLOW}IMPORTANT : Copiez-collez la commande 'sudo env...' affichée ci-dessous${NC}"
    echo ""
    pm2 startup
    echo ""
    info "Démarrage initial des services..."
    pm2 start "$SCRIPT_DIR/ecosystem.config.js"
    pm2 save
    echo ""
    success "PM2 configuré ! JARVIS redémarrera automatiquement après un reboot."
    echo ""
    echo -e "${BOLD}Commandes utiles :${NC}"
    echo -e "  pm2 status             — état de tous les services"
    echo -e "  pm2 logs               — logs en temps réel"
    echo -e "  pm2 logs jarvis-backend — logs du backend seulement"
    echo -e "  pm2 restart all        — redémarrer tout"
    echo -e "  pm2 monit              — tableau de bord interactif"
    ;;

  start)
    info "Démarrage des services JARVIS via PM2..."
    pm2 start "$SCRIPT_DIR/ecosystem.config.js"
    pm2 save
    echo ""
    pm2 status
    echo ""
    success "Services démarrés."
    echo -e "  Interface Web    → ${BOLD}http://localhost:8501${NC}"
    echo -e "  Interface Mobile → ${BOLD}http://localhost:3001${NC}"
    echo -e "  TTS Voxtral      → ${BOLD}http://localhost:8001${NC} (si MISTRAL_API_KEY configurée)"
    ;;

  stop)
    info "Arrêt des services JARVIS..."
    pm2 stop ecosystem.config.js 2>/dev/null || pm2 stop all
    success "Services arrêtés."
    ;;

  restart)
    info "Redémarrage des services JARVIS..."
    pm2 restart ecosystem.config.js 2>/dev/null || pm2 restart all
    pm2 status
    success "Services redémarrés."
    ;;

  reload)
    info "Rechargement sans interruption (zero-downtime)..."
    pm2 reload ecosystem.config.js 2>/dev/null || pm2 reload all
    pm2 status
    ;;

  status)
    pm2 status
    echo ""
    echo -e "Logs : ${BOLD}pm2 logs${NC}  |  Monitoring : ${BOLD}pm2 monit${NC}"
    ;;

  logs)
    pm2 logs --lines 50
    ;;

  delete)
    warn "Suppression des processus PM2 JARVIS..."
    pm2 delete ecosystem.config.js 2>/dev/null || true
    pm2 save
    success "Processus supprimés de PM2."
    ;;

  *)
    echo "Usage: bash pm2-manager.sh {install|start|stop|restart|reload|status|logs|delete}"
    echo ""
    echo "  install  — Installe PM2 et configure le démarrage au boot"
    echo "  start    — Démarre tous les services"
    echo "  stop     — Arrête tous les services"
    echo "  restart  — Redémarre tous les services"
    echo "  reload   — Recharge sans interruption (zero-downtime)"
    echo "  status   — Affiche l'état des services"
    echo "  logs     — Affiche les logs en temps réel"
    echo "  delete   — Supprime les processus de PM2"
    exit 1
    ;;
esac
