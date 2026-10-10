import os
import sqlite3
from typing import Any

from services import cache as cache_service
from services import cloud as cloud_service
from services import database as database_service
from services import degrade as degrade_service
from services.rgpd import PATTERNS_SENSIBLES
from services.rbac import ROLE_LABELS

def _safe_db_value(db_path: str, query: str, default: Any = 0) -> Any:
    if not os.path.exists(db_path):
        return default

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(query)
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else default
    finally:
        conn.close()


def _file_size_kb(path: str) -> int:
    if not os.path.exists(path):
        return 0
    return round(os.path.getsize(path) / 1024)


def build_governance_snapshot() -> dict[str, Any]:
    total_users = _safe_db_value(database_service.DB_PATH, 'SELECT COUNT(*) FROM users')
    admin_users = _safe_db_value(
        database_service.DB_PATH,
        "SELECT COUNT(*) FROM users WHERE role != 'student'"
    )
    cache_entries = _safe_db_value(
        cache_service.DB_PATH,
        'SELECT COUNT(*) FROM cache'
    )
    history_entries = _safe_db_value(
        database_service.DB_PATH,
        'SELECT COUNT(*) FROM historique'
    )
    cloud_answers = _safe_db_value(
        database_service.DB_PATH,
        "SELECT COUNT(*) FROM historique WHERE source = 'cloud_groq'"
    )
    local_answers = _safe_db_value(
        database_service.DB_PATH,
        "SELECT COUNT(*) FROM historique WHERE source IN ('degrade_local', 'degrade_fallback')"
    )
    average_latency = _safe_db_value(
        database_service.DB_PATH,
        'SELECT ROUND(AVG(CASE WHEN temps_cloud > 0 THEN temps_cloud ELSE temps_local END), 2) FROM historique',
        None
    )

    return {
        'app': {
            'name': 'FERHAA',
            'version': '1.1',
            'campus': 'ENSABM',
        },
        'models': {
            'primary': {
                'name': cloud_service.MODEL_NAME,
                'provider': cloud_service.PROVIDER_NAME,
                'mode': 'cloud',
                'configured': bool(os.getenv('GROQ_API_KEY')),
            },
            'fallback': {
                'name': degrade_service.MODEL_NAME,
                'provider': degrade_service.PROVIDER_NAME,
                'mode': 'local',
                'configured': True,
            },
        },
        'storage': {
            'cache_db': {
                'path': cache_service.DB_PATH,
                'size_kb': _file_size_kb(cache_service.DB_PATH),
                'entries': cache_entries,
            },
            'history_db': {
                'path': database_service.DB_PATH,
                'size_kb': _file_size_kb(database_service.DB_PATH),
                'entries': history_entries,
            },
            'users_db': {
                'path': database_service.DB_PATH,
                'size_kb': _file_size_kb(database_service.DB_PATH),
                'entries': total_users,
            },
        },
        'traffic': {
            'cloud_answers': cloud_answers,
            'local_answers': local_answers,
            'average_latency_seconds': average_latency or 0,
            'cache_entries': cache_entries,
        },
        'privacy': {
            'rgpd_guard_patterns': len(PATTERNS_SENSIBLES),
            'sensitive_fields_stored_locally': [
                'identifiant',
                'cin',
                'prenom',
                'nom',
                'email',
                'telephone',
                'filiere',
                'annee',
            ],
            'sent_to_model_fields': [
                'question',
                'prenom',
                'filiere',
                'annee',
            ],
            'never_shared_fields': [
                'identifiant',
                'cin',
                'email',
                'telephone',
                'password',
            ],
            'tracking_enabled': False,
            'third_party_sale': False,
        },
        'roles': {
            'available_roles': ROLE_LABELS,
            'admin_users': admin_users,
            'standard_users': total_users - admin_users,
        },
    }
