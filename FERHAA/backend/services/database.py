import json
import os
import sqlite3
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'donnees_locales.db')
USERS_JSON = os.path.join(os.path.dirname(__file__), '..', 'data', 'users.json')


def _get_connection():
    return sqlite3.connect(DB_PATH)


def _migrate_json_users(cur):
    """Import users.json into the users table (runs once when the table is empty)."""
    try:
        with open(USERS_JSON, 'r', encoding='utf-8') as f:
            raw_users = json.load(f)
        if not isinstance(raw_users, list):
            return
        for user in raw_users:
            perms = user.get('permissions', [])
            cur.execute(
                '''
                INSERT OR IGNORE INTO users (
                    identifiant, email, password_hash, cin, prenom, nom,
                    telephone, filiere, annee, department, role, role_label,
                    permissions, special_apogee, special_cin, status, institution
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''',
                (
                    str(user.get('identifiant', '') or user.get('email', '')).strip(),
                    str(user.get('email', '')).strip().lower(),
                    user.get('password_hash', ''),
                    str(user.get('cin', '')).strip().upper(),
                    str(user.get('prenom', '')).strip(),
                    str(user.get('nom', '')).strip(),
                    str(user.get('telephone', '')).strip(),
                    str(user.get('filiere', '')).strip(),
                    str(user.get('annee', '')).strip(),
                    str(user.get('department', '')).strip(),
                    user.get('role', 'student'),
                    user.get('role_label', ''),
                    json.dumps(perms, ensure_ascii=False) if isinstance(perms, list) else (perms or '[]'),
                    user.get('special_apogee', ''),
                    user.get('special_cin', ''),
                    user.get('status', 'active'),
                    user.get('institution', 'ENSABM'),
                )
            )
        print(f"[migration] {len(raw_users)} utilisateurs importés depuis users.json vers SQLite.")
    except Exception as e:
        print(f"[migration] Erreur lors de l'import users.json : {e}")


