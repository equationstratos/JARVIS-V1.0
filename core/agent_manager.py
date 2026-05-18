"""
Agent Manager — CRUD complet des agents JARVIS

Gère :
- Création / lecture / modification / suppression des fichiers JSON d'agents
- Backups automatiques avant chaque modification
- Validation des noms et des champs
- Templates prédéfinis pour créer rapidement un agent
- Reload à chaud (intégration avec l'orchestrator)
- Skills disponibles (introspection)

Stockage :
- agents/configs/{Name}.json    → fichiers d'agents
- agents/configs/.backups/      → backups (max 30 jours)
"""
import os
import json
import time
import re
import shutil
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta


# ── Constantes ──
PROTECTED_AGENTS = {"Manager"}  # Agents ne pouvant pas être supprimés
MAX_NAME_LEN = 40
MAX_PROMPT_LEN = 20_000
MAX_DESCRIPTION_LEN = 200
NAME_REGEX = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,39}$")
BACKUP_RETENTION_DAYS = 30


# ── Templates de démarrage ──
AGENT_TEMPLATES = {
    "shell": {
        "name": "MyShellAgent",
        "description": "Exécute des commandes shell sur le système.",
        "model": "gemini/gemini-2.0-flash",
        "system_prompt": (
            "Tu es ShellAgent. 1. Action : utilise 'execute_shell' pour chaque "
            "commande demandée. 2. Feedback : explique TOUJOURS en français ce "
            "que tu as fait et ce que tu vois dans la sortie. 3. Sécurité : ne "
            "lance jamais de commande destructive sans confirmation explicite. "
            "RÉPONDS TOUJOURS EN FRANÇAIS."
        ),
        "skills": ["shell_executor"],
        "history_limit": 10,
        "inherit_model": False,
    },
    "code": {
        "name": "MyCodeAgent",
        "description": "Génère et améliore du code source.",
        "model": "anthropic/claude-sonnet-4-5",
        "system_prompt": (
            "Tu es un expert en développement logiciel. Ton objectif est de "
            "produire un code propre, optimisé et documenté. 1. Utilise "
            "'write_file' pour créer ou modifier des fichiers de code. "
            "2. N'exécute jamais le code, délègue à un autre agent si besoin. "
            "3. Suis les meilleures pratiques (lint, typage, tests). "
            "RÉPONDS TOUJOURS EN FRANÇAIS."
        ),
        "skills": ["file_writer"],
        "history_limit": 10,
        "inherit_model": False,
    },
    "search": {
        "name": "MySearchAgent",
        "description": "Recherche d'information sur le web.",
        "model": "gemini/gemini-2.5-flash",
        "system_prompt": (
            "Tu es un expert en recherche d'information. 1. Utilise 'web_search' "
            "pour trouver des informations à jour. 2. Synthétise les résultats "
            "en français de façon claire et structurée. 3. Privilégie les sources "
            "officielles et récentes. RÉPONDS TOUJOURS EN FRANÇAIS."
        ),
        "skills": ["web_search"],
        "history_limit": 5,
        "inherit_model": False,
    },
    "blank": {
        "name": "MyAgent",
        "description": "Agent personnalisé.",
        "model": "gemini/gemini-2.0-flash",
        "system_prompt": (
            "Tu es un agent assistant. RÉPONDS TOUJOURS EN FRANÇAIS."
        ),
        "skills": [],
        "history_limit": 10,
        "inherit_model": True,  # Par défaut, hérite du modèle global
    },
}


