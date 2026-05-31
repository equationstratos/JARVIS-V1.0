"""
Orchestrator JARVIS — version optimisée

Optimisations clés :
- Routage par mots-clés (0ms vs ~500ms d'appel LLM)
- Cache LRU sur les décisions de routage ambigües
- Fallback LLM uniquement quand vraiment nécessaire
- Streaming natif via async generators
"""
import json
import os
import re
import asyncio
from functools import lru_cache
from typing import List, Dict, Any, AsyncGenerator, Optional
import litellm
from dotenv import load_dotenv
from core.blackboard import Blackboard
from core.agent import Agent
from utils.cache_manager import CacheManager
if os.getenv("ENABLE_VECTOR_ROUTING", "false").lower() == "true":
    from utils.semantic_router import SemanticRouter
else:
    SemanticRouter = None  # type: ignore

load_dotenv()

# Désactiver les retries par défaut de litellm (on les gère)
litellm.drop_params = True
litellm.set_verbose = False


# ── Mots-clés de routage (couvre ~90% des cas sans LLM) ──
ROUTING_PATTERNS = {
    "ShellAgent": re.compile(
        r"\b(shell|terminal|bash|commande|cmd|ls|cd|pwd|grep|find|df|du|ps|kill|"
        r"install(?:e|er)?|apt|sudo|systemctl|service|disk|espace|disque|"
        r"process(?:us)?|cpu|m[ée]moire|ram|chmod|chown|tar|zip|curl|wget|ping|"
        r"netstat|ss|top|htop|uname|free|mount|fdisk|crontab)\b",
        re.IGNORECASE,
    ),
    "GitAgent": re.compile(
        r"\b(git|commit(?:s|er)?|branch(?:es)?|branche|merge|pull|push|diff|"
        r"checkout|rebase|stash|reset|cherry[\s-]pick|blame|log\s+git|"
        r"r[ée]po(?:sitory)?|statut\s+git|gitignore)\b",
        re.IGNORECASE,
    ),
    "CodeMaster": re.compile(
        r"\b(code|script|fonction|function|classe?|class|refacto(?:r|re|ring)?|"
        r"[ée]cri(?:s|re|t)|cr[ée]e?(?:r|s)?|programme(?:r)?|python|javascript|"
        r"typescript|java|rust|c\+\+|golang|html|css|impl[ée]ment(?:e|er|ation)?|"
        r"d[ée]bug(?:ger)?|fix(?:er)?\s+(?:le\s+)?(?:bug|code))\b",
        re.IGNORECASE,
    ),
    "WebResearcher": re.compile(
        r"\b(recherche(?:r)?|cherche(?:r)?|search|google|web|internet|actualit[ée]s?|"
        r"news|trouve(?:r)?\s+(?:en\s+ligne|sur\s+le\s+web|sur\s+internet)|"
        r"derni[èe]re?s?\s+(?:info|nouvelle|version)|info\s+sur)\b",
        re.IGNORECASE,
    ),
    "PlannerAgent": re.compile(
        r"\b(plan(?:ifie|ifier|ning)?|[ée]tapes?|roadmap|strat[ée]gie|"
        r"organise(?:r)?|structure(?:r)?|d[ée]coupe(?:r)?|comment\s+(?:faire|proc[ée]der)|"
        r"par\s+o[ùu]\s+commencer|architecture|conception)\b",
        re.IGNORECASE,
    ),
}

# Modèle par défaut sécurisé (Claude Opus 4.7 pour meilleure qualité)
DEFAULT_MODEL = os.getenv("JARVIS_DEFAULT_MODEL", "claude-opus-4-7")
ROUTING_MODEL = os.getenv("JARVIS_ROUTING_MODEL", "claude-opus-4-7")
FALLBACK_MODEL = os.getenv("JARVIS_FALLBACK_MODEL", "gemini/gemini-2.0-flash")


