# Mobile App Development Guide

## Architecture Overview

```
┌─────────────────────────────────────────┐
│         Mobile App (React Native)       │
│  Chat | Models | Settings screens       │
└──────────────┬──────────────────────────┘
               │
               │ HTTP/SSE
               │
┌──────────────▼──────────────────────────┐
│    JARVIS Backend (FastAPI)             │
│  - /chat (POST)                         │
│  - /chat/stream (POST - SSE)            │
│  - /health (GET)                        │
│  - /api/models (GET)                    │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
    ┌───▼────┐   ┌───▼────┐
    │  Ollama │   │  APIs  │
    │ (Local) │   │ (Cloud)│
    └────────┘   └────────┘
```

## State Management (Zustand)

The app uses **Zustand** for global state:

```typescript
// Chat state
messages[]           // Message history
selectedModel        // Current model
serverUrl           // Backend URL
isLoading           // Streaming indicator
liveMode            // Live/Standard mode toggle
```

## Component Hierarchy

```
App.tsx (Navigation Container)
├── ChatStack (Chat Screen)
│   └── ChatScreen
│       ├── MessagesList (FlatList)
│       ├── InputBar
│       └── LiveToggle
├── ModelsScreen
│   ├── ServerConfig
│   ├── ModelSelector
│   └── HealthCheck
└── SettingsScreen
    ├── ChatSettings
    ├── About
    └── Features
```

## API Integration

### Chat with Streaming (Live Mode)

```typescript
// Client-side (mobile)
const response = await client.chatStream({
  query: userMessage,
  model: selectedModel,
  liveMode: true,
});

for await (const token of response) {
  updateLastMessage(fullText += token);
}
```

```python
# Server-side (FastAPI)
@app.post("/chat/stream")
async def chat_stream(request: Request):
    async def event_stream():
        for token in llm.stream(prompt):
            yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Model Support

**API Models** (credentials in .env):
- Gemini 2.0 Flash (Google)
- Claude 3.5 Sonnet (Anthropic)
- GPT-4 Turbo (OpenAI)
- Mistral (Mistral AI)

**Local Models** (via Ollama):
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull and run a model
ollama pull llama2
ollama serve  # Starts on http://localhost:11434
```

Then point mobile app to your JARVIS backend which connects to both.

## Development Workflow

### 1. Start Backend
```bash
cd ..
python interfaces/web_v2.py
# Server: http://localhost:8501
```

### 2. Start Mobile App
```bash
npm install
npm start
# Press 'a' for Android, 'i' for iOS, or scan QR code
```

### 3. Configure App
- Navigate to **Models** tab
- Check server health (green dot = connected)
- Select a model and start chatting

## Key Features Implementation

### Live Streaming
- Uses SSE (Server-Sent Events) on backend
- Mobile client parses `data: {...}\n\n` format
- Updates UI token-by-token for responsive feel

### Model Switching
- Instant switching in UI
- Backend respects model override via form data
- No message loss when switching

### Offline Support (Future)
- Cache messages locally
- Queue messages when offline
- Sync when connection restored

## Debugging

### Enable Debug Logging
```typescript
// In app initialization
if (process.env.DEBUG) {
  client.enableLogging();
}
```

### Check Server Connection
1. Go to **Models** tab
2. Verify "Server Status: Connected" (green)
3. If offline, check:
   - Server URL is correct
   - Backend is running
   - Network connection

### Common Issues

**"Cannot connect to server"**
- Ensure backend runs on correct port
- Check firewall settings
- Update server URL to match your network

**"Model not found"**
- Verify model is available in backend config
- For Ollama models, ensure Ollama is running
- Check API credentials are set in backend .env

**"Streaming is slow"**
- Check network latency
- Verify model is not overloaded
- Try switching to faster model

## Building for Production

### Android APK
```bash
eas build --platform android --type apk
```

### iOS App
```bash
eas build --platform ios --type simulator
# Then submit to App Store
```

### Web (optional)
```bash
npm run web
```

## Performance Tips

- Keep message history under 100 for smooth scrolling
- Use smaller models for quick responses
- Enable compression in backend nginx
- Cache model metadata locally

## Testing

```bash
# Component testing
npm test

# API testing
curl -X POST http://localhost:8501/chat \
  -F "query=Hello" \
  -F "model=gemini/gemini-2.0-flash"
```