# ── Skills disponibles (introspection ou liste statique) ──
def discover_skills(project_root: str) -> List[Dict]:
    """
    Tente de découvrir les skills depuis le code du projet.
    Fallback sur une liste statique si introspection impossible.
    """
    skills_static = [
        {"id": "shell_executor", "name": "Exécution shell", "icon": "🐚",
         "description": "Lance des commandes shell sur le système"},
        {"id": "file_writer", "name": "Écriture fichiers", "icon": "📝",
         "description": "Crée et modifie des fichiers"},
        {"id": "file_reader", "name": "Lecture fichiers", "icon": "📖",
         "description": "Lit le contenu de fichiers"},
        {"id": "web_search", "name": "Recherche web", "icon": "🔍",
         "description": "Cherche des informations sur internet"},
        {"id": "web_fetch", "name": "Téléchargement web", "icon": "🌐",
         "description": "Télécharge le contenu d'une URL"},
        {"id": "git_commands", "name": "Commandes Git", "icon": "📦",
         "description": "Exécute des commandes git (status, commit, diff…)"},
        {"id": "code_executor", "name": "Exécution code", "icon": "▶️",
         "description": "Exécute du code Python sandboxed"},
    ]
    # Tentative de découverte dynamique
    skills_dir = os.path.join(project_root, "agents", "skills")
    if os.path.isdir(skills_dir):
        try:
            discovered = set()
            for f in os.listdir(skills_dir):
                if f.endswith(".py") and not f.startswith("_"):
                    discovered.add(f[:-3])
            # Compléter la liste statique avec ce qui existe sur disque
            existing_ids = {s["id"] for s in skills_static}
            for d in discovered:
                if d not in existing_ids:
                    skills_static.append({
                        "id": d, "name": d.replace("_", " ").title(),
                        "icon": "🔧", "description": "Skill détecté dans agents/skills/"
                    })
        except Exception:
            pass
    return skills_static


# ── Validation ──
class AgentValidationError(Exception):
    """Erreur de validation des données d'un agent."""
    pass


def validate_agent_data(data: dict, is_update: bool = False) -> dict:
    """
    Valide et normalise les données d'un agent.
    Lève AgentValidationError si invalide.
    Retourne un dict normalisé prêt à être sauvegardé.
    """
    if not isinstance(data, dict):
        raise AgentValidationError("Les données doivent être un objet JSON")

    name = (data.get("name") or "").strip()
    if not name:
        raise AgentValidationError("Le nom est requis")
    if not NAME_REGEX.match(name):
        raise AgentValidationError(
            "Nom invalide : doit commencer par une lettre, contenir uniquement "
            f"lettres/chiffres/underscore, longueur 3 à {MAX_NAME_LEN}"
        )

    description = (data.get("description") or "").strip()
    if len(description) > MAX_DESCRIPTION_LEN:
        raise AgentValidationError(
            f"Description trop longue (max {MAX_DESCRIPTION_LEN} chars)"
        )

    model = (data.get("model") or "").strip()
    if not model:
        raise AgentValidationError("Le modèle est requis")
    # Validation soft : on accepte tout ce qui ressemble à provider/model
    if "/" not in model:
        raise AgentValidationError(
            "Format modèle invalide (attendu: provider/model, ex: gemini/gemini-2.0-flash)"
        )

    system_prompt = data.get("system_prompt") or ""
    if not isinstance(system_prompt, str):
        raise AgentValidationError("system_prompt doit être une chaîne")
    if len(system_prompt) > MAX_PROMPT_LEN:
        raise AgentValidationError(
            f"Prompt système trop long (max {MAX_PROMPT_LEN} chars, "
            f"actuellement {len(system_prompt)})"
        )

    skills = data.get("skills") or []
    if not isinstance(skills, list):
        raise AgentValidationError("skills doit être une liste")
    skills = [str(s) for s in skills if isinstance(s, str)]

    try:
        history_limit = int(data.get("history_limit", 10))
    except (TypeError, ValueError):
        raise AgentValidationError("history_limit doit être un entier")
    if history_limit < 1 or history_limit > 100:
        raise AgentValidationError("history_limit doit être entre 1 et 100")

    inherit_model = bool(data.get("inherit_model", False))

    return {
        "name": name,
        "description": description,
        "model": model,
        "system_prompt": system_prompt,
        "skills": skills,
        "history_limit": history_limit,
        "inherit_model": inherit_model,
    }