class Orchestrator:
    def __init__(self, agents_dir: str, cache_manager: Optional[CacheManager] = None):
        self.agents: Dict[str, Agent] = {}
        self.blackboard = Blackboard()
        self.agents_dir = agents_dir
        self.cache_manager = cache_manager or CacheManager()
        self.semantic_router = SemanticRouter() if SemanticRouter is not None else None
        self.override_model: Optional[str] = None
        self._route_cache: Dict[str, str] = {}  # Cache des décisions de routage
        self.load_agents(agents_dir)

    def set_override_model(self, model_name: str):
        self.override_model = model_name

    def load_agents(self, agents_dir: str):
        if not os.path.exists(agents_dir):
            return
        for filename in os.listdir(agents_dir):
            if filename.endswith(".json"):
                try:
                    agent = Agent(os.path.join(agents_dir, filename), self.cache_manager)
                    self.agents[agent.name] = agent
                except Exception as e:
                    print(f"Error loading agent {filename}: {e}")

    async def initialize_semantic_router(self):
        """Initialise le routeur sémantique avec tous les agents"""
        if self.semantic_router is not None:
            await self.semantic_router.initialize_agents(self.agents)

    def _fast_route(self, user_query: str) -> Optional[str]:
        """Routage instantané par mots-clés + keywords des agents. Retourne None si ambigu."""
        # Cache hit ?
        cache_key = user_query.lower()[:200]
        if cache_key in self._route_cache:
            return self._route_cache[cache_key]

        # Préfixe explicite "!commande" → ShellAgent
        if user_query.strip().startswith("!"):
            return "ShellAgent" if "ShellAgent" in self.agents else None

        query_lower = user_query.lower()

        # Scoring par keywords configurés dans chaque agent
        scores = {}
        for agent_name, agent in self.agents.items():
            keywords = agent.routing_keywords
            if keywords:
                # Compter les mots-clés correspondants
                matches = sum(1 for kw in keywords if kw.lower() in query_lower)
                if matches > 0:
                    scores[agent_name] = matches

        # Si pas de keywords configurés, fallback aux patterns regex
        if not scores:
            for agent_name, pattern in ROUTING_PATTERNS.items():
                if agent_name not in self.agents:
                    continue
                matches = pattern.findall(user_query)
                if matches:
                    scores[agent_name] = len(matches)

        if not scores:
            # Pas de match → Manager (conversation générale)
            chosen = "Manager" if "Manager" in self.agents else None
        elif len(scores) == 1:
            # Match unique
            chosen = max(scores, key=scores.get)
        elif max(scores.values()) > 1:
            # Un agent qui domine clairement
            chosen = max(scores, key=scores.get)
        else:
            # Ambiguité (plusieurs agents avec 1 point chacun) → LLM
            return None

        if chosen:
            self._route_cache[cache_key] = chosen
        return chosen

    async def _llm_route(self, user_query: str) -> str:
        """Fallback LLM pour cas ambigus uniquement. Utilise best model disponible."""
        model = self.override_model or ROUTING_MODEL
        is_local = model.startswith("ollama/") or model.startswith("ollama_chat/")

        # Pour Ollama : éviter le LLM routing (trop lent pour 20 tokens) → Manager direct
        if is_local:
            return "Manager" if "Manager" in self.agents else next(iter(self.agents))

        agent_descriptions = "\n".join(
            [
                f"- {name}: {a.config.get('description', '')}"
                for name, a in self.agents.items()
            ]
        )
        routing_prompt = (
            f"You are a routing expert. Choose the BEST agent for this user query.\n\n"
            f"Available agents:\n{agent_descriptions}\n\n"
            f"User query: \"{user_query}\"\n\n"
            f"Respond with ONLY the agent name, nothing else."
        )
        try:
            resp = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": routing_prompt}],
                max_tokens=20,
                temperature=0.0,
                timeout=5,
            )
            choice = resp.choices[0].message.content.strip().split()[0].strip(".,!?'\"")
            return choice if choice in self.agents else "Manager"
        except Exception as e:
            print(f"Routing LLM error: {e}, using Manager")
            return "Manager"

    async def _resolve_agent(self, user_query: str) -> Agent:
        """Résout l'agent à utiliser: cache → keywords → semantic → LLM → Manager."""
        # 1. Vérifier le cache de routage
        if self.cache_manager:
            cached_agent = await self.cache_manager.get_cached_routing(user_query)
            if cached_agent and cached_agent in self.agents:
                return self.agents[cached_agent]

        # 2. Routage par keywords (0ms)
        target = self._fast_route(user_query)
        if target is None:
            # 3. Routage sémantique (si disponible, ~50ms)
            if self.semantic_router is not None and self.semantic_router.is_available():
                semantic_target = await self.semantic_router.route_single(
                    user_query, confidence_threshold=0.6
                )
                if semantic_target:
                    target = semantic_target
            # 4. Fallback LLM (si toujours ambigu, ~500ms)
            if target is None:
                target = await self._llm_route(user_query)

        if target not in self.agents:
            target = "Manager" if "Manager" in self.agents else next(iter(self.agents))

        # Cacher la décision
        if self.cache_manager:
            await self.cache_manager.cache_routing_decision(user_query, target, ttl=7200)

        return self.agents[target]

    async def route(
        self, user_query: str, history: List[Dict[str, str]]
    ) -> str:
        """API non-streaming (compatibilité)."""
        agent = await self._resolve_agent(user_query)
        return await agent.execute(
            user_query, history, self.blackboard,
            model_override=self.override_model,
        )

    async def route_stream(
        self, user_query: str, history: List[Dict[str, str]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """API streaming. Yield des dicts {type, data}."""
        agent = await self._resolve_agent(user_query)
        yield {"type": "agent", "data": agent.name}
        async for chunk in agent.execute_stream(
            user_query, history, self.blackboard,
            model_override=self.override_model,
        ):
            yield chunk
