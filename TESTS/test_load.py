"""
Test de chargement de la configuration .env de JARVIS.
"""
import os
from dotenv import load_dotenv

# Résoudre .env depuis la racine du projet (un niveau au-dessus de TESTS/)
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
dotenv_path = os.path.join(PROJECT_ROOT, '.env')

print(f"Loading from: {dotenv_path}")

if not os.path.exists(dotenv_path):
    print(f"WARNING: .env not found at {dotenv_path}")
    print("Copy .env.example to .env and configure your settings.")
else:
    load_dotenv(dotenv_path)
    print("OK: .env loaded")

google_key = os.getenv('GOOGLE_API_KEY')
anthropic_key = os.getenv('ANTHROPIC_API_KEY')
default_model = os.getenv('JARVIS_DEFAULT_MODEL', 'not set')

print(f"GOOGLE_API_KEY:       {'set (' + google_key[:8] + '...)' if google_key else 'not set'}")
print(f"ANTHROPIC_API_KEY:    {'set (' + anthropic_key[:8] + '...)' if anthropic_key else 'not set'}")
print(f"JARVIS_DEFAULT_MODEL: {default_model}")

if default_model.startswith("ollama/"):
    print("\nOK: Ollama mode — no cloud API keys required.")
elif not google_key and not anthropic_key:
    print("\nWARNING: No API keys set. Add ANTHROPIC_API_KEY or GOOGLE_API_KEY in .env for cloud models.")
else:
    print("\nOK: At least one cloud API key is configured.")
