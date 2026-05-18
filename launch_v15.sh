#!/bin/bash

# Kill existing processes
echo "Stopping existing services..."
pkill -f tts_server4.py
pkill -f web_v2.py

# Launch TTS Server
echo "Starting TTS Server..."
cd ../jarvis-voice
python3 tts_server4.py &
TTS_PID=$!
cd ../JARVISV15

# Launch Main Server
echo "Starting Main Server..."
cd interfaces/
python3 web_v2.py &
MAIN_PID=$!

echo "JARVIS V15 started (TTS PID: $TTS_PID, Main PID: $MAIN_PID)"
echo "Press Ctrl+C to stop both."

# Wait for process exit
wait
