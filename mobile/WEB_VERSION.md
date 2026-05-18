# 🌐 JARVIS Chat - Version Web

Accès rapide et facile à JARVIS Chat via navigateur web.

## ⚡ Démarrage Rapide

```bash
cd mobile
python3 -m http.server 3000
# Ouvre: http://127.0.0.1:3000/index.html
```

C'est tout! 🎉

## ✨ Features

✅ **Chat en Temps Réel** - Communique avec le backend JARVIS
✅ **Modèles Multiples** - Ollama local + APIs cloud
✅ **Refresh Immédiat** - Appuie F5 pour voir les changements
✅ **UI Moderne** - Design professionnel et fluide
✅ **Responsive** - Fonctionne sur tous les écrans
✅ **Zéro Setup** - Pas de build, pas de compilation

## 🎮 Utilisation

### 1. **Chat Tab**
- Tape un message
- Sélectionne un modèle dans Models tab
- Appuie Entrée ou ➤
- Obtiens une réponse

### 2. **Models Tab**
- Configure l'URL du serveur
- Sélectionne un modèle (Llama3, Gemini, etc.)
- Appuie Test Connection (doit être vert ✅)

### 3. **Settings Tab**
- About info
- Clear chat history

## 🔧 Configuration

### Server URL
Par défaut: `http://127.0.0.1:8501`

Remplace par:
- **Local**: `http://127.0.0.1:8501`
- **Réseau**: `http://192.168.X.X:8501`
- **Remote**: `http://votre-ip.com:8501`

### Modèles Disponibles

**Local (Ollama)**:
- `ollama/llama3` (recommandé)
- `ollama/llama2`
- `ollama/mistral`
- `ollama/neural-chat`

**Cloud APIs**:
- `gemini/gemini-2.0-flash`
- `claude-3-5-sonnet`
- `gpt-4-turbo`

## 🚀 Dev Workflow

### Modifier le Design
1. Ouvre `index.html` dans l'éditeur
2. Modifie le HTML/CSS/JS
3. Sauvegarde
4. Appuie **F5** dans le navigateur
5. C'est live! ⚡

### Exemple: Changer la Couleur
```html
<!-- Ligne 150: Titre -->
<h1>🚀 JARVIS CHAT v2.0</h1>

<!-- Ligne 200: Couleur primaire (CSS) -->
color: #00d4ff;  /* Cyan - change en #ff00ff pour magenta */
```

## 🐛 Troubleshooting

### "Cannot connect to server"
- ✓ Backend tourne: `python interfaces/web_v2.py`
- ✓ URL correcte dans Models tab
- ✓ Status doit être vert ✅

### "Message sent but no response"
- Vérifie que le modèle existe
- Pour Ollama: `ollama list`
- Attends quelques secondes (local peut être lent)

### "Server is slow"
- Local models (Llama) = lent (normal)
- Essaie un modèle API plus rapide (Gemini)
- Ou utilise une machine avec plus de RAM

## 📊 Architecture

```
Browser (Web App)
    ↓
Fetch API
    ↓
JARVIS Backend (FastAPI)
    ↓
Ollama (local) or APIs (cloud)
```

## 💾 Stockage

- Messages sauvegardés localement (en mémoire)
- Efface avec Clear Chat dans Settings
- Pas de serveur de stockage (stateless)

## 🔐 Sécurité

- ✅ CORS enabled
- ✅ IP whitelist (local IPs auto-allowed)
- ✅ No credentials stored in browser
- ✅ API keys in backend only

## 📱 Responsive Design

Fonctionne sur:
- 📱 Mobile (portrait/landscape)
- 💻 Tablet
- 🖥️ Desktop
- 📺 Grand écran

## 🎨 Customization

### Changer les Couleurs
Dans `<style>`:
```css
--primary: #00d4ff;   /* Couleur cyan */
--dark: #1a1a1a;      /* Couleur background sombre */
```

### Ajouter des Modèles
```javascript
const MODELS = {
    'My Category': [
        { id: 'model-id', name: 'Model Name', icon: '🚀' },
    ]
};
```

## 🚀 Déployer en Production

```bash
# 1. Copie index.html sur un serveur web
scp mobile/index.html user@server:/var/www/html/

# 2. Serve avec nginx/apache
# Ou utilise un CDN

# 3. Configure l'URL du backend
# Users entrent l'URL du serveur dans Models tab
```

## 📚 Ressources

- Backend: `interfaces/web_v2.py`
- Mobile App: `mobile/App.tsx`
- Guide Complet: `TWO_VERSIONS.md`
- Debugging: `DEBUGGING_MOBILE.md`

## 🎯 C'est Tout!

La version web est prête à utiliser. Pas de compilateur, pas de build, juste du HTML + JavaScript moderne. 🎉

Profites-en pour développer et tester rapidement!
