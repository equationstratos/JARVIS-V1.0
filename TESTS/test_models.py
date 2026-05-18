"""
Test des modèles LLM configurés dans JARVIS.
Teste Ollama en priorité (local, gratuit), puis les modèles cloud si les clés sont présentes.
"""
import os
import sys
import litellm
from dotenv import load_dotenv

# Charger .env depuis la racine du projet
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

default_model = os.getenv('JARVIS_DEFAULT_MODEL', 'ollama/mistral-small3.2')
google_key = os.getenv('GOOGLE_API_KEY')
anthropic_key = os.getenv('ANTHROPIC_API_KEY')

print(f"Default model: {default_model}")
print(f"GOOGLE_API_KEY:    {'set' if google_key else 'not set'}")
print(f"ANTHROPIC_API_KEY: {'set' if anthropic_key else 'not set'}")
print()

success_count = 0
fail_count = 0


# 1. Test Ollama (toujours testé en premier — local et gratuit)
print("Testing Ollama (local)...")
try:
    response = litellm.completion(
        model="ollama/mistral-small3.2",
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        api_base="http://localhost:11434",
        max_tokens=10,
    )
    print("  OK: ollama/mistral-small3.2 responded")
    success_count += 1
except Exception as e:
    print(f"  FAILED: ollama/mistral-small3.2 — {e}")
    print("  (Make sure Ollama is running: ollama serve)")
    fail_count += 1


# 2. Test llama3 via Ollama
print("\nTesting Ollama llama3...")
try:
    response = litellm.completion(
        model="ollama/llama3",
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        api_base="http://localhost:11434",
        max_tokens=10,
    )
    print("  OK: ollama/llama3 responded")
    success_count += 1
except Exception as e:
    print(f"  FAILED: ollama/llama3 — {e}")
    print("  (Pull model: ollama pull llama3)")
    fail_count += 1


# 3. Test Google Gemini (seulement si clé disponible)
if google_key:
    print("\nTesting Google Gemini...")
    try:
        response = litellm.completion(
            model="gemini/gemini-2.0-flash",
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            api_key=google_key,
            max_tokens=10,
        )
        print("  OK: gemini/gemini-2.0-flash responded")
        success_count += 1
    except Exception as e:
        print(f"  FAILED: gemini/gemini-2.0-flash — {e}")
        fail_count += 1
else:
    print("\nSkipping Google Gemini test (GOOGLE_API_KEY not set)")


# 4. Test Anthropic Claude (seulement si clé disponible)
if anthropic_key:
    print("\nTesting Anthropic Claude...")
    try:
        response = litellm.completion(
            model="claude-haiku-4-5",
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            api_key=anthropic_key,
            max_tokens=10,
        )
        print("  OK: claude-haiku-4-5 responded")
        success_count += 1
    except Exception as e:
        print(f"  FAILED: claude-haiku-4-5 — {e}")
        fail_count += 1
else:
    print("\nSkipping Anthropic Claude test (ANTHROPIC_API_KEY not set)")


print(f"\nResults: {success_count} passed, {fail_count} failed")
sys.exit(0 if fail_count == 0 else 1)