def init_db():
    conn = _get_connection()
    cur = conn.cursor()

    # ── Table users ────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            identifiant     TEXT    NOT NULL,
            email           TEXT    NOT NULL,
            password_hash   TEXT    NOT NULL DEFAULT '',
            cin             TEXT    DEFAULT '',
            prenom          TEXT    DEFAULT '',
            nom             TEXT    DEFAULT '',
            telephone       TEXT    DEFAULT '',
            filiere         TEXT    DEFAULT '',
            annee           TEXT    DEFAULT '',
            department      TEXT    DEFAULT '',
            role            TEXT    DEFAULT 'student',
            role_label      TEXT    DEFAULT '',
            permissions     TEXT    DEFAULT '[]',
            special_apogee  TEXT    DEFAULT '',
            special_cin     TEXT    DEFAULT '',
            status          TEXT    DEFAULT 'active',
            institution     TEXT    DEFAULT 'ENSABM'
        )
    ''')

    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_identifiant ON users(identifiant)')
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(LOWER(email))')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_users_special_apogee ON users(special_apogee)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_users_special_cin ON users(special_cin)')

    # ── Migration JSON → SQLite (one-shot) ─────────────────────────────────
    cur.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] == 0 and os.path.exists(USERS_JSON):
        _migrate_json_users(cur)

    # ── Table historique ────────────────────────────────────────────────────
    cur.execute('''CREATE TABLE IF NOT EXISTS historique (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_identifiant TEXT,
        question TEXT,
        rep_cloud TEXT,
        rep_locale TEXT,
        temps_cloud REAL,
        temps_local REAL,
        source TEXT,
        date TEXT)''')

    cur.execute("PRAGMA table_info(historique)")
    columns = [row[1] for row in cur.fetchall()]
    if 'user_identifiant' not in columns:
        cur.execute('ALTER TABLE historique ADD COLUMN user_identifiant TEXT')

    # ── Table audit_logs ────────────────────────────────────────────────────
    cur.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_identifiant TEXT,
        user_role TEXT,
        action TEXT,
        target TEXT,
        details TEXT,
        severity TEXT,
        date TEXT)''')

    # ── Table feedback ──────────────────────────────────────────────────────
    cur.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_identifiant TEXT,
        question TEXT,
        response TEXT,
        rating TEXT,
        comment TEXT,
        date TEXT)''')

    # ── Table reclamations (migration si ancien schéma détecté) ────────────
    cur.execute("PRAGMA table_info(reclamations)")
    rec_cols = [row[1] for row in cur.fetchall()]
    if rec_cols and 'source_ia' not in rec_cols:
        # Ancien schéma (< v2) : on recrée proprement (données de dev uniquement)
        cur.execute('DROP TABLE reclamations')
        rec_cols = []

    cur.execute('''CREATE TABLE IF NOT EXISTS reclamations (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_identifiant TEXT NOT NULL DEFAULT '',
        reponse_ia       TEXT NOT NULL DEFAULT '',
        source_ia        TEXT          DEFAULT '',
        description      TEXT NOT NULL DEFAULT '',
        statut           TEXT          DEFAULT 'ouvert',
        admin_assigned   TEXT          DEFAULT 'admin_pedagogique',
        reponse_admin    TEXT          DEFAULT '',
        decision_admin   TEXT          DEFAULT '',
        improvement_needed INTEGER     DEFAULT 0,
        reviewed_by      TEXT          DEFAULT '',
        reviewed_at      TEXT          DEFAULT '',
        date_creation    TEXT NOT NULL DEFAULT '',
        date_resolution  TEXT          DEFAULT ''
    )''')

    cur.execute('CREATE INDEX IF NOT EXISTS idx_rec_statut ON reclamations(statut)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_rec_admin  ON reclamations(admin_assigned)')
    cur.execute("PRAGMA table_info(reclamations)")
    rec_cols = [row[1] for row in cur.fetchall()]
    if 'decision_admin' not in rec_cols:
        cur.execute("ALTER TABLE reclamations ADD COLUMN decision_admin TEXT DEFAULT ''")
    if 'improvement_needed' not in rec_cols:
        cur.execute("ALTER TABLE reclamations ADD COLUMN improvement_needed INTEGER DEFAULT 0")
    if 'reviewed_by' not in rec_cols:
        cur.execute("ALTER TABLE reclamations ADD COLUMN reviewed_by TEXT DEFAULT ''")
    if 'reviewed_at' not in rec_cols:
        cur.execute("ALTER TABLE reclamations ADD COLUMN reviewed_at TEXT DEFAULT ''")

    # ── Table corpus pédagogique ───────────────────────────────────────────
    cur.execute('''CREATE TABLE IF NOT EXISTS course_materials (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL DEFAULT '',
        filename    TEXT NOT NULL DEFAULT '',
        stored_name TEXT NOT NULL DEFAULT '',
        file_path   TEXT NOT NULL DEFAULT '',
        mime_type   TEXT NOT NULL DEFAULT 'application/pdf',
        sha256      TEXT NOT NULL DEFAULT '',
        uploaded_by TEXT NOT NULL DEFAULT '',
        department  TEXT NOT NULL DEFAULT '',
        page_count  INTEGER DEFAULT 0,
        text_excerpt TEXT DEFAULT '',
        content_text TEXT DEFAULT '',
        status      TEXT NOT NULL DEFAULT 'ready',
        uploaded_at TEXT NOT NULL DEFAULT ''
    )''')

    # ── Table config (clé/valeur persistante) ──────────────────────────────
    cur.execute('''CREATE TABLE IF NOT EXISTS config (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT '',
        date  TEXT          DEFAULT ''
    )''')

    conn.commit()
    conn.close()


# ── Config ────────────────────────────────────────────────────────────────────

def get_config(key: str, default: str = '') -> str:
    conn = _get_connection()
    cur = conn.cursor()
    row = cur.execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_config(key: str, value: str):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT OR REPLACE INTO config (key, value, date) VALUES (?,?,?)',
        (key, value, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()


def get_all_config() -> dict:
    conn = _get_connection()
    cur = conn.cursor()
    rows = cur.execute('SELECT key, value FROM config').fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


# ── Réclamations ──────────────────────────────────────────────────────────────

def create_reclamation(user_identifiant: str, reponse_ia: str, source_ia: str,
                       description: str) -> int:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''INSERT INTO reclamations
           (user_identifiant, reponse_ia, source_ia, description, statut,
            admin_assigned, date_creation)
           VALUES (?,?,?,?,?,?,?)''',
        (user_identifiant, reponse_ia, source_ia, description, 'ouvert',
         'admin_pedagogique', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    rec_id = cur.lastrowid
    conn.commit()
    conn.close()
    return rec_id


def get_reclamations_user(user_identifiant: str) -> list:
    """Réclamations de l'étudiant connecté — ne retourne jamais celles d'un autre."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        '''SELECT id, source_ia, description, statut, reponse_admin,
                  decision_admin, improvement_needed, reviewed_by, reviewed_at,
                  date_creation, date_resolution
           FROM reclamations
           WHERE user_identifiant = ?
           ORDER BY id DESC''',
        (user_identifiant,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_reclamations_pedagogique(statut: str = None) -> list:
    """Réclamations pour l'admin pédagogique — sans user_identifiant (RGPD)."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if statut:
        cur.execute(
            '''SELECT r.id, r.source_ia, r.description, r.reponse_ia, r.statut,
                      r.reponse_admin, r.decision_admin, r.improvement_needed,
                      r.reviewed_by, r.reviewed_at, r.date_creation, r.date_resolution,
                      u.filiere
               FROM reclamations r
               LEFT JOIN users u ON u.identifiant = r.user_identifiant
               WHERE r.admin_assigned = 'admin_pedagogique' AND r.statut = ?
               ORDER BY r.id DESC''',
            (statut,)
        )
    else:
        cur.execute(
            '''SELECT r.id, r.source_ia, r.description, r.reponse_ia, r.statut,
                      r.reponse_admin, r.decision_admin, r.improvement_needed,
                      r.reviewed_by, r.reviewed_at, r.date_creation, r.date_resolution,
                      u.filiere
               FROM reclamations r
               LEFT JOIN users u ON u.identifiant = r.user_identifiant
               WHERE r.admin_assigned = 'admin_pedagogique'
               ORDER BY r.id DESC LIMIT 100'''
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_reclamations_all() -> list:
    """Toutes les réclamations (super admin) avec filière mais sans identifiant."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        '''SELECT r.id, r.source_ia, r.description, r.reponse_ia, r.statut,
                  r.admin_assigned, r.reponse_admin, r.decision_admin,
                  r.improvement_needed, r.reviewed_by, r.reviewed_at,
                  r.date_creation, r.date_resolution,
                  u.filiere
           FROM reclamations r
           LEFT JOIN users u ON u.identifiant = r.user_identifiant
           ORDER BY r.id DESC LIMIT 200'''
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def resolve_reclamation(
    rec_id: int,
    reponse_admin: str,
    decision_admin: str = '',
    improvement_needed: bool = False,
    reviewed_by: str = ''
):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''UPDATE reclamations
           SET statut='resolu', reponse_admin=?, decision_admin=?, improvement_needed=?,
               reviewed_by=?, reviewed_at=?, date_resolution=?
           WHERE id=?''',
        (
            reponse_admin,
            decision_admin,
            1 if improvement_needed else 0,
            reviewed_by,
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            rec_id
        )
    )
    conn.commit()
    conn.close()


def reassign_reclamation(rec_id: int, admin_assigned: str):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        'UPDATE reclamations SET admin_assigned=? WHERE id=?',
        (admin_assigned, rec_id)
    )
    conn.commit()
    conn.close()


def get_reclamation_by_id(rec_id: int) -> dict | None:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM reclamations WHERE id=?', (rec_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ── Statistiques — Admin IT ───────────────────────────────────────────────────

def get_stats_it() -> dict:
    """Métriques pour l'admin IT."""
    conn = _get_connection()
    cur = conn.cursor()
    total = cur.execute('SELECT COUNT(*) FROM historique').fetchone()[0]
    cloud = cur.execute("SELECT COUNT(*) FROM historique WHERE source='cloud_groq'").fetchone()[0]
    edge  = cur.execute("SELECT COUNT(*) FROM historique WHERE source IN ('degrade_local','degrade_fallback')").fetchone()[0]
    cache = cur.execute("SELECT COUNT(*) FROM audit_logs WHERE action='cache_hit'").fetchone()[0]
    ask   = cur.execute("SELECT COUNT(*) FROM audit_logs WHERE action='ask_ai'").fetchone()[0]
    active = cur.execute("SELECT COUNT(*) FROM users WHERE status='active'").fetchone()[0]
    admins = cur.execute("SELECT COUNT(*) FROM users WHERE status='active' AND role != 'student'").fetchone()[0]
    students = active - admins
    conn.close()
    return {
        'total': total,
        'cloud': cloud,
        'edge': edge,
        'cache_hits': cache,
        'ask_total': ask,
        'cache_rate': round(cache / ask * 100, 1) if ask > 0 else None,
        'active_users': active,
        'admin_count': admins,
        'student_count': students,
    }


def get_stats_hourly_today() -> list:
    """Volume de requêtes par heure aujourd'hui."""
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT strftime('%H', date) as heure, COUNT(*) as nb
           FROM audit_logs
           WHERE action = 'ask_ai' AND date >= date('now')
           GROUP BY heure ORDER BY heure"""
    )
    rows = [{'heure': row[0], 'nb': row[1]} for row in cur.fetchall()]
    conn.close()
    return rows


def get_audit_logs_full(limit: int = 50) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        '''SELECT user_identifiant, action, target, severity, date
           FROM audit_logs ORDER BY id DESC LIMIT ?''',
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Statistiques — Admin Pédagogique ─────────────────────────────────────────

def get_stats_pedagogique() -> dict:
    conn = _get_connection()
    cur = conn.cursor()
    total  = cur.execute('SELECT COUNT(*) FROM historique').fetchone()[0]
    pos    = cur.execute("SELECT COUNT(*) FROM feedback WHERE rating='up'").fetchone()[0]
    neg    = cur.execute("SELECT COUNT(*) FROM feedback WHERE rating='down'").fetchone()[0]
    course_materials = cur.execute("SELECT COUNT(*) FROM course_materials").fetchone()[0]
    rec_open = cur.execute(
        "SELECT COUNT(*) FROM reclamations WHERE statut='ouvert' AND admin_assigned='admin_pedagogique'"
    ).fetchone()[0]
    filieres = [r[0] for r in cur.execute(
        "SELECT DISTINCT filiere FROM users WHERE role='student' AND filiere != ''"
    ).fetchall()]
    conn.close()
    quality = round(pos / (pos + neg) * 100, 1) if (pos + neg) > 0 else None
    return {
        'total': total,
        'feedback_pos': pos,
        'feedback_neg': neg,
        'quality_score': quality,
        'rec_open': rec_open,
        'course_materials': course_materials,
        'filieres': filieres,
        'evaluated': pos + neg,
        'non_evaluated': max(0, total - (pos + neg)),
    }


def get_stats_by_filiere() -> list:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''SELECT u.filiere, h.source, COUNT(*) as nb
           FROM historique h
           JOIN users u ON h.user_identifiant = u.identifiant
           WHERE u.filiere != ''
           GROUP BY u.filiere, h.source
           ORDER BY nb DESC'''
    )
    rows = [{'filiere': r[0], 'source': r[1], 'nb': r[2]} for r in cur.fetchall()]
    conn.close()
    return rows


# ── Statistiques — Admin Sécurité ─────────────────────────────────────────────

def get_stats_securite() -> dict:
    conn = _get_connection()
    cur = conn.cursor()
    today = datetime.date.today().strftime('%Y-%m-%d')
    rgpd_today = cur.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE action='rgpd_block' AND date >= ?", (today,)
    ).fetchone()[0]
    anomalies = cur.execute(
        """SELECT COUNT(*) FROM audit_logs
           WHERE severity IN ('critical','warning')
           AND date >= datetime('now','-24 hours')"""
    ).fetchone()[0]
    suspended = cur.execute(
        "SELECT COUNT(*) FROM users WHERE status='inactive'"
    ).fetchone()[0]
    total_logs = cur.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
    conn.close()
    return {
        'rgpd_today': rgpd_today,
        'anomalies_24h': anomalies,
        'suspended_accounts': suspended,
        'total_logs': total_logs,
    }


def get_anomalies_quota() -> list:
    conn = _get_connection()
    cur = conn.cursor()
    today = datetime.date.today().strftime('%Y-%m-%d')
    cur.execute(
        """SELECT user_identifiant, COUNT(*) as nb
           FROM audit_logs WHERE action='quota_exceeded' AND date >= ?
           GROUP BY user_identifiant""",
        (today,)
    )
    rows = [{'user_identifiant': r[0], 'nb': r[1]} for r in cur.fetchall()]
    conn.close()
    return rows


def get_anomalies_role_changes() -> list:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT user_identifiant, target, details, date
           FROM audit_logs WHERE action='update_role'
           AND date >= datetime('now','-24 hours')
           ORDER BY id DESC"""
    )
    rows = [{'by': r[0], 'target': r[1], 'details': r[2], 'date': r[3]}
            for r in cur.fetchall()]
    conn.close()
    return rows


def get_anomalies_off_hours(hour_start: int = 7, hour_end: int = 20) -> list:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        f"""SELECT user_identifiant, date
            FROM audit_logs
            WHERE action='login'
            AND (CAST(strftime('%H', date) AS INTEGER) < {hour_start}
                 OR CAST(strftime('%H', date) AS INTEGER) >= {hour_end})
            AND date >= datetime('now','-24 hours')
            ORDER BY id DESC"""
    )
    rows = [{'user_identifiant': r[0], 'date': r[1]} for r in cur.fetchall()]
    conn.close()
    return rows


