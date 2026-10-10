import json
import os
import re
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from services.rbac import DEFAULT_ADMIN_ACCOUNTS, ROLE_LABELS, generate_admin_identifiers, get_permissions_for_role

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'donnees_locales.db')


# ── Connexion ────────────────────────────────────────────────────────────────

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row):
    d = dict(row)
    raw_perms = d.get('permissions', '[]')
    try:
        d['permissions'] = json.loads(raw_perms) if isinstance(raw_perms, str) else raw_perms
    except (json.JSONDecodeError, TypeError):
        d['permissions'] = []
    # Ne jamais exposer de mot de passe en clair
    d.pop('password', None)
    return d


def _perms_to_json(permissions):
    if isinstance(permissions, list):
        return json.dumps(permissions, ensure_ascii=False)
    return permissions or '[]'


# ── Lookups indexés (O(log n)) ───────────────────────────────────────────────

def get_user_by_login(login_value):
    """Lookup par email, identifiant, apogée ou CIN spécial — utilise les index."""
    login_value = str(login_value or '').strip().lower()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT * FROM users
        WHERE LOWER(email) = ?
           OR LOWER(identifiant) = ?
           OR LOWER(special_apogee) = ?
           OR LOWER(special_cin) = ?
        LIMIT 1
        ''',
        (login_value, login_value, login_value, login_value)
    )
    row = cur.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def get_user_by_identifiant(identifiant):
    """Lookup direct par identifiant (index unique)."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE identifiant = ?', (str(identifiant or '').strip(),))
    row = cur.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def email_exists(email):
    """Vérifie si l'email est déjà pris sans charger tous les utilisateurs."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM users WHERE LOWER(email) = ?', (email.strip().lower(),))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


# ── Écriture ─────────────────────────────────────────────────────────────────

def create_user(user_dict):
    """Insère un nouvel utilisateur. Lève sqlite3.IntegrityError si doublon."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO users (
            identifiant, email, password_hash, cin, prenom, nom, telephone,
            filiere, annee, department, role, role_label, permissions,
            special_apogee, special_cin, status, institution
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''',
        (
            user_dict.get('identifiant', ''),
            user_dict.get('email', '').strip().lower(),
            user_dict.get('password_hash', ''),
            user_dict.get('cin', ''),
            user_dict.get('prenom', ''),
            user_dict.get('nom', ''),
            user_dict.get('telephone', ''),
            user_dict.get('filiere', ''),
            user_dict.get('annee', ''),
            user_dict.get('department', ''),
            user_dict.get('role', 'student'),
            user_dict.get('role_label', ROLE_LABELS.get(user_dict.get('role', 'student'), '')),
            _perms_to_json(user_dict.get('permissions', [])),
            user_dict.get('special_apogee', ''),
            user_dict.get('special_cin', ''),
            user_dict.get('status', 'active'),
            user_dict.get('institution', 'ENSABM'),
        )
    )
    conn.commit()
    conn.close()


_UPDATABLE_FIELDS = {
    'prenom', 'nom', 'email', 'telephone', 'filiere', 'annee', 'cin',
    'role', 'role_label', 'permissions', 'status', 'password_hash',
    'department', 'special_apogee', 'special_cin',
}


def update_user_fields(identifiant, fields):
    """Met à jour des champs précis pour l'utilisateur donné."""
    safe = {k: v for k, v in fields.items() if k in _UPDATABLE_FIELDS}
    if not safe:
        return
    conn = _get_conn()
    cur = conn.cursor()
    for key, value in safe.items():
        if key == 'permissions':
            value = _perms_to_json(value)
        cur.execute(f'UPDATE users SET {key} = ? WHERE identifiant = ?', (value, identifiant))
    conn.commit()
    conn.close()


# ── Listing complet (admin uniquement) ───────────────────────────────────────

