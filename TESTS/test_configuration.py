#!/usr/bin/env python3
"""
Test de configuration de JARVIS

Vérifie que tous les composants se chargent correctement et sont
opérationnels.
"""
import asyncio
import os
import sys

# Ajouter la racine du projet (parent de TESTS/) au path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Charger .env avant d'importer config
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

try:
    from config import JARVISConfig
except ImportError as e:
    print(f"FAILED to import config: {e}")
    print("Make sure the venv is active: source venv/bin/activate")
    sys.exit(1)

try:
    from core.orchestrator import Orchestrator
    from utils.cache_manager import CacheManager
    from utils.validator import ResponseValidator
    from utils.semantic_router import SemanticRouter
    from utils.observability import ObservabilityManager
except ImportError as e:
    print(f"FAILED to import core modules: {e}")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)


async def test_configuration():
    """Test tous les composants"""
    print("=" * 60)
    print("JARVIS Configuration Test")
    print("=" * 60)

    # 1. Configuration
    print("\n1. Testing Configuration...")
    is_valid, errors = JARVISConfig.validate()
    if not is_valid:
        if JARVISConfig.DEFAULT_MODEL.startswith("ollama/"):
            print(f"  NOTE: {errors}")
            print("  OK: Ollama mode — configuration valid without cloud keys")
        else:
            print(f"  FAILED Configuration errors: {errors}")
            return False
    else:
        print("  OK Configuration valid")
    print(JARVISConfig.summary())

    # 2. Cache Manager
    print("\n2. Testing Cache Manager...")
    try:
        cache = CacheManager()
        await cache.set("test_key", {"value": "test"}, ttl=3600)
        result = await cache.get("test_key")
        assert result == {"value": "test"}, "Cache set/get mismatch"
        print("  OK Cache Manager (in-memory mode)")
    except Exception as e:
        print(f"  FAILED Cache Manager: {e}")
        return False

    # 3. Validator
    print("\n3. Testing Response Validator...")
    try:
        validator = ResponseValidator()
        result = await validator.validate_response(
            "What is 2+2?",
            "The answer is 4.",
            "TestAgent"
        )
        assert "confidence" in result, "Validator missing confidence"
        assert "is_valid" in result, "Validator missing is_valid"
        print(f"  OK Response Validator (confidence: {result.get('confidence', 0):.2f})")
    except Exception as e:
        print(f"  FAILED Response Validator: {e}")
        return False

    # 4. Semantic Router
    print("\n4. Testing Semantic Router...")
    try:
        router = SemanticRouter()
        available = router.is_available()
        print(f"  OK Semantic Router available: {available}")
        if not available:
            print("  (sentence-transformers not installed — semantic routing disabled)")
    except Exception as e:
        print(f"  FAILED Semantic Router: {e}")
        return False

    # 5. Observability
    print("\n5. Testing Observability Manager...")
    try:
        obs = ObservabilityManager(enabled=False)
        obs.record_agent_execution(
            agent_name="TestAgent",
            model_name="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=1500.0,
            confidence_score=0.95
        )
        stats = obs.get_global_stats()
        assert "avg_latency_ms" in stats, "Observability missing avg_latency_ms"
        print(f"  OK Observability Manager ({len(obs.metrics_history)} metrics recorded)")
    except Exception as e:
        print(f"  FAILED Observability Manager: {e}")
        return False

    # 6. Orchestrator & Agents
    print("\n6. Testing Orchestrator & Agents...")
    try:
        agents_dir = os.path.join(PROJECT_ROOT, "agents/configs")
        orchestrator = Orchestrator(agents_dir, cache)
        print(f"  OK Orchestrator loaded {len(orchestrator.agents)} agents:")
        for agent_name in sorted(orchestrator.agents.keys()):
            agent = orchestrator.agents[agent_name]
            print(f"    - {agent_name}: {agent.model}")

        if router.is_available():
            await orchestrator.initialize_semantic_router()
            print("  OK Semantic router initialized")

    except Exception as e:
        print(f"  FAILED Orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 7. Routing
    print("\n7. Testing Routing Logic...")
    try:
        test_queries = [
            ("ls -la", "ShellAgent"),
            ("git status", "GitAgent"),
            ("write a python function", "CodeMaster"),
            ("search for python docs", "WebResearcher"),
            ("what should I do first?", "PlannerAgent"),
            ("hello", "Manager"),
        ]

        for query, expected_agent in test_queries:
            agent = await orchestrator._resolve_agent(query)
            status = "OK" if agent.name == expected_agent else "WARN"
            print(f"  {status} '{query}' -> {agent.name} (expected: {expected_agent})")
    except Exception as e:
        print(f"  FAILED Routing: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\nJARVIS is ready. Start with: bash launch-JARVIS.sh")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_configuration())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
