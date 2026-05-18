import os
import litellm
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"Testing with API Key: {api_key[:10]}...")

try:
    # Try a simple completion with a different model name format
    response = litellm.completion(
        model="gemini/gemini-pro",
        messages=[{"role": "user", "content": "hi"}],
        api_key=api_key
    )
    print("Success with gemini/gemini-pro")
except Exception as e:
    print(f"Failed with gemini/gemini-pro: {e}")

try:
    response = litellm.completion(
        model="gemini/gemini-1.5-flash-latest",
        messages=[{"role": "user", "content": "hi"}],
        api_key=api_key
    )
    print("Success with gemini/gemini-1.5-flash-latest")
except Exception as e:
    print(f"Failed with gemini/gemini-1.5-flash-latest: {e}")
