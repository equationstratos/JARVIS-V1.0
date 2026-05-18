"""
Cache Manager — Caching intelligent pour les réponses et les décisions de routage
"""
import hashlib
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import asyncio

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheManager:
    """Gère le caching avec Redis ou en-mémoire"""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 3600,
        max_memory_items: int = 1000,
    ):
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.max_memory_items = max_memory_items
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Tuple[Any, datetime]] = {}
        self.use_redis = REDIS_AVAILABLE and redis_url is not None

    async def connect(self):
        """Initialise la connexion Redis"""
        if self.use_redis:
            try:
                self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)
                await self.redis_client.ping()
                print("✓ Redis cache connected")
            except Exception as e:
                print(f"⚠ Redis connection failed: {e}, falling back to memory cache")
                self.use_redis = False

    async def disconnect(self):
        """Ferme la connexion Redis"""
        if self.redis_client:
            await self.redis_client.close()

    def _hash_key(self, *parts: str) -> str:
        """Crée une clé hash unique"""
        combined = ":".join(str(p) for p in parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    async def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache"""
        if self.use_redis and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception:
                pass

        # Fallback: memory cache
        if key in self.memory_cache:
            value, expiry = self.memory_cache[key]
            if datetime.now() < expiry:
                return value
            else:
                del self.memory_cache[key]

        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Définit une valeur dans le cache"""
        ttl = ttl or self.ttl_seconds

        try:
            serialized = json.dumps(value, default=str)
        except Exception:
            return False

        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.setex(key, ttl, serialized)
                return True
            except Exception:
                pass

        # Memory cache
        if len(self.memory_cache) >= self.max_memory_items:
            oldest_key = min(self.memory_cache, key=lambda k: self.memory_cache[k][1])
            del self.memory_cache[oldest_key]

        self.memory_cache[key] = (value, datetime.now() + timedelta(seconds=ttl))
        return True

    async def delete(self, key: str) -> bool:
        """Supprime une valeur du cache"""
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception:
                pass

        if key in self.memory_cache:
            del self.memory_cache[key]

        return True

    async def cache_response(
        self,
        prompt: str,
        response: str,
        agent_name: str,
        confidence: float,
        ttl: Optional[int] = None,
    ) -> str:
        """Cache une réponse d'agent avec score de confiance"""
        key = f"response:{agent_name}:{self._hash_key(prompt)}"
        value = {
            "response": response,
            "confidence": confidence,
            "cached_at": datetime.now().isoformat(),
        }
        await self.set(key, value, ttl)
        return key

    async def get_cached_response(self, prompt: str, agent_name: str) -> Optional[Tuple[str, float]]:
        """Récupère une réponse cachée"""
        key = f"response:{agent_name}:{self._hash_key(prompt)}"
        cached = await self.get(key)
        if cached:
            return cached["response"], cached["confidence"]
        return None

    async def cache_routing_decision(
        self, query: str, agent_name: str, ttl: Optional[int] = None
    ) -> None:
        """Cache une décision de routage"""
        key = f"routing:{self._hash_key(query)}"
        await self.set(key, {"agent": agent_name, "cached_at": datetime.now().isoformat()}, ttl)

    async def get_cached_routing(self, query: str) -> Optional[str]:
        """Récupère une décision de routage cachée"""
        key = f"routing:{self._hash_key(query)}"
        cached = await self.get(key)
        if cached:
            return cached["agent"]
        return None

    async def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        stats = {
            "memory_items": len(self.memory_cache),
            "redis_enabled": self.use_redis and self.redis_client is not None,
        }

        if self.use_redis and self.redis_client:
            try:
                info = await self.redis_client.info()
                stats["redis_memory_bytes"] = info.get("used_memory", 0)
                stats["redis_keys"] = await self.redis_client.dbsize()
            except Exception:
                pass

        return stats
