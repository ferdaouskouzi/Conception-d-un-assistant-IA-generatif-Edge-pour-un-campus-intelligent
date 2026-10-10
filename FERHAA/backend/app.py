import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

from flask import Flask, render_template, redirect, request, session, jsonify
from flask_cors import CORS
from services.cache import init_cache
from services.database import get_config, init_db
from services.degrade import warmup_ollama
from services.mail import init_mail
from services.users import ensure_admin_accounts
from routes.ask import ask_bp
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.governance import governance_bp
from routes.reclamations import reclamations_bp
from routes.user_pages import user_pages_bp

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, 'templates'),
    static_folder=os.path.join(FRONTEND_DIR, 'static')
)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(32)
CORS(app)

# Initialisation
init_db()               # crée les tables + migre users.json si nécessaire
init_cache()
init_mail(app)          # configure Flask-Mail (no-op si MAIL_SERVER absent)
ensure_admin_accounts() # insère les comptes admin par défaut si absents
warmup_ollama()         # pré-charge le modèle local en RAM (évite le cold start)

# Blueprints
app.register_blueprint(ask_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(governance_bp)
app.register_blueprint(reclamations_bp)
app.register_blueprint(user_pages_bp)

# ── Middleware maintenance ──────────────────────────────

@app.before_request
def check_maintenance():
    """Bloque les étudiants si le mode maintenance est actif."""
    if request.path.startswith('/api/ask') or request.path == '/ask':
        if get_config('maintenance_mode', 'false') == 'true':
            user = session.get('user', {})
            if user.get('role', 'student') == 'student':
                return jsonify({
                    'erreur': 'FERHAA est temporairement en maintenance. Veuillez réessayer dans quelques minutes.'
                }), 503

# ── Pages ──────────────────────────────────────────────

@app.route('/')
def index():
    if session.get('user'):
        return redirect('/chat')
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/chat')
def chat():
    if not session.get('user'):
        return redirect('/')
    return render_template('chat.html')

# ── API utilitaire ──────────────────────────────────────

@app.route('/api/me')
def me():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'non connecté'}), 401
    return jsonify(user)

# ── UTF-8 charset forcé sur toutes les réponses HTML ────
@app.after_request
def force_utf8_charset(response):
    if response.content_type and 'text/html' in response.content_type:
        response.content_type = 'text/html; charset=utf-8'
    return response

# ── Lancement ───────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
