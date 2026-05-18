# JARVIS-V1.0 — Modular Agentic AI Ecosystem

> Orchestrateur d'agents IA modulaires avec interfaces Web, Mobile et Terminal.  
> Fonctionne **100% en local** grâce à Ollama (mistral-small3.2, llama3) — aucune clé API requise.

---

## Présentation

JARVIS est un système multi-agents IA qui route automatiquement vos requêtes vers l'agent le plus adapté :

- **9 agents spécialisés** : Code, Shell, Git, Recherche Web, Planification, Mémoire...
- **3 interfaces** : Web (navigateur), Mobile (React Native / web mobile), Terminal (TUI)
- **Multi-modèles** : Ollama (local), Claude (Anthropic), Gemini (Google), et 50+ via LiteLLM
- **Streaming temps réel** (SSE) — les réponses s'affichent token par token
- **Mémoire vectorielle** (ChromaDB) pour le contexte long terme
- **TTS vocal** (Kokoro, optionnel) — JARVIS vous parle

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Interfaces utilisateur               │
│   Navigateur :8501  │  Mobile :3001  │  Terminal (TUI) │
└────────────────────┬────────────────────────────────────┘
                     │
          ┌──────────▼──────────────┐
          │   Backend FastAPI :8501  │
          │   Orchestrateur + Agents │
          │   LiteLLM (multi-modèles)│
          └──────────┬──────────────┘
                     │
     ┌───────────────┼──────────────────┐
     │               │                  │
┌────▼─────┐  ┌──────▼──────┐  ┌───────▼──────────────┐
│  Ollama  │  │  ChromaDB   │  │  TTS (optionnel)      │
│ :11434   │  │  (mémoire)  │  │  Kokoro   :8000       │
│ mistral  │  │             │  │  Voxtral  :8001       │
│ llama3   │  └─────────────┘  └───────────────────────┘
└──────────┘
```

| Service          | Port  | Rôle                                       |
|------------------|-------|--------------------------------------------|
| Backend          | 8501  | API principale, orchestration agents        |
| Mobile proxy     | 3001  | Interface mobile + proxy TTS               |
| TTS Kokoro       | 8000  | Synthèse vocale locale (optionnel)         |
| TTS Voxtral      | 8001  | Synthèse vocale Mistral AI (optionnel)     |
| Ollama           | 11434 | Modèles IA locaux                          |

---

## Agents disponibles

| Agent         | Rôle                                        | Modèle par défaut      |
|---------------|---------------------------------------------|------------------------|
| Manager       | Coordinateur, conversation générale         | ollama/mistral-small3.2|
| ShellAgent    | Commandes terminal, administration système  | ollama/mistral-small3.2|
| GitAgent      | Opérations git (commit, branch, merge...)   | ollama/mistral-small3.2|
| CodeMaster    | Écriture et refactoring de code             | ollama/mistral-small3.2|
| WebResearcher | Recherche web, synthèse d'informations      | ollama/mistral-small3.2|
| PlannerAgent  | Planification de projets, architecture      | ollama/mistral-small3.2|
| MemoryAgent   | Apprentissage, contexte historique          | ollama/mistral-small3.2|
| MemoryAgentRAG| Mémoire RAG (ChromaDB)                     | ollama/mistral-small3.2|
| Parleur       | Réponses optimisées pour la voix (TTS)      | ollama/mistral-small3.2|

---

## Prérequis

- **Python 3.10+**
- **Node.js 18+** (pour l'app mobile)
- **Git**
- **~8 GB** d'espace disque (modèles Ollama)
- **Linux**, **macOS** ou **WSL2**

---

## Installation rapide (une seule commande)

```bash
curl -sSL https://raw.githubusercontent.com/equationstratos/jarvis-v1.0/main/install-JARVIS-V1.0.sh | bash
```

Ce script effectue automatiquement :
1. Vérification et installation des dépendances système
2. Clonage du repo (ou utilisation du dossier courant)
3. Création de l'environnement Python virtuel
4. Installation des dépendances Python
5. Installation d'Ollama
6. Téléchargement des modèles `mistral-small3.2` et `llama3`
7. Création du fichier `.env` avec les defaults Ollama
8. Installation des dépendances de l'app mobile
9. Validation de l'installation

---

## Installation manuelle

```bash
# 1. Cloner le repo
git clone https://github.com/equationstratos/jarvis-v1.0.git
cd jarvis-v1.0

# 2. Environnement Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install chromadb

# 3. Installer Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
ollama pull mistral-small3.2
ollama pull llama3

# 4. Configuration
cp .env.example .env
# Éditez .env si nécessaire (les defaults Ollama fonctionnent sans modification)

# 5. App mobile (optionnel)
cd mobile && npm install && cd ..

