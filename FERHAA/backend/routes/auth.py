import re

from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash

from services.database import log_audit
from services.rbac import ROLE_LABELS, get_permissions_for_role
from services.users import (
    create_user,
    email_exists,
    get_profile_payload,
    get_user_by_identifiant,
    get_user_by_login,
    is_admin_role,
    sanitize_user,
    update_user_fields,
    validate_password_strength,
    verify_password,
)

auth_bp = Blueprint('auth', __name__)

CIN_REGEX = re.compile(r'^[A-Za-z]{1,2}\d{6}$')


@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    login_value = data.get('identifiant', '').strip()  # identifiant : strip OK
    password = data.get('password', '')                 # password : pas de strip — un espace fait partie du mot de passe

    # Lookup indexé O(log n) — ne charge plus tous les utilisateurs
    user = get_user_by_login(login_value)
    if user and verify_password(user, password):
        session['user'] = sanitize_user(user)
        log_audit(
            session['user'].get('identifiant', ''),
            session['user'].get('role', 'student'),
            'login',
            target='session',
            details='Connexion reussie'
        )
        return jsonify({'success': True, 'user': session['user']})

    return jsonify({'success': False, 'message': 'Email institutionnel ou mot de passe incorrect'}), 401


@auth_bp.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    required = ['email', 'password', 'prenom', 'nom', 'identifiant', 'cin']
    for field in required:
        if not data.get(field, '').strip():
            return jsonify({'success': False, 'message': f'Champ obligatoire manquant : {field}'}), 400

    email = data['email'].strip().lower()
    if not email.endswith('@usms.ac.ma'):
        return jsonify({'success': False, 'message': 'Utilisez un email institutionnel de la forme prenom.nom@usms.ac.ma.'}), 400

    cin = data.get('cin', '').strip().upper()
    if not CIN_REGEX.match(cin):
        return jsonify({'success': False, 'message': 'Format CIN invalide (ex: AB123456 ou K123456)'}), 400

    identifiant = data.get('identifiant', '').strip()
    password = data['password']  # pas de strip — préserver les espaces intentionnels
    is_strong, conditions = validate_password_strength(password, email=email, identifiant=identifiant)
    if not is_strong:
        return jsonify({
            'success': False,
            'message': "mot de passe n'est pas fort",
            'conditions': conditions,
        }), 400

    # Vérification d'unicité sans charger tous les utilisateurs
    if email_exists(email):
        return jsonify({'success': False, 'message': 'Cet email institutionnel est deja utilise'}), 400

    create_user({
        'identifiant': identifiant,
        'email': email,
        'password': '',
        'password_hash': generate_password_hash(password),
        'cin': cin,
        'prenom': data['prenom'].strip(),
        'nom': data['nom'].strip(),
        'telephone': data.get('telephone', '').strip(),
        'filiere': data.get('filiere', '').strip(),
        'annee': data.get('annee', '').strip(),
        'role': 'student',
        'role_label': ROLE_LABELS['student'],
        'permissions': get_permissions_for_role('student'),
        'department': '',
        'special_apogee': '',
        'special_cin': '',
        'status': 'active',
        'institution': 'ENSABM',
    })
    log_audit(
        identifiant,
        'student',
        'register',
        target='account',
        details='Creation de compte etudiant'
    )
    return jsonify({'success': True})


@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    user = session.get('user')
    if user:
        log_audit(
            user.get('identifiant', ''),
            user.get('role', 'student'),
            'logout',
            target='session',
            details='Deconnexion utilisateur'
        )
    session.clear()
    return jsonify({'success': True})


@auth_bp.route('/api/profile', methods=['GET'])
def get_profile():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'non connecte'}), 401
    return jsonify(get_profile_payload(user))


@auth_bp.route('/api/profile/password', methods=['PUT'])
def change_password():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'non connecte'}), 401

    data = request.get_json() or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Champs obligatoires manquants'}), 400

    current = get_user_by_identifiant(user.get('identifiant'))
    if not current:
        return jsonify({'success': False, 'message': 'Utilisateur introuvable'}), 404

    if not verify_password(current, current_password):
        return jsonify({'success': False, 'message': 'Mot de passe actuel incorrect'}), 400

    is_strong, conditions = validate_password_strength(
        new_password,
        email=current.get('email', ''),
        identifiant=current.get('identifiant', '')
    )
    if not is_strong:
        return jsonify({'success': False, 'message': 'Nouveau mot de passe trop faible', 'conditions': conditions}), 400

    update_user_fields(user.get('identifiant'), {'password_hash': generate_password_hash(new_password)})
    log_audit(
        user.get('identifiant', ''),
        user.get('role', 'student'),
        'change_password',
        target='profile',
        details='Changement de mot de passe'
    )
    return jsonify({'success': True, 'message': 'Mot de passe modifie avec succes'})


@auth_bp.route('/api/profile', methods=['PUT'])
def update_profile():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'non connecte'}), 401

    data = request.get_json() or {}
    identifiant = user.get('identifiant')

    # Lookup direct sans charger toute la table
    current = get_user_by_identifiant(identifiant)
    if not current:
        return jsonify({'success': False, 'message': 'Utilisateur introuvable'}), 404

    editable = {}
    for field in ['prenom', 'nom', 'email', 'telephone', 'filiere', 'annee', 'cin']:
        if field not in data:
            continue
        if is_admin_role(current.get('role')) and field in {'telephone', 'filiere', 'annee'}:
            continue
        if field == 'email':
            editable[field] = str(data[field]).strip().lower()
        elif field == 'cin':
            editable[field] = str(data[field]).strip().upper()
        else:
            editable[field] = str(data[field]).strip()

    update_user_fields(identifiant, editable)

    updated = get_user_by_identifiant(identifiant)
    session['user'] = get_profile_payload(updated)
    log_audit(
        identifiant,
        user.get('role', 'student'),
        'update_profile',
        target='profile',
        details='Mise a jour du profil utilisateur'
    )
    return jsonify({'success': True, 'user': session['user']})
