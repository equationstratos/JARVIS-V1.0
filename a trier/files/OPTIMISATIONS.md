# JARVIS — Guide d'optimisation et de migration

## 🎯 Résumé des gains attendus

| Métrique                      | Avant         | Après         | Gain          |
|-------------------------------|---------------|---------------|---------------|
| **Time-to-first-token (TTFB)**| ~2-3 s        | ~300-600 ms   | **~5-10x**    |
| Latence routage agent         | ~400-800 ms   | ~0-5 ms       | **~100x**     |
| Réponse perçue (streaming)    | bloquée       | fluide        | qualitatif    |
| Lecture fichiers multiples    | séquentielle  | parallèle     | linéaire ↘    |
| Connexions HTTP litellm       | nouvelles     | keep-alive H2 | -50ms / appel |
| Re-render UI pendant stream   | ~60+ Hz       | 20 Hz max     | -70% CPU      |

## 🔥 Bottlenecks identifiés et corrections

### 1. **CRITIQUE — Double appel LLM pour le routage**
Avant : `orchestrator.py` faisait UN APPEL LLM juste pour choisir l'agent, puis un second pour répondre.
Après : routage par regex de mots-clés (~0ms) avec fallback LLM uniquement sur cas ambigus.
→ **Gain : 400-800ms par message**

### 2. **CRITIQUE — Aucun streaming bout-en-bout**
Avant : `/chat` attend la réponse complète avant de retourner. L'utilisateur voit le spinner pendant 3-5s.
Après : `/chat/stream` en SSE (Server-Sent Events). Le premier token arrive en ~500ms et s'affiche progressivement.
→ **Impact perçu : énorme. C'est CE qui rend la conversation "fluide".**

### 3. **CRITIQUE — Modèles inexistants dans les configs**
`gemini/gemini-3.1-flash-lite-preview` et `gemini/gemini-flash-lite` n'existent pas. Premier appel échouait silencieusement.
Configs corrigées vers `gemini/gemini-2.0-flash` (qui existe et est très rapide).
→ Vérifie dans la console actuelle si tu vois des erreurs `model not found`.

### 4. **HTML cassé — balises manquantes**
`index.html` original n'avait pas de `<body>`, et `</head>` n'était jamais fermé. Les navigateurs faisaient du quirks-mode parsing.
→ Structure HTML5 valide dans la version optimisée.

### 5. **Shell synchrone bloquant**
`subprocess.Popen(...)` bloque l'event loop ; `"".join(list(execute_shell()))` consomme tout d'un coup.
→ Remplacé par `asyncio.create_subprocess_shell` avec stream async.

### 6. **HTTP/1.1 sans keep-alive**
Chaque appel litellm faisait un nouveau handshake TCP+TLS (~80-200ms perdus à chaque requête).
→ Pool `httpx.AsyncClient` avec HTTP/2 et keepalive 60s, configuré au lifespan FastAPI.

### 7. **Three.js chargé même quand non utilisé**
Le `<script>` Three.js (~600KB) bloquait le first paint.
→ Lazy-load à l'activation du toggle, pause du loop quand l'onglet est masqué.

### 8. **Animation grid CSS toujours active**
Pas dramatique mais consomme du GPU sur écrans 4K.
→ Pause auto quand la viz 3D est active (`body.no-bg-anim`).

### 9. **Lecture fichiers séquentielle**
Boucle `for file in files: await file.read()` → temps linéaire.
→ `asyncio.gather(*[read(f) for f in files])` → temps du plus lent.

### 10. **Blackboard re-sérialisé à chaque message**
`json.dumps(blackboard)` à chaque appel d'agent.
→ Cache par hash du dict.

### 11. **uvicorn avec access logs**
Petit gain mais cumule : `access_log=False` + `log_level="warning"`.

### 12. **uvloop**
Sur Linux/macOS, `uvloop` rend l'event loop ~30% plus rapide. Installé via `requirements.txt`.

## 📦 Migration rapide

```bash
# 1. Sauvegarde
cp -r /chemin/vers/JARVISV13 /chemin/vers/JARVISV13.bak

# 2. Copier les fichiers optimisés
cp jarvis_optimized/core/orchestrator.py /chemin/JARVISV13/core/
cp jarvis_optimized/core/agent.py /chemin/JARVISV13/core/
cp jarvis_optimized/utils/shell_utils.py /chemin/JARVISV13/utils/
cp jarvis_optimized/utils/web_utils.py /chemin/JARVISV13/utils/
cp jarvis_optimized/interfaces/web_v2.py /chemin/JARVISV13/interfaces/
cp jarvis_optimized/interfaces/static/index.html /chemin/JARVISV13/interfaces/static/
cp jarvis_optimized/agents/configs/*.json /chemin/JARVISV13/agents/configs/
cp jarvis_optimized/requirements.txt /chemin/JARVISV13/

# 3. Update deps
source venv/bin/activate
pip install -U -r requirements.txt

# 4. Relancer
./launch.sh
```

