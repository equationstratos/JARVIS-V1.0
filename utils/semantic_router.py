"""
Semantic Router — Routage basé sur la similarité sémantique

Utilise bge-small pour embedder les descriptions d'agents et les queries.
Beaucoup plus robuste que les patterns regex pour les cas ambigus.
"""
from typing import Dict, List, Optional, Tuple
import asyncio
from functools import partial
import numpy as np

# Import différé — sentence_transformers tire PyTorch (~30s sur machines lentes)
# L'import réel se fait à la première utilisation dans __init__
TRANSFORMERS_AVAILABLE: Optional[bool] = None  # None = pas encore vérifié


def _check_transformers() -> bool:
    global TRANSFORMERS_AVAILABLE
    if TRANSFORMERS_AVAILABLE is None:
        try:
            import sentence_transformers  # noqa: F401
            TRANSFORMERS_AVAILABLE = True
        except ImportError:
            TRANSFORMERS_AVAILABLE = False
    return bool(TRANSFORMERS_AVAILABLE)


class SemanticRouter:
    """Routage par similarité sémantique"""

    def __init__(self, model_name: str = "sentence-transformers/bge-small-en-v1.5"):
        self.model_name = model_name
        self.model = None
        self.agent_embeddings: Dict[str, np.ndarray] = {}
        self.agent_descriptions: Dict[str, str] = {}
        self.initialized = False

        if _check_transformers():
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(model_name)
                self.initialized = True
            except Exception as e:
                print(f"⚠ SemanticRouter initialization failed: {e}")

    async def initialize_agents(self, agents: Dict[str, "Agent"]) -> None:
        """Pré-calcule les embeddings de tous les agents"""
        if not self.initialized or not self.model:
            return

        agent_descriptions = {}
        for agent_name, agent in agents.items():
            description = agent.config.get("description", agent_name)
            agent_descriptions[agent_name] = description

        # Encodage parallèle
        descriptions_list = list(agent_descriptions.values())
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, partial(self.model.encode, descriptions_list, convert_to_numpy=True)
        )

        for (agent_name, description), embedding in zip(agent_descriptions.items(), embeddings):
            self.agent_embeddings[agent_name] = embedding
            self.agent_descriptions[agent_name] = description

        print(f"✓ Semantic router initialized with {len(self.agent_embeddings)} agents")

    async def route(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """
        Route une query vers les top-k agents les plus similaires

        Returns: List of (agent_name, similarity_score)
        """
        if not self.initialized or not self.model or not self.agent_embeddings:
            return []

        # Encoder la query
        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(
            None, partial(self.model.encode, query, convert_to_numpy=True)
        )

        # Calculer les similarités
        similarities = {}
        for agent_name, agent_embedding in self.agent_embeddings.items():
            similarity = self._cosine_similarity(query_embedding, agent_embedding)
            similarities[agent_name] = similarity

        # Retourner les top-k
        sorted_agents = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        return sorted_agents[:top_k]

    async def route_single(self, query: str, confidence_threshold: float = 0.5) -> Optional[str]:
        """
        Route vers un seul agent si la confiance est suffisante

        Returns: agent_name or None si confiance insuffisante
        """
        results = await self.route(query, top_k=2)
        if not results:
            return None

        best_agent, best_score = results[0]

        # Vérifier qu'il y a une bonne séparation avec le second
        if len(results) > 1:
            second_score = results[1][1]
            confidence = best_score - second_score
        else:
            confidence = best_score

        if best_score >= confidence_threshold and confidence > 0.1:
            return best_agent

        return None

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calcule la similarité cosinus"""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def get_agent_info(self) -> Dict[str, str]:
        """Retourne les descriptions des agents"""
        return self.agent_descriptions.copy()

    def is_available(self) -> bool:
        """Vérifie si le routeur sémantique est disponible"""
        return self.initialized and self.model is not None
