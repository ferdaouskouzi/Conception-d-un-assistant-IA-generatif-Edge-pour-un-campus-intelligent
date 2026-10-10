"""
Configuration pytest partagée.
Fournit un client Flask de test et des bases SQLite temporaires.
"""
import importlib.util
import os
import sys

import pytest

# ── Chemin du backend ─────────────────────────────────────────────────────────
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Garantir que backend/ est en tête de sys.path pour éviter d'importer
# le app.py prototype à la racine du projet
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _load_flask_app():
    """Charge backend/app.py explicitement pour éviter tout conflit avec le prototype racine."""
    app_path = os.path.join(BACKEND_DIR, 'app.py')
    spec = importlib.util.spec_from_file_location('backend_app', app_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['backend_app'] = module
    spec.loader.exec_module(module)
    return module.app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def _flask_app(tmp_path_factory):
    """
    Application Flask partagée pour toute la session de test.
    Utilise une base SQLite temporaire isolée.
    """
    tmp = tmp_path_factory.mktemp('data')

    os.environ['SECRET_KEY'] = 'test-secret-key'
    os.environ['GROQ_API_KEY'] = 'test-key'
    os.environ.setdefault('OLLAMA_URL', 'http://localhost:11434')
    os.environ.setdefault('OLLAMA_MODEL', 'llama3.2:3b')

    import services.database as db_mod
    import services.cache as cache_mod
    import services.users as users_mod

    db_mod.DB_PATH = str(tmp / 'test.db')
    cache_mod.DB_PATH = str(tmp / 'cache.db')
    users_mod.DB_PATH = str(tmp / 'test.db')

    flask_app = _load_flask_app()
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'

    with flask_app.app_context():
        db_mod.init_db()
        cache_mod.init_cache()
        users_mod.ensure_admin_accounts()

    return flask_app


@pytest.fixture
def app(_flask_app):
    return _flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Client connecté en tant qu'étudiant."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'identifiant': 'test.etudiant',
            'email': 'test@usms.ac.ma',
            'role': 'student',
            'prenom': 'Test',
            'nom': 'Etudiant',
            'filiere': 'INFO',
            'annee': 'CI1',
            'permissions': ['ask_ai', 'view_personal_history', 'submit_feedback', 'view_personal_profile'],
        }
    return client


@pytest.fixture
def admin_client(client):
    """Client connecté en tant qu'admin IT."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'identifiant': 'AIT-APOGEE-001',
            'email': 'admin.it@ensabm.ac.ma',
            'role': 'admin_it',
            'prenom': 'Admin',
            'nom': 'IT',
            'filiere': 'SI',
            'annee': 'STAFF',
            'permissions': ['ask_ai', 'view_admin_dashboard', 'manage_accounts', 'view_audit_logs'],
        }
    return client
