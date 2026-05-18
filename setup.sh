#!/bin/bash
echo "Setting up JARVIS ecosystem..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
if [ ! -f .env ]; then
    echo "Creating .env file. Please fill in your API keys."
    echo "GEMINI_API_KEY=" >> .env
    echo "OPENAI_API_KEY=" >> .env
    echo "ANTHROPIC_API_KEY=" >> .env
    echo "MISTRAL_API_KEY=" >> .env
fi
echo "Setup complete. Use 'source venv/bin/activate' and 'python main.py --tui' to start."