# 6. Validation
python TESTS/test_load.py
python TESTS/test_configuration.py
```

---

## Configuration

### Mode Ollama (par défaut — 100% local, gratuit)

Aucune configuration requise. Les defaults dans `.env.example` utilisent Ollama :

```env
JARVIS_DEFAULT_MODEL=ollama/mistral-small3.2
JARVIS_ROUTING_MODEL=ollama/mistral-small3.2
JARVIS_FALLBACK_MODEL=ollama/llama3
```

### Clés API cloud (optionnel — pour de meilleures performances)

Ajoutez dans `.env` :

```env
ANTHROPIC_API_KEY=sk-ant-...        # Claude Opus / Sonnet
GOOGLE_API_KEY=AIza...              # Gemini 2.0 Flash
```

### Référence complète `.env`

| Variable                  | Défaut                      | Description                          |
|---------------------------|-----------------------------|--------------------------------------|
| `JARVIS_DEFAULT_MODEL`    | `ollama/mistral-small3.2`   | Modèle principal                     |
| `JARVIS_ROUTING_MODEL`    | `ollama/mistral-small3.2`   | Modèle pour le routage des agents    |
| `JARVIS_FALLBACK_MODEL`   | `ollama/llama3`             | Modèle de secours                    |
| `ANTHROPIC_API_KEY`       | *(vide)*                    | Clé API Anthropic (optionnel)        |
| `GOOGLE_API_KEY`          | *(vide)*                    | Clé API Google (optionnel)           |
| `SERVER_HOST`             | `0.0.0.0`                   | Hôte du serveur backend              |
| `SERVER_PORT`             | `8501`                      | Port du serveur backend              |
| `ENABLE_CACHING`          | `true`                      | Cache des réponses                   |
| `ENABLE_MEMORY_AGENT`     | `true`                      | Agent mémoire actif                  |
| `ENABLE_VECTOR_ROUTING`   | `false`                     | Routage sémantique (embeddings)      |
| `REDIS_HOST`              | `localhost`                 | Redis (optionnel, fallback mémoire)  |

---

## Démarrage

### Avec PM2 — recommandé (auto-restart, démarrage au boot)

PM2 surveille les processus et les redémarre automatiquement en cas de crash.

```bash
# Démarrer tous les services
bash pm2-manager.sh start

# Voir l'état
pm2 status

# Logs en temps réel
pm2 logs

# Tableau de bord interactif
pm2 monit
```

#### Activer le démarrage automatique au boot

```bash
pm2 startup          # Affiche une commande sudo à copier-coller
# → Coller la commande 'sudo env...' affichée
pm2 save             # Sauvegarde la liste des processus
```

Après reboot, tous les services redémarrent automatiquement.

#### Commandes PM2 courantes

| Commande | Action |
|----------|--------|
| `pm2 start ecosystem.config.js` | Démarrer via le fichier de config |
| `pm2 stop all` | Arrêter tous les services |
| `pm2 restart all` | Redémarrer tous les services |
| `pm2 restart jarvis-backend` | Redémarrer un service spécifique |
| `pm2 logs jarvis-backend` | Logs d'un service |
| `pm2 delete all` | Supprimer les processus de PM2 |

### Démarrage direct (session terminal)

```bash
source venv/bin/activate
bash launch-JARVIS.sh     # Tous les serveurs, Ctrl+C pour arrêter
```

### Démarrage manuel (service par service)

```bash
source venv/bin/activate

python main.py --web          # Backend :8501
python webmobile.py           # Mobile proxy :3001
python tts/voxtral_server.py  # TTS Voxtral :8001 (si MISTRAL_API_KEY)
python main.py --tui          # Interface terminal
```

---

## Interfaces

### Interface Web — `http://localhost:8501`

- Chat avec streaming temps réel
- Sélection d'agent et de modèle
- **Agent Studio** : créer, modifier, tester les agents via l'interface
- Statistiques système et benchmarks

### Interface Mobile Web — `http://localhost:3001`

- Interface optimisée pour mobile
- 4 thèmes disponibles (iOS, Material, Glassmorphism, Ultra)
- TTS intégré (si Kokoro actif)
- Sélection du modèle parmi 50+

### App Mobile Native (React Native / Expo)

```bash
cd mobile
npx expo start
```

Scannez le QR code avec l'app **Expo Go** sur votre téléphone.  
L'app se connecte au backend sur `:8501` (configurable dans Settings).

### Interface Terminal (TUI)

```bash
python main.py --tui
```

Navigation clavier, sélection d'agent, chat en mode texte.

---

## TTS — Synthèse vocale (optionnel)

JARVIS supporte deux moteurs TTS, sélectionnables dans l'interface web (Settings → TTS Engine) :

### Kokoro (port 8000) — voix française locale, gratuit

Installation dans le dossier parent :