def get_rgpd_blocks_by_pattern() -> list:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT target, COUNT(*) as nb FROM audit_logs
           WHERE action='rgpd_block'
           GROUP BY target ORDER BY nb DESC"""
    )
    rows = [{'pattern': r[0], 'nb': r[1]} for r in cur.fetchall()]
    conn.close()
    return rows


def get_heatmap_data() -> list:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT strftime('%w', date) as jour, strftime('%H', date) as heure, COUNT(*) as nb
           FROM audit_logs WHERE action='ask_ai'
           AND date >= datetime('now','-7 days')
           GROUP BY jour, heure"""
    )
    rows = [{'jour': r[0], 'heure': r[1], 'nb': r[2]} for r in cur.fetchall()]
    conn.close()
    return rows


# ── Statistiques — Super Admin ────────────────────────────────────────────────

def get_stats_30days() -> dict:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT source, COUNT(*) as nb FROM historique
           WHERE date >= datetime('now','-30 days')
           GROUP BY source ORDER BY nb DESC"""
    )
    sources = {r[0]: r[1] for r in cur.fetchall()}
    total_30 = sum(sources.values())
    conn.close()
    return {'sources': sources, 'total': total_30}


def get_admin_activity() -> list:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT user_identifiant, COUNT(*) as nb_actions
           FROM audit_logs
           WHERE user_role != 'student'
           AND date >= datetime('now','-30 days')
           GROUP BY user_identifiant
           ORDER BY nb_actions DESC"""
    )
    rows = [{'identifiant': r[0], 'nb_actions': r[1]} for r in cur.fetchall()]
    conn.close()
    return rows


