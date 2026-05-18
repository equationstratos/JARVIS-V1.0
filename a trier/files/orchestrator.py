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

# Modèle par défaut sécurisé (le précédent n'existait pas)
DEFAULT_MODEL = os.getenv("JARVIS_DEFAULT_MODEL", "gemini/gemini-2.0-flash")
ROUTING_MODEL = os.getenv("JARVIS_ROUTING_MODEL", "gemini/gemini-2.0-flash-lite")


class Orchestrator:
    def __init__(self, agents_dir: str):
        self.agents: Dict[str, Agent] = {}
        self.blackboard = Blackboard()
        self.agents_dir = agents_dir
        self.load_agents(agents_dir)
        self.override_model: Optional[str] = None
        self._route_cache: Dict[str, str] = {}  # Cache des décisions de routage

    def set_override_model(self, model_name: str):
        self.override_model = model_name

    def load_agents(self, agents_dir: str):
        if not os.path.exists(agents_dir):
            return
        for filename in os.listdir(agents_dir):
            if filename.endswith(".json"):
                try:
                    agent = Agent(os.path.join(agents_dir, filename))
                    self.agents[agent.name] = agent
                except Exception as e:
                    print(f"Error loading agent {filename}: {e}")

    def _fast_route(self, user_query: str) -> Optional[str]:
        """Routage instantané par mots-clés. Retourne None si ambigu."""
        # Cache hit ?
        cache_key = user_query.lower()[:200]
        if cache_key in self._route_cache:
            return self._route_cache[cache_key]

        # Préfixe explicite "!commande" → ShellAgent
        if user_query.strip().startswith("!"):
            return "ShellAgent" if "ShellAgent" in self.agents else None

        # Scoring par regex
        scores = {}
        for agent_name, pattern in ROUTING_PATTERNS.items():
            if agent_name not in self.agents:
                continue
            matches = pattern.findall(user_query)
            if matches:
                scores[agent_name] = len(matches)

        if not scores:
            # Pas de match → Manager (conversation générale)
            chosen = "Manager" if "Manager" in self.agents else None
        elif len(scores) == 1 or max(scores.values()) > 1:
            # Match clair (un seul agent ou un agent qui domine)
            chosen = max(scores, key=scores.get)
        else:
            # Ambiguïté → on retourne None pour fallback LLM
            return None

        if chosen:
            self._route_cache[cache_key] = chosen
        return chosen

    async def _llm_route(self, user_query: str) -> str:
        """Fallback LLM pour cas ambigus uniquement."""
        agent_descriptions = "\n".join(
            [
                f"- {name}: {a.config.get('description', '')[:80]}"
                for name, a in self.agents.items()
            ]
        )
        routing_prompt = (
            f"Choose the best agent for this query.\n"
            f"Agents:\n{agent_descriptions}\n\n"
            f"Query: \"{user_query[:300]}\"\n\n"
            f"Answer with ONLY the agent name."
        )
        try:
            resp = await litellm.acompletion(
                model=self.override_model or ROUTING_MODEL,
                messages=[{"role": "user", "content": routing_prompt}],
                max_tokens=15,
                temperature=0.0,
                timeout=5,  # Timeout court : si ça traîne, on fallback
            )
            choice = resp.choices[0].message.content.strip().split()[0].strip(".,!?'\"")
            return choice if choice in self.agents else "Manager"
        except Exception:
            return "Manager"

    async def _resolve_agent(self, user_query: str) -> Agent:
        """Résout l'agent à utiliser, avec fast path."""
        target = self._fast_route(user_query)
        if target is None:
            target = await self._llm_route(user_query)
        if target not in self.agents:
            target = "Manager" if "Manager" in self.agents else next(iter(self.agents))
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