def load_users():
    """Retourne tous les utilisateurs — réservé aux vues admin."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users')
    rows = [_row_to_dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# ── Compatibilité ascendante (admin.py update_role) ──────────────────────────

def save_users(users):
    """Upsert groupé — conservé pour la route admin update_role."""
    conn = _get_conn()
    cur = conn.cursor()
    for user in users:
        cur.execute(
            '''
            INSERT INTO users (
                identifiant, email, password_hash, cin, prenom, nom, telephone,
                filiere, annee, department, role, role_label, permissions,
                special_apogee, special_cin, status, institution
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(identifiant) DO UPDATE SET
                email=excluded.email, password_hash=excluded.password_hash,
                cin=excluded.cin, prenom=excluded.prenom, nom=excluded.nom,
                telephone=excluded.telephone, filiere=excluded.filiere,
                annee=excluded.annee, department=excluded.department,
                role=excluded.role, role_label=excluded.role_label,
                permissions=excluded.permissions,
                special_apogee=excluded.special_apogee,
                special_cin=excluded.special_cin,
                status=excluded.status, institution=excluded.institution
            ''',
            (
                user.get('identifiant', ''),
                user.get('email', '').strip().lower(),
                user.get('password_hash', ''),
                user.get('cin', ''),
                user.get('prenom', ''),
                user.get('nom', ''),
                user.get('telephone', ''),
                user.get('filiere', ''),
                user.get('annee', ''),
                user.get('department', ''),
                user.get('role', 'student'),
                user.get('role_label', ''),
                _perms_to_json(user.get('permissions', [])),
                user.get('special_apogee', ''),
                user.get('special_cin', ''),
                user.get('status', 'active'),
                user.get('institution', 'ENSABM'),
            )
        )
    conn.commit()
    conn.close()


def find_user_for_login(login_value, users=None):
    """Délègue au lookup indexé — l'argument `users` est ignoré."""
    return get_user_by_login(login_value)


# ── Comptes administrateurs par défaut ───────────────────────────────────────

def _migrate_legacy_security_admin():
    """Fusionne l'ancien role admin_securite dans admin_it et met à jour le label admin_it."""
    conn = _get_conn()
    cur = conn.cursor()

    # Fusion des anciens comptes admin_securite dans admin_it
    cur.execute("SELECT identifiant FROM users WHERE role = 'admin_securite'")
    legacy_ids = [row[0] for row in cur.fetchall()]
    merged_permissions = get_permissions_for_role('admin_it')
    for identifiant in legacy_ids:
        cur.execute(
            '''
            UPDATE users
            SET role = ?, role_label = ?, permissions = ?, department = ?
            WHERE identifiant = ?
            ''',
            ('admin_it', ROLE_LABELS['admin_it'], _perms_to_json(merged_permissions), 'IT & Sécurité', identifiant)
        )

    # Mise à jour du label pour tous les admin_it existants (renommage Admin IT → Admin IT & Sécurité)
    cur.execute(
        "UPDATE users SET role_label = ? WHERE role = 'admin_it' AND role_label != ?",
        (ROLE_LABELS['admin_it'], ROLE_LABELS['admin_it'])
    )

    conn.commit()
    conn.close()


def _cleanup_legacy_sample_users():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE LOWER(email) = 'strong.user@usms.ac.ma'")
    cur.execute(
        "UPDATE users SET role_label = ? WHERE role = 'student' AND (role_label = '' OR role_label = 'Utilisateur')",
        (ROLE_LABELS['student'],)
    )
    conn.commit()
    conn.close()


def ensure_admin_accounts():
    _migrate_legacy_security_admin()
    _cleanup_legacy_sample_users()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users')
    next_index = cur.fetchone()[0]
    conn.close()

    for admin in DEFAULT_ADMIN_ACCOUNTS:
        if get_user_by_login(admin['email']):
            continue
        identifiers = generate_admin_identifiers(admin['role'], next_index + 1)
        create_user({
            'identifiant': identifiers['special_apogee'],
            'email': admin['email'],
            'password_hash': generate_password_hash('Admin@12345'),
            'prenom': admin['prenom'],
            'nom': admin['nom'],
            'telephone': '',
            'filiere': admin['filiere'],
            'annee': admin['annee'],
            'department': admin['department'],
            'role': admin['role'],
            'role_label': ROLE_LABELS.get(admin['role'], ''),
            'permissions': get_permissions_for_role(admin['role']),
            'special_apogee': identifiers['special_apogee'],
            'special_cin': identifiers['special_cin'],
            'status': 'active',
            'institution': 'ENSABM',
        })
        next_index += 1


