/**
 * JARVIS-V1.0 — Configuration PM2
 *
 * Démarrer tous les services :  pm2 start ecosystem.config.js
 * Activer au boot :              pm2 startup  (puis coller la commande affichée)
 *                                pm2 save
 * Statut :                       pm2 status
 * Logs en temps réel :           pm2 logs
 * Redémarrer un service :        pm2 restart jarvis-backend
 * Arrêter tout :                 pm2 stop all
 */

const path = require('path');
const ROOT = __dirname;

// Détecte le bon python (venv si disponible)
const PYTHON = path.join(ROOT, 'venv', 'bin', 'python');

// Dossier des logs PM2 (centralisé dans Logs/)
const LOG_DIR = path.join(ROOT, 'Logs');

module.exports = {
  apps: [

    // ── 1. Backend principal :8501 ──────────────────────────────
    {
      name: 'jarvis-backend',
      script: PYTHON,
      args: 'main.py --web',
      cwd: ROOT,
      interpreter: 'none',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 3000,
      out_file: path.join(LOG_DIR, 'backend.log'),
      error_file: path.join(LOG_DIR, 'backend.error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      env: {
        PYTHONUNBUFFERED: '1',
      },
    },

    // ── 2. Proxy mobile :3001 ───────────────────────────────────
    {
      name: 'jarvis-mobile',
      script: PYTHON,
      args: 'webmobile.py',
      cwd: ROOT,
      interpreter: 'none',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 3000,
      out_file: path.join(LOG_DIR, 'mobile.log'),
      error_file: path.join(LOG_DIR, 'mobile.error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      env: {
        PYTHONUNBUFFERED: '1',
      },
    },

    // ── 3. TTS Voxtral :8001 (Mistral AI) ──────────────────────
    // Actif seulement si MISTRAL_API_KEY est configurée dans .env
    {
      name: 'jarvis-voxtral',
      script: PYTHON,
      args: 'tts/voxtral_server.py',
      cwd: ROOT,
      interpreter: 'none',
      watch: false,
      autorestart: true,
      max_restarts: 5,
      min_uptime: '10s',
      restart_delay: 5000,
      out_file: path.join(LOG_DIR, 'voxtral.log'),
      error_file: path.join(LOG_DIR, 'voxtral.error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      env: {
        PYTHONUNBUFFERED: '1',
      },
    },

    // ── 4. TTS Kokoro :8000 (optionnel — externe) ───────────────
    // Décommentez ce bloc si ../jarvis-voice/tts_server4.py existe
    // {
    //   name: 'jarvis-kokoro',
    //   script: path.join(ROOT, '..', 'jarvis-voice', 'venv', 'bin', 'python'),
    //   args: path.join(ROOT, '..', 'jarvis-voice', 'tts_server4.py'),
    //   cwd: path.join(ROOT, '..', 'jarvis-voice'),
    //   interpreter: 'none',
    //   watch: false,
    //   autorestart: true,
    //   max_restarts: 5,
    //   min_uptime: '10s',
    //   restart_delay: 5000,
    //   out_file: path.join(LOG_DIR, 'kokoro.log'),
    //   error_file: path.join(LOG_DIR, 'kokoro.error.log'),
    //   log_date_format: 'YYYY-MM-DD HH:mm:ss',
    //   env: { PYTHONUNBUFFERED: '1' },
    // },

  ],
};