# ── Stockage atomique + backups ──
class AgentManager:
    def __init__(self, agents_dir: str):
        self.agents_dir = agents_dir
        self.backups_dir = os.path.join(agents_dir, ".backups")
        os.makedirs(self.agents_dir, exist_ok=True)
        os.makedirs(self.backups_dir, exist_ok=True)

    def _path_for(self, name: str) -> str:
        return os.path.join(self.agents_dir, f"{name}.json")

    def exists(self, name: str) -> bool:
        return os.path.isfile(self._path_for(name))

    def list_names(self) -> List[str]:
        try:
            return sorted([
                f[:-5] for f in os.listdir(self.agents_dir)
                if f.endswith(".json") and not f.startswith(".")
            ])
        except FileNotFoundError:
            return []

    def read(self, name: str) -> dict:
        path = self._path_for(name)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Agent '{name}' introuvable")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Compatibilité descendante : ajouter inherit_model si manquant
        if "inherit_model" not in data:
            data["inherit_model"] = False
        return data

    def list_full(self) -> List[dict]:
        result = []
        for name in self.list_names():
            try:
                result.append(self.read(name))
            except Exception as e:
                result.append({"name": name, "error": str(e)})
        return result

    def _backup(self, name: str) -> Optional[str]:
        """Sauvegarde le fichier actuel dans .backups/ avant modification."""
        src = self._path_for(name)
        if not os.path.isfile(src):
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{name}.{ts}.json"
        dst = os.path.join(self.backups_dir, backup_name)
        try:
            shutil.copy2(src, dst)
            return dst
        except Exception as e:
            print(f"⚠ Backup échoué pour {name}: {e}")
            return None

    def cleanup_old_backups(self):
        """Supprime les backups de plus de BACKUP_RETENTION_DAYS jours."""
        cutoff = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)
        try:
            for fname in os.listdir(self.backups_dir):
                fpath = os.path.join(self.backups_dir, fname)
                if os.path.isfile(fpath):
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime < cutoff:
                        os.remove(fpath)
        except Exception:
            pass

    def _atomic_write(self, name: str, data: dict):
        """Écriture atomique : .tmp → rename."""
        path = self._path_for(name)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.write("\n")
        os.replace(tmp_path, path)  # atomique sur POSIX

    def create(self, data: dict) -> dict:
        """Crée un nouvel agent. Lève si le nom existe déjà."""
        normalized = validate_agent_data(data)
        if self.exists(normalized["name"]):
            raise AgentValidationError(
                f"Un agent nommé '{normalized['name']}' existe déjà"
            )
        self._atomic_write(normalized["name"], normalized)
        return normalized

    def update(self, name: str, data: dict) -> dict:
        """
        Modifie un agent existant.
        Si data['name'] diffère de name, c'est un renommage (création + suppression).
        """
        if not self.exists(name):
            raise FileNotFoundError(f"Agent '{name}' introuvable")

        normalized = validate_agent_data(data, is_update=True)
        new_name = normalized["name"]

        # Backup avant modification
        self._backup(name)

        # Cas du renommage
        if new_name != name:
            if self.exists(new_name):
                raise AgentValidationError(
                    f"Impossible de renommer : '{new_name}' existe déjà"
                )
            if name in PROTECTED_AGENTS:
                raise AgentValidationError(
                    f"L'agent '{name}' est protégé et ne peut pas être renommé"
                )
            # Écrire le nouveau, supprimer l'ancien
            self._atomic_write(new_name, normalized)
            try:
                os.remove(self._path_for(name))
            except OSError:
                pass
        else:
            self._atomic_write(name, normalized)

        return normalized

    def delete(self, name: str) -> bool:
        """Supprime un agent. Refuse pour les agents protégés."""
        if name in PROTECTED_AGENTS:
            raise AgentValidationError(
                f"L'agent '{name}' est protégé et ne peut pas être supprimé"
            )
        if not self.exists(name):
            raise FileNotFoundError(f"Agent '{name}' introuvable")

        # Backup avant suppression (au cas où)
        self._backup(name)
        os.remove(self._path_for(name))
        return True

    def get_template(self, template_id: str) -> dict:
        """Retourne un template clonable. template_id ∈ {shell, code, search, blank}."""
        if template_id not in AGENT_TEMPLATES:
            raise AgentValidationError(f"Template '{template_id}' inconnu")
        # Deep copy pour éviter les modifs accidentelles
        return json.loads(json.dumps(AGENT_TEMPLATES[template_id]))

    def list_backups(self, name: Optional[str] = None) -> List[Dict]:
        """Liste les backups disponibles, optionnellement filtrés par nom."""
        result = []
        try:
            for fname in sorted(os.listdir(self.backups_dir), reverse=True):
                if not fname.endswith(".json"):
                    continue
                # Format : {AgentName}.{YYYYMMDD_HHMMSS}.json
                parts = fname.rsplit(".", 2)
                if len(parts) != 3:
                    continue
                agent_name, timestamp, _ = parts
                if name and agent_name != name:
                    continue
                fpath = os.path.join(self.backups_dir, fname)
                result.append({
                    "filename": fname,
                    "agent_name": agent_name,
                    "timestamp": timestamp,
                    "size": os.path.getsize(fpath),
                })
        except Exception:
            pass
        return result
