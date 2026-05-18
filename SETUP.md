# JARVIS Setup & Installation Guide

## Quick Start (5 minutes)

### 1. Clone & Install Dependencies

```bash
cd /path/to/JARVISGITHUB
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure API Keys

Copy the example configuration and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add:

```env
# REQUIRED: At least one API key
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
GOOGLE_API_KEY=xxxxxxxxxxxxx

# OPTIONAL: Redis for distributed caching
REDIS_HOST=localhost
REDIS_PORT=6379

# OPTIONAL: Observability
OTEL_ENABLED=false
```

### 3. Test Configuration

```bash
python test_configuration.py
```

Expected output:
```
✅ ALL TESTS PASSED!
✓ Configuration valid
✓ Cache Manager OK
✓ Response Validator OK
✓ Semantic Router available: true/false
✓ Observability Manager OK
✓ Orchestrator loaded 7 agents
✓ Routing logic working correctly
```

### 4. Start JARVIS

#### Option A: Web Interface (Recommended)

```bash
python main.py --web
# Server starts at http://localhost:8501
```

#### Option B: Terminal UI

```bash
python main.py --tui
```

## Configuration Details

### Model Selection

Default models are configured in `config.py`:

| Model | Use Case |
|-------|----------|
| `claude-opus-4-7` | Primary model (all agents) |
| `gemini/gemini-2.0-flash` | Fallback if Anthropic unavailable |

Override per-agent:
```json
{
  "name": "MyAgent",
  "model": "claude-opus-4-7",
  "temperature": 0.2,
  "max_tokens": 2048
}
```

### Agents Configuration

Agent configs are in `agents/configs/*.json`:

1. **ShellAgent**: System commands execution (temp: 0.2)
2. **GitAgent**: Version control operations (temp: 0.1)
3. **CodeMaster**: Code writing & refactoring (temp: 0.1)
4. **WebResearcher**: Web search & information (temp: 0.1)
5. **PlannerAgent**: Project planning & strategy (temp: 0.2)
6. **Manager**: General conversation & coordination (temp: 0.3)
7. **MemoryAgent**: Learning & pattern recognition (temp: 0.1)

### Caching Strategy

JARVIS uses 3-layer caching:

1. **Response Cache** (1 hour TTL)
   - Caches complete agent responses
   - Keyed on: agent_name + query_hash
   - Hit rate > 40% for common queries

2. **Routing Cache** (2 hour TTL)
   - Caches agent routing decisions
   - Saves ~400ms per ambiguous query

3. **Memory Cache** (fallback)
   - In-memory LRU cache (max 1000 items)
   - Used if Redis unavailable
   - Automatic cleanup on overflow

Enable Redis for distributed caching:
```env
REDIS_HOST=redis.example.com
REDIS_PORT=6379
ENABLE_CACHING=true
```

### Validation & Response Quality

All responses are validated:

1. **Format Check**: Is it well-formed?
2. **Content Check**: Does it answer the question? (LLM-based)
3. **Confidence Scoring**: 0.0-1.0 score
4. **Auto-Improvement**: Retries if confidence < 0.5

Disable validation for faster responses:
```json
{
  "name": "FastAgent",
  "enable_validation": false
}
```

### Semantic Routing

Uses `bge-small` embeddings for intelligent agent selection:

```env
ENABLE_VECTOR_ROUTING=true
```

Routing pipeline:
1. Keywords match (0ms) ← Try first
2. Semantic similarity (50ms) ← If keywords ambiguous
3. LLM routing (500ms) ← If still uncertain
4. Default to Manager ← Last resort

### Observability & Monitoring

Enable OpenTelemetry for production:

```env
ENABLE_OBSERVABILITY=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

View metrics:
```bash
# Export local metrics to JSON
curl http://localhost:8501/metrics
```

Metrics include:
- Per-agent latency (p50, p95, p99)
- Token usage per model
- Cache hit rates
- Response confidence scores
- Validation pass rates

## Environment Variables

### Required

```env
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

### Optional

```env
# Models
JARVIS_DEFAULT_MODEL=claude-opus-4-7
JARVIS_ROUTING_MODEL=claude-opus-4-7
JARVIS_FALLBACK_MODEL=gemini/gemini-2.0-flash

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8501
SERVER_LOG_LEVEL=warning

# Caching
ENABLE_CACHING=true
REDIS_HOST=localhost
REDIS_PORT=6379

# Features
ENABLE_MEMORY_AGENT=true
ENABLE_VECTOR_ROUTING=true
ENABLE_OBSERVABILITY=false

# Observability
OTEL_ENABLED=false
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

## Troubleshooting

### "model not found" error

Check that your API keys are valid:
```bash
export ANTHROPIC_API_KEY=xxx
python -c "import litellm; print(litellm.completion(model='claude-opus-4-7', messages=[{'role':'user','content':'hi'}]))"
```

### Low precision (< 50%)

1. Check that Claude Opus 4.7 is configured in agents
2. Enable validation: `"enable_validation": true` in agent configs
3. Check model temperature: 0.1-0.3 for precision tasks
4. Increase max_tokens: 1024-2048 for complex responses

### Slow response times

1. Enable caching: `ENABLE_CACHING=true`
2. Use semantic routing: `ENABLE_VECTOR_ROUTING=true`
3. Check network latency to API endpoints
4. Consider using Gemini as fallback for faster responses

### Redis connection issues

```bash
# Test Redis connection
redis-cli ping

# If not running:
docker run -d -p 6379:6379 redis:7

# Or disable Redis fallback (uses in-memory cache)
ENABLE_CACHING=false
```

## Performance Targets

With optimal configuration:

| Metric | Target | Current |
|--------|--------|---------|
| Time-to-first-token (TTFB) | 300-600ms | - |
| End-to-end latency | 1-2s | - |
| Routing latency | < 50ms | - |
| Cache hit rate | > 30% | - |
| Response precision | 95-100% | - |

## Upgrading Dependencies

```bash
pip install -U -r requirements.txt
```

## For Production Deployment

### 1. Security

- Never commit `.env` to git
- Use environment variables for secrets
- Add authentication to API endpoints
- Use HTTPS in production

### 2. Scaling

- Deploy multiple workers with uvicorn
- Use Redis for shared cache
- Set up observability (OTLP collector)
- Monitor metrics with Grafana

### 3. Reliability

- Enable response caching
- Set up health checks
- Configure circuit breakers
- Use semantic routing for robustness

### Example Docker Compose

```yaml
version: '3.8'
services:
  jarvis:
    build: .
    ports:
      - "8501:8501"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
      REDIS_HOST: redis
      ENABLE_CACHING: "true"
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  otel-collector:
    image: otel/opentelemetry-collector:latest
    ports:
      - "4317:4317"
    volumes:
      - ./otel-config.yaml:/etc/otel-collector-config.yaml
```

## Need Help?

- Check existing logs: `tail -f /tmp/jarvis.log`
- Run diagnostics: `python test_configuration.py`
- Review agent configs: `ls agents/configs/`
- Check metrics: Visit `http://localhost:8501/metrics`

---

**Last Updated**: 2025-05-11  
**Version**: 2.0 (Major Architecture Upgrade)