## 🎨 Améliorations UI au-delà de la perf

1. **Indicateur de streaming visuel** (curseur ▊ clignotant pendant qu'arrivent les tokens)
2. **Stats temps réel** dans la sidebar : TTFB et tokens/seconde — utile pour benchmarker tes modèles
3. **Toggle streaming on/off** pour comparer A/B
4. **Highlighting de l'agent actif** dans la liste sidebar (border cyan)
5. **Pause auto quand onglet masqué** (visibilitychange listener)
6. **Boutons d'action sur chaque message** (TTS individuel, copy individuel)
7. **Reconnexion auto WebSocket** shell (au lieu de mourir silencieusement)
8. **Lazy-load Three.js** (gain ~600KB sur le first load)
9. **DOM cache** dans `dom = {...}` au lieu de `getElementById` à chaque event
10. **Throttle du rendu markdown** à 50ms pendant le streaming (sinon reflows à chaque token)

## 🧠 Améliorations conceptuelles à considérer

### Court terme (faciles à ajouter)

- **Cache de réponses identiques** : `hashlib.sha256(query).hexdigest()` → réponse en mémoire / Redis. Économise 100% sur les questions répétées.
- **Compression de l'historique** : au-delà de 20 messages, résumer les anciens via un LLM cheap (Haiku) une seule fois.
- **Paralléliser tool_calls** quand le LLM en demande plusieurs : c'est déjà fait dans le nouveau `agent.py` via `asyncio.gather`.
- **Streaming TTS** : actuellement le TTS attend la fin de la réponse. On pourrait découper en phrases (`.`, `!`, `?`) et envoyer dès qu'une phrase est complète.

### Moyen terme

- **Vector store pour le routage** : embedder les descriptions d'agents + le query dans un petit modèle (ex: `bge-small`), prendre le plus proche. Plus robuste que les regex pour les cas ambigus, sans appel LLM.
- **Speculative decoding** côté Ollama : si tu utilises des modèles locaux, regarde `llama.cpp` avec un draft model.
- **Prompt caching Anthropic** : si tu utilises Claude, le prompt système est long et identique → caching divise la latence et le coût.
- **WebSocket pour le chat** au lieu de SSE : permet l'interruption côté serveur (l'utilisateur peut "couper" l'agent qui parle).

### Longue terme

- **Backend de file unifiée** : Redis pub/sub pour partager le blackboard entre plusieurs workers uvicorn (scalabilité horizontale).
- **Observabilité** : OpenTelemetry pour tracer chaque appel agent → LLM → tool. Indispensable quand tu auras 10+ agents.
- **Un dashboard interne** `/admin` qui montre la latence p50/p95/p99 par agent et par modèle, en live.

## ⚠️ Points d'attention

1. **`gemini-flash-latest`, `gemini-pro-latest`** : ces alias sont dépréciés. Préférer la version explicite (`gemini-2.0-flash`, `gemini-2.5-pro`).
2. **TTS server `tts_server4.py`** : non fourni, mais le frontend pointe vers `localhost:8000` — vérifier qu'il tourne.
3. **CORS** : si tu sépares un jour le frontend du backend, ajoute `fastapi.middleware.cors.CORSMiddleware`.
4. **Pas d'auth** : actuellement le serveur écoute sur `0.0.0.0` sans token. À sécuriser si exposé sur un VPS public.
5. **`history` est une variable de classe globale** dans `web_v2.py` → si tu lances plusieurs workers, tu auras des historiques disjoints. Migrer vers Redis si besoin.

## ✅ Checklist de validation après migration

- [ ] `curl http://localhost:8501/health` retourne `{"status":"ok",...}` avec la liste des agents
- [ ] Premier token arrive en moins d'1 seconde dans l'UI
- [ ] La sidebar montre TTFB et tok/s après chaque réponse
- [ ] L'agent actif change dynamiquement selon le query (test : "git status" → GitAgent)
- [ ] Les commandes `!ls -la` streament en temps réel dans le terminal
- [ ] Le toggle Streaming on/off bascule entre les deux modes
- [ ] Pas d'erreur `model not found` dans les logs
