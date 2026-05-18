import time
import asyncio
import os
import json
import litellm
from core.orchestrator import Orchestrator

# Suppress verbose logs
litellm.set_verbose = False
os.environ["LITELLM_LOG"] = "ERROR"

# Configuration
AGENTS_DIR = "agents/configs"
PROMPTS = [
    "Explique moi brièvement comment fonctionne un LLM.",
    "Crée un script python simple pour lister les fichiers d'un dossier.",
    "Donne-moi une idée de projet innovant en IA pour le domaine de la domotique."
]
MODELS_TO_TEST = [
    "gemini/gemini-2.0-flash",
    "gemini/gemini-pro-latest",
    "gemini/gemini-3.1-flash-lite-preview",
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-opus-20240229",
    "mistral/mistral-large-latest",
    "mistral/mistral-small-latest",
    "ollama/llama3",
    "ollama/mistral"
]

async def run_benchmark():
    orchestrator = Orchestrator(AGENTS_DIR)
    results = {}

    print(f"{'Modèle':<35} | {'Prompt':<40} | {'Latence (s)':<10}")
    print("-" * 90)

    for model in MODELS_TO_TEST:
        orchestrator.set_override_model(model)
        results[model] = []
        
        for prompt in PROMPTS:
            start_time = time.time()
            try:
                # We simulate the chat endpoint logic
                response = await orchestrator.route(prompt, [])
                latency = time.time() - start_time
                results[model].append({"prompt": prompt, "latency": latency})
                print(f"{model:<35} | {prompt[:37]+'...':<40} | {latency:<10.2f}")
            except Exception as e:
                print(f"Error testing {model}: {e}")

    # Summary
    print("\n--- Synthèse ---")
    for model, data in results.items():
        avg_latency = sum(d['latency'] for d in data) / len(data)
        print(f"{model}: Latence moyenne = {avg_latency:.2f}s")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
