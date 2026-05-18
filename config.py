"""
Configuration centralisée pour JARVIS
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()


class JARVISConfig:
    """Configuration principale de JARVIS"""

    # Models
    DEFAULT_MODEL = os.getenv("JARVIS_DEFAULT_MODEL", "claude-opus-4-7")
    ROUTING_MODEL = os.getenv("JARVIS_ROUTING_MODEL", "claude-opus-4-7")
    FALLBACK_MODEL = os.getenv("JARVIS_FALLBACK_MODEL", "gemini/gemini-2.0-flash")

    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

    # Server
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8501"))
    SERVER_LOG_LEVEL = os.getenv("SERVER_LOG_LEVEL", "warning")

    # Features
    ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    ENABLE_MEMORY_AGENT = os.getenv("ENABLE_MEMORY_AGENT", "true").lower() == "true"
    ENABLE_VECTOR_ROUTING = os.getenv("ENABLE_VECTOR_ROUTING", "false").lower() == "true"
    ENABLE_OBSERVABILITY = os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true"

    # Observability
    OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    @classmethod
    def validate(cls) -> tuple[bool, list[str]]:
        """Valide la configuration et retourne (is_valid, errors)"""
        errors = []

        using_ollama = cls.DEFAULT_MODEL.startswith("ollama/")
        if not using_ollama and not cls.ANTHROPIC_API_KEY and not cls.GOOGLE_API_KEY:
            errors.append("At least one API key must be configured (ANTHROPIC_API_KEY or GOOGLE_API_KEY)")

        if cls.ANTHROPIC_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = cls.ANTHROPIC_API_KEY
        if cls.GOOGLE_API_KEY:
            os.environ["GOOGLE_API_KEY"] = cls.GOOGLE_API_KEY

        return len(errors) == 0, errors

    @classmethod
    def get_redis_url(cls) -> str:
        """Construit l'URL Redis"""
        password = f":{cls.REDIS_PASSWORD}@" if cls.REDIS_PASSWORD else ""
        return f"redis://{password}{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"

    @classmethod
    def summary(cls) -> str:
        """Retourne un résumé de la configuration"""
        return f"""
JARVIS Configuration Summary:
  Default Model: {cls.DEFAULT_MODEL}
  Routing Model: {cls.ROUTING_MODEL}
  Fallback Model: {cls.FALLBACK_MODEL}
  Caching Enabled: {cls.ENABLE_CACHING}
  Vector Routing: {cls.ENABLE_VECTOR_ROUTING}
  Observability: {cls.ENABLE_OBSERVABILITY}
  Redis: {cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}
"""
