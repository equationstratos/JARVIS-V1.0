import os
from dotenv import load_dotenv

# Use absolute path for safety
dotenv_path = '/home/stratos/JARVIS/.env'
print(f"Loading from: {dotenv_path}")
load_dotenv(dotenv_path)

key = os.getenv('GEMINI_API_KEY')
print(f"GEMINI_API_KEY value: {key}")
