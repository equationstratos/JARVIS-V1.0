import requests
import json

def test_stream():
    print("Testing backend streaming endpoint...")
    response = requests.post(
        "http://localhost:8501/chat-stream",
        json={"command": "ls -la"}
    )
    
    if response.status_code == 200:
        print("Success! Streaming response received.")
        print(response.text)
    else:
        print(f"Failed. Status code: {response.status_code}")

if __name__ == "__main__":
    test_stream()