```bash
cd ..
git clone https://github.com/remsky/Kokoro-FastAPI.git jarvis-voice
cd jarvis-voice
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`launch-JARVIS.sh` détecte automatiquement `../jarvis-voice/tts_server4.py` et le démarre.  
Voix disponible : `ff_siwis` (française féminine).

### Voxtral (port 8001) — IA Mistral, qualité supérieure

Voxtral est le moteur TTS de Mistral AI. Il nécessite une clé API Mistral.

**Configuration :**
```bash
# Dans .env
MISTRAL_API_KEY=votre-cle-mistral
```

`launch-JARVIS.sh` démarre automatiquement `tts/voxtral_server.py` si `MISTRAL_API_KEY` est configurée.

Voix disponibles : `fr_female`, `fr_male`

**Obtenir une clé Mistral :** https://console.mistral.ai/

### Changer de moteur TTS

Dans l'interface web (`http://localhost:8501`) :  
**Settings → TTS Engine → Kokoro / Voxtral**

L'interface mobile (`http://localhost:3001`) utilise le proxy `/tts` avec le paramètre `engine`.

---

## Tests

```bash
source venv/bin/activate

# Test de chargement .env
python TESTS/test_load.py

# Test de configuration complète (imports, agents, routing)
python TESTS/test_configuration.py

# Test des modèles LLM (Ollama requis)
python TESTS/test_models.py

# Test du streaming (backend doit être lancé)
python TESTS/test_stream.py
```

---

## Dépannage

| Problème                          | Solution                                                  |
|-----------------------------------|-----------------------------------------------------------|
| `ollama: command not found`       | `curl -fsSL https://ollama.ai/install.sh \| sh`           |
| Ollama ne répond pas              | `ollama serve` dans un terminal séparé                    |
| Modèle manquant                   | `ollama pull mistral-small3.2` ou `ollama pull llama3`    |
| Port 8501 déjà utilisé            | `kill $(lsof -ti:8501)` puis relancer                     |
| Port 3001 déjà utilisé            | `kill $(lsof -ti:3001)` puis relancer                     |
| `ModuleNotFoundError: chromadb`   | `pip install chromadb`                                    |
| `No API key` error                | Vérifiez que `JARVIS_DEFAULT_MODEL` commence par `ollama/` |
| Tests d'import échouent           | `source venv/bin/activate` avant de lancer les tests      |
| App mobile ne se connecte pas     | Vérifiez l'URL du serveur dans Settings (IP de la machine, pas localhost) |
| `pm2: command not found`          | `npm install -g pm2`                                      |
| Service PM2 ne redémarre pas      | `pm2 logs <nom>` pour voir l'erreur, puis `pm2 restart <nom>` |
| Voxtral TTS désactivé             | Ajoutez `MISTRAL_API_KEY=...` dans `.env` puis `pm2 restart jarvis-voxtral` |

---

## Structure du projet

```
JARVIS-V1.0/
├── install-JARVIS-V1.0.sh   # Installateur complet
├── launch-JARVIS.sh          # Lancement de tous les serveurs
├── main.py                   # Point d'entrée (--web ou --tui)
├── webmobile.py              # Proxy mobile (:3001)
├── config.py                 # Configuration centralisée
├── requirements.txt          # Dépendances Python
├── .env.example              # Template de configuration
├── agents/configs/           # Configurations JSON des 9 agents
├── core/                     # Moteur d'orchestration
│   ├── orchestrator.py       # Routage et coordination
│   ├── agent.py              # Classe Agent
│   ├── agent_manager.py      # CRUD agents
│   ├── blackboard.py         # État partagé
│   └── validator.py          # Validation des réponses
├── utils/                    # Utilitaires
│   ├── cache_manager.py      # Cache multi-couches
│   ├── semantic_router.py    # Routage par embeddings
│   ├── shell_utils.py        # Exécution shell asynchrone
│   ├── web_utils.py          # Scraping et HTTP
│   ├── validator.py          # Validation LLM
│   └── observability.py      # Métriques OpenTelemetry
├── interfaces/
│   ├── web_v2.py             # Serveur FastAPI (:8501)
│   ├── tui.py                # Interface terminal
│   └── static/               # Assets web (HTML/CSS)
├── mobile/                   # App React Native
│   ├── App.tsx               # Navigation principale
│   ├── src/screens/          # Écrans (Chat, Models, Settings)
│   ├── src/api/              # Client HTTP vers le backend
│   └── src/store/            # État global (Zustand)
└── TESTS/                    # Suite de tests
```

---

## Contribution

1. Forkez le repo
2. Créez une branche : `git checkout -b feature/ma-fonctionnalite`
3. Committez vos changements : `git commit -m "feat: description"`
4. Pushez : `git push origin feature/ma-fonctionnalite`
5. Ouvrez une Pull Request

---

## Licence

MIT — Voir [LICENSE](LICENSE) pour les détails.
