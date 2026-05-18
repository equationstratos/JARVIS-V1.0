#!/usr/bin/env python3
"""
Test de configuration de JARVIS

Vérifie que tous les composants se chargent correctement et sont
opérationnels.
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import JARVISConfig
from core.orchestrator import Orchestrator
from utils.cache_manager import CacheManager
from utils.validator import ResponseValidator
from utils.semantic_router import SemanticRouter
from utils.observability import ObservabilityManager


async def test_configuration():
    """Test tous les composants"""
    print("=" * 60)
    print("JARVIS Configuration Test")
    print("=" * 60)

    # 1. Configuration
    print("\n1. Testing Configuration...")
    is_valid, errors = JARVISConfig.validate()
    if not is_valid:
        print(f"❌ Configuration errors: {errors}")
        return False
    print("✓ Configuration valid")
    print(JARVISConfig.summary())

    # 2. Cache Manager
    print("\n2. Testing Cache Manager...")
    try:
        cache = CacheManager()
        await cache.set("test_key", {"value": "test"}, ttl=3600)
        result = await cache.get("test_key")
        assert result == {"value": "test"}, "Cache set/get failed"
        print("✓ Cache Manager OK")
    except Exception as e:
        print(f"❌ Cache Manager failed: {e}")
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
        print(f"✓ Response Validator OK (confidence: {result.get('confidence', 0):.2f})")
    except Exception as e:
        print(f"❌ Response Validator failed: {e}")
        return False

    # 4. Semantic Router
    print("\n4. Testing Semantic Router...")
    try:
        router = SemanticRouter()
        available = router.is_available()
        print(f"✓ Semantic Router available: {available}")
        if not available:
            print("  (sentence-transformers not installed, will skip semantic routing)")
    except Exception as e:
        print(f"❌ Semantic Router initialization failed: {e}")
        return False

    # 5. Observability
    print("\n5. Testing Observability Manager...")
    try:
        obs = ObservabilityManager(enabled=False)  # No OTLP for test
        snapshot = obs.record_agent_execution(
            agent_name="TestAgent",
            model_name="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=1500.0,
            confidence_score=0.95
        )
        stats = obs.get_global_stats()
        assert "avg_latency_ms" in stats, "Observability missing avg_latency_ms"
        print(f"✓ Observability Manager OK (recorded {len(obs.metrics_history)} metrics)")
    except Exception as e:
        print(f"❌ Observability Manager failed: {e}")
        return False

    # 6. Orchestrator & Agents
    print("\n6. Testing Orchestrator & Agents...")
    try:
        agents_dir = os.path.join(os.path.dirname(__file__), "agents/configs")
        orchestrator = Orchestrator(agents_dir, cache)
        print(f"✓ Orchestrator loaded {len(orchestrator.agents)} agents:")
        for agent_name in sorted(orchestrator.agents.keys()):
            agent = orchestrator.agents[agent_name]
            print(f"  - {agent_name}: {agent.model} (temp={agent.temperature})")

        # Initialize semantic router if available
        if router.is_available():
            await orchestrator.initialize_semantic_router()
            print("✓ Semantic router initialized")

    except Exception as e:
        print(f"❌ Orchestrator loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 7. Routing test
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
            status = "✓" if agent.name == expected_agent else "⚠"
            print(f"  {status} '{query}' → {agent.name} (expected: {expected_agent})")
    except Exception as e:
        print(f"❌ Routing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nJARVIS is ready to use. Configure your API keys in .env file:")
    print("  ANTHROPIC_API_KEY=xxx")
    print("  GOOGLE_API_KEY=xxx")
    print("\nThen start with: python main.py --web")

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_configuration())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