def get_reclamations_overdue(days: int = 5) -> list:
    """Réclamations non résolues depuis plus de N jours."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        f"""SELECT r.id, r.source_ia, r.statut, r.admin_assigned, r.date_creation, u.filiere
            FROM reclamations r
            LEFT JOIN users u ON u.identifiant = r.user_identifiant
            WHERE r.statut != 'resolu'
            AND r.date_creation <= datetime('now', '-{days} days')
            ORDER BY r.date_creation ASC"""
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def purge_old_logs(days: int = 90) -> int:
    """Supprime les logs d'audit de plus de N jours. Retourne le nombre de lignes supprimées."""
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM audit_logs WHERE date < datetime('now', '-{days} days')"
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def count_purgeable_logs(days: int = 90) -> int:
    conn = _get_connection()
    cur = conn.cursor()
    n = cur.execute(
        f"SELECT COUNT(*) FROM audit_logs WHERE date < datetime('now', '-{days} days')"
    ).fetchone()[0]
    conn.close()
    return n


# ── Statistiques communes ────────────────────────────────────────────────────

def get_stats_by_source() -> dict:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''SELECT source, COUNT(*) as cnt FROM historique
           WHERE source IS NOT NULL GROUP BY source ORDER BY cnt DESC'''
    )
    rows = {row[0]: row[1] for row in cur.fetchall()}
    total = sum(rows.values()) or 1
    conn.close()
    return {'sources': rows, 'total': total}


def get_stats_last_7_days() -> list:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''SELECT DATE(date) as jour, COUNT(*) as cnt
           FROM historique
           WHERE date >= DATE('now', '-6 days')
           GROUP BY jour ORDER BY jour ASC'''
    )
    rows = [{'date': row[0], 'count': row[1]} for row in cur.fetchall()]
    conn.close()
    return rows


