import requests
from typing import Optional

def get_public_ip() -> Optional[str]:
    """
    Retrieves the public IP address of the machine using api.ipify.org.
    
    Returns:
        str: The public IP address if successful, None otherwise.
    """
    url = "https://api.ipify.org"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving public IP: {e}")
        return None

if __name__ == "__main__":
    ip = get_public_ip()
    if ip:
        print(f"Public IP Address: {ip}")
    else:
        print("Failed to retrieve public IP.")
