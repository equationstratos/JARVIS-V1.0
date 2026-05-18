# JARVIS Mobile Chat

A cross-platform mobile chat application (Android & iPhone) with:
- **Live streaming responses** (real-time token streaming)
- **Multi-model support** (API models + local Ollama)
- **Gemini-like interface** with dark theme
- **Fast switching** between models

## Quick Start

```bash
cd mobile
npm install
npm start
```

Then:
- Press `a` for Android emulator
- Press `i` for iOS simulator
- Scan QR code with Expo Go for real device

## Features

- 🔴 **Live Mode**: Stream responses token-by-token
- 🤖 **50+ Models**: Claude, Gemini, GPT-4, Llama, Mistral, etc.
- 🏠 **Local Ollama**: Run models locally on your machine
- 🔧 **Custom Server**: Point to your own JARVIS backend
- 📱 **Native UI**: Optimized for Android & iOS

## Configuration

1. **Server URL**: Navigate to Models tab to set your backend URL (default: `http://localhost:8501`)
2. **Model Selection**: Browse and select from 50+ available models
3. **Live Mode**: Toggle in chat header to enable streaming

## Backend Integration

This app connects to the JARVIS FastAPI backend. Make sure:

```bash
cd ..
python interfaces/web_v2.py
# Server runs on http://localhost:8501
```

## Architecture

```
mobile/
├── App.tsx                 # Main navigation
├── src/
│   ├── screens/           # Chat, Models, Settings
│   ├── store/             # Zustand state management
│   └── api/               # JARVIS API client
└── package.json           # Dependencies
```

## API Endpoints Used

- `POST /chat` - Send message (non-streaming)
- `POST /chat/stream` - Send message (streaming)
- `POST /clear` - Clear chat history
- `GET /health` - Server health check

## Model Categories

**API Models** (require credentials):
- Gemini 2.0 Flash
- Claude 3.5 Sonnet
- GPT-4 Turbo
- Mistral

**Local Models** (via Ollama):
- Llama 2
- Mistral
- Neural Chat
- Dolphin Mixtral

## Requirements

- Node.js 18+
- Expo CLI: `npm install -g expo-cli`
- JARVIS backend running (for full functionality)
- Ollama installed locally (for Ollama models)