# ── Historique ────────────────────────────────────────────────────────────────

def sauvegarder(question, rc, rl, tc, tl, source, user_identifiant=''):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''INSERT INTO historique (
            user_identifiant, question, rep_cloud, rep_locale,
            temps_cloud, temps_local, source, date
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_identifiant, question, rc, rl, tc, tl, source,
         datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()


def get_history_for_user(user_identifiant, limit=50):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        '''SELECT id, question, rep_cloud, rep_locale, temps_cloud, temps_local, source, date
           FROM historique WHERE user_identifiant = ?
           ORDER BY id DESC LIMIT ?''',
        (user_identifiant, limit)
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def delete_history_item(user_identifiant, item_id):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''DELETE FROM historique WHERE id = ?
             AND (user_identifiant = ? OR user_identifiant IS NULL OR user_identifiant = '')''',
        (item_id, user_identifiant)
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


def delete_all_history_for_user(user_identifiant):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM historique WHERE user_identifiant = ?', (user_identifiant,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def get_full_history_for_export(user_identifiant):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        '''SELECT id, question, rep_cloud, rep_locale, source, date
           FROM historique WHERE user_identifiant = ?
           ORDER BY id DESC''',
        (user_identifiant,)
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# ── Audit ─────────────────────────────────────────────────────────────────────

def log_audit(user_identifiant, user_role, action, target='', details='', severity='info'):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''INSERT INTO audit_logs (
            user_identifiant, user_role, action, target, details, severity, date
           ) VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user_identifiant, user_role, action, target, details, severity,
         datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()


# ── Feedback ──────────────────────────────────────────────────────────────────

def save_feedback(user_identifiant, question, response, rating, comment=''):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''INSERT INTO feedback (user_identifiant, question, response, rating, comment, date)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (user_identifiant, question, response, rating, comment,
         datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()


# ── Quota ─────────────────────────────────────────────────────────────────────

DAILY_QUESTION_LIMIT = 50


def count_questions_today(user_identifiant: str) -> int:
    today = datetime.date.today().strftime('%Y-%m-%d')
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM historique WHERE user_identifiant = ? AND date LIKE ?",
        (user_identifiant, today + '%')
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


# ── Dashboard admin générique ─────────────────────────────────────────────────

def get_admin_dashboard_stats():
    conn = _get_connection()
    cur = conn.cursor()
    stats = {
        'history_count':  cur.execute('SELECT COUNT(*) FROM historique').fetchone()[0],
        'cloud_count':    cur.execute("SELECT COUNT(*) FROM historique WHERE source='cloud_groq'").fetchone()[0],
        'degraded_count': cur.execute("SELECT COUNT(*) FROM historique WHERE source IN ('degrade_local','degrade_fallback','fallback_predefined','cache_local')").fetchone()[0],
        'audit_count':    cur.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0],
        'feedback_count': cur.execute('SELECT COUNT(*) FROM feedback').fetchone()[0],
    }
    cur.execute(
        '''SELECT user_identifiant, user_role, action, target, details, severity, date
           FROM audit_logs ORDER BY id DESC LIMIT 20'''
    )
    audit_rows = [
        {'user_identifiant': r[0], 'user_role': r[1], 'action': r[2],
         'target': r[3], 'details': r[4], 'severity': r[5], 'date': r[6]}
        for r in cur.fetchall()
    ]
    cur.execute(
        'SELECT user_identifiant, rating, comment, date FROM feedback ORDER BY id DESC LIMIT 20'
    )
    feedback_rows = [
        {'user_identifiant': r[0], 'rating': r[1], 'comment': r[2], 'date': r[3]}
        for r in cur.fetchall()
    ]
    conn.close()
    return stats, audit_rows, feedback_rows