# ── Helpers métier ────────────────────────────────────────────────────────────

def sanitize_user(user):
    return {k: v for k, v in user.items() if k not in ('password', 'password_hash')}


def is_admin_role(role):
    return str(role or '') in ('admin_it', 'admin_pedagogique', 'super_admin')


def mask_email(email):
    email = str(email or '').strip().lower()
    if '@' not in email:
        return ''
    local_part, domain = email.split('@', 1)
    if len(local_part) <= 2:
        masked_local = f'{local_part[:1]}*'
    else:
        masked_local = f'{local_part[:2]}{"*" * min(4, len(local_part) - 2)}'
    return f'{masked_local}@{domain}'


def get_profile_payload(user):
    profile = sanitize_user(user)
    if is_admin_role(profile.get('role')):
        profile['telephone'] = ''
        profile['filiere'] = ''
        profile['annee'] = ''
    return profile


def get_admin_directory_entry(user):
    clean = sanitize_user(user)
    role = clean.get('role', 'student')
    is_admin = is_admin_role(role)
    full_name = ' '.join(part for part in [clean.get('prenom', ''), clean.get('nom', '')] if part).strip() or 'Utilisateur'
    return {
        'identifiant': clean.get('identifiant', ''),
        'display_name': full_name,
        'initials': ((clean.get('prenom', '')[:1] + clean.get('nom', '')[:1]).upper() or 'U'),
        'role': role,
        'role_label': clean.get('role_label', ROLE_LABELS.get(role, role)),
        'status': clean.get('status', 'active'),
        'institution': clean.get('institution', 'ENSABM'),
        'department': clean.get('department', ''),
        'email_masked': mask_email(clean.get('email', '')),
        'special_apogee': clean.get('special_apogee', ''),
        'permissions_count': len(clean.get('permissions') or []),
        'is_admin': is_admin,
        'academic_info': '' if is_admin else ' · '.join(
            part for part in [clean.get('filiere', ''), clean.get('annee', '')] if part
        ),
        'scope_summary': {
            'admin_it': 'Infra, comptes, audit et securite operationnelle',
            'admin_pedagogique': 'Qualite pedagogique et reclamations',
            'super_admin': 'Gouvernance globale et acces complet',
        }.get(role, 'Compte etudiant'),
        'privacy_note': 'Historique personnel non visible dans le dashboard admin',
    }


def verify_password(user, password):
    password_hash = user.get('password_hash', '')
    if password_hash:
        return check_password_hash(password_hash, password)
    return False


def validate_password_strength(password, email='', identifiant=''):
    password = str(password or '')
    email = str(email or '').lower()
    identifiant = str(identifiant or '').lower()

    conditions = [
        'Contenir au moins 8 caractères',
        'Inclure au moins une lettre majuscule',
        'Inclure au moins une lettre minuscule',
        'Inclure au moins un chiffre',
        'Inclure au moins un caractère spécial',
    ]

    common_passwords = {
        '12345678', 'password', 'password123', 'azerty123', 'qwerty123',
        '123123123', 'abcdefgh', 'abcd1234', 'admin123', '00000000'
    }

    if len(password) < 8:
        return False, conditions
    if not re.search(r'[A-Z]', password):
        return False, conditions
    if not re.search(r'[a-z]', password):
        return False, conditions
    if not re.search(r'\d', password):
        return False, conditions
    if not re.search(r'[^A-Za-z0-9]', password):
        return False, conditions
    if password.lower() in common_passwords:
        return False, conditions
    if len(set(password)) == 1:
        return False, conditions
    if email and (email.split('@')[0] in password.lower() or email in password.lower()):
        return False, conditions
    if identifiant and identifiant in password.lower():
        return False, conditions

    return True, conditions
