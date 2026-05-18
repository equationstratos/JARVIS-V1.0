"""
Test du endpoint de streaming SSE du backend JARVIS.
Nécessite que le backend soit lancé : python main.py --web
"""
import sys
import requests

BACKEND_URL = "http://localhost:8501"


def test_stream():
    print("Testing backend streaming endpoint...")
    print(f"Endpoint: {BACKEND_URL}/chat/stream")

    try:
        response = requests.post(
            f"{BACKEND_URL}/chat/stream",
            json={"command": "say hello"},
            stream=True,
            timeout=30,
        )

        if response.status_code == 200:
            print("Success! Streaming response:")
            print("-" * 40)
            for chunk in response.iter_content(chunk_size=None):
                if chunk:
                    print(chunk.decode('utf-8'), end='', flush=True)
            print("\n" + "-" * 40)
            print("Stream complete.")
        else:
            print(f"Failed. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)

    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to {BACKEND_URL}")
        print("Start the backend first: python main.py --web")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out after 30s")
        sys.exit(1)


if __name__ == "__main__":
    test_stream()
