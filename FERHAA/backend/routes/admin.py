import csv
import io
import os

from flask import Blueprint, jsonify, render_template, request, session, Response
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from routes.decorators import login_required, permission_required
from services.course_materials import list_course_materials, save_course_material
from services.database import (
    count_purgeable_logs,
    get_admin_activity,
    get_admin_dashboard_stats,
    get_all_config,
    get_anomalies_off_hours,
    get_anomalies_quota,
    get_anomalies_role_changes,
    get_audit_logs_full,
    get_config,
    get_heatmap_data,
    get_reclamations_all,
    get_reclamations_overdue,
    get_rgpd_blocks_by_pattern,
    get_stats_30days,
    get_stats_by_filiere,
    get_stats_by_source,
    get_stats_hourly_today,
    get_stats_it,
    get_stats_last_7_days,
    get_stats_pedagogique,
    get_stats_securite,
    log_audit,
    purge_old_logs,
    save_feedback,
    set_config,
)
from services.rbac import ROLE_LABELS, get_permissions_for_role
from services.users import (
    create_user,
    get_admin_directory_entry,
    get_user_by_identifiant,
    is_admin_role,
    load_users,
    update_user_fields,
)

admin_bp = Blueprint('admin', __name__)


# ── Page ──────────────────────────────────────────────────────────────────────

@admin_bp.route('/admin')
@permission_required('view_admin_dashboard')
def admin_page():
    return render_template('admin.html')


# ── Dashboard principal ───────────────────────────────────────────────────────

@admin_bp.route('/api/admin/dashboard')
@permission_required('view_admin_dashboard')
def admin_dashboard_api():
    stats, audit_logs, _feedback_rows = get_admin_dashboard_stats()
    users = load_users()
    return jsonify({
        'stats': {
            **stats,
            'user_count': len(users),
            'admin_count': len([u for u in users if u.get('role') != 'student']),
        },
        'users': [get_admin_directory_entry(u) for u in users],
        'audit_logs': audit_logs,
        'roles': ROLE_LABELS,
    })


# ── Stats Admin IT ────────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/stats/it')
@permission_required('view_admin_dashboard')
def stats_it():
    return jsonify(get_stats_it())


@admin_bp.route('/api/admin/stats/hourly')
@permission_required('view_admin_dashboard')
def stats_hourly():
    return jsonify({'hours': get_stats_hourly_today()})


@admin_bp.route('/api/admin/stats/7days')
@permission_required('view_admin_dashboard')
def stats_7days():
    return jsonify({'days': get_stats_last_7_days()})


@admin_bp.route('/api/admin/stats/sources')
@permission_required('view_admin_dashboard')
def stats_sources():
    return jsonify(get_stats_by_source())


# ── Stats Admin Pédagogique ───────────────────────────────────────────────────

@admin_bp.route('/api/admin/stats/pedagogique')
@permission_required('review_academic_content')
def stats_pedagogique():
    return jsonify(get_stats_pedagogique())


@admin_bp.route('/api/admin/course-materials', methods=['GET'])
@permission_required('review_academic_content')
def course_materials_api():
    return jsonify({'items': list_course_materials()})


@admin_bp.route('/api/admin/course-materials', methods=['POST'])
@permission_required('review_academic_content')
def upload_course_material_api():
    current = session.get('user')
    file = request.files.get('file')
    if not file or not secure_filename(file.filename or ''):
        return jsonify({'error': 'Aucun fichier PDF valide fourni.'}), 400

    try:
        material = save_course_material(
            file,
            uploaded_by=current.get('identifiant', ''),
            department=current.get('department', '')
        )
    except ValueError:
        return jsonify({'error': 'Format non supporte. PDF uniquement.'}), 400
    except Exception as exc:
        return jsonify({'error': f'Import impossible: {exc}'}), 500

    log_audit(
        current.get('identifiant', ''),
        current.get('role', 'admin_pedagogique'),
        'upload_course_material',
        target=material.get('filename', 'pdf'),
        details=f"Corpus pedagogique ajoute: {material.get('title', '')}",
        severity='info'
    )
    return jsonify({'success': True, 'item': material}), 201


@admin_bp.route('/api/admin/stats/filiere')
@permission_required('review_academic_content')
def stats_filiere():
    return jsonify({'rows': get_stats_by_filiere()})


# ── Stats Admin Sécurité ──────────────────────────────────────────────────────

@admin_bp.route('/api/admin/stats/securite')
@permission_required('view_audit_logs')
def stats_securite():
    return jsonify(get_stats_securite())


@admin_bp.route('/api/admin/stats/anomalies')
@permission_required('view_audit_logs')
def stats_anomalies():
    off_hour_start = int(get_config('off_hour_start', '7'))
    off_hour_end   = int(get_config('off_hour_end', '20'))
    return jsonify({
        'quota':        get_anomalies_quota(),
        'role_changes': get_anomalies_role_changes(),
        'off_hours':    get_anomalies_off_hours(off_hour_start, off_hour_end),
    })


@admin_bp.route('/api/admin/stats/rgpd-patterns')
@permission_required('view_audit_logs')
def stats_rgpd_patterns():
    return jsonify({'patterns': get_rgpd_blocks_by_pattern()})


@admin_bp.route('/api/admin/stats/heatmap')
@permission_required('view_audit_logs')
def stats_heatmap():
    return jsonify({'heatmap': get_heatmap_data()})


# ── Stats Super Admin ─────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/stats/30days')
@permission_required('full_access')
def stats_30days():
    return jsonify(get_stats_30days())


@admin_bp.route('/api/admin/stats/admin-activity')
@permission_required('full_access')
def stats_admin_activity():
    return jsonify({'activity': get_admin_activity()})


@admin_bp.route('/api/admin/reclamations/overdue')
@permission_required('full_access')
def reclamations_overdue():
    days = int(request.args.get('days', 5))
    return jsonify({'reclamations': get_reclamations_overdue(days)})


# ── Audit export CSV ──────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/audit/export')
@permission_required('view_audit_logs')
def audit_export():
    logs = get_audit_logs_full(limit=1000)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=['user_identifiant', 'action', 'target', 'severity', 'date']
    )
    writer.writeheader()
    writer.writerows(logs)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=audit_ferhaa.csv'}
    )


# ── Gestion des comptes ───────────────────────────────────────────────────────

@admin_bp.route('/api/admin/users')
@permission_required('manage_accounts')
def admin_users_api():
    return jsonify({'items': [get_admin_directory_entry(u) for u in load_users()]})


@admin_bp.route('/api/admin/users', methods=['POST'])
@permission_required('manage_accounts')
def admin_create_user():
    current = session.get('user')
    data = request.get_json(silent=True) or {}
    required = ['email', 'password', 'prenom', 'nom', 'role']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Champs manquants : {", ".join(missing)}'}), 400
    if data['role'] not in ROLE_LABELS:
        return jsonify({'error': 'Rôle invalide'}), 400

    import sqlite3
    role = data['role']
    email = data['email'].strip().lower()
    is_admin = is_admin_role(role)
    # Génère un identifiant unique basé sur l'email (partie locale)
    identifiant = email.split('@')[0][:16].replace('.', '')
    try:
        create_user({
            'identifiant':   identifiant,
            'email':         email,
            'password_hash': generate_password_hash(data['password']),
            'prenom':        data.get('prenom', '').strip(),
            'nom':           data.get('nom', '').strip(),
            'role':          role,
            'role_label':    ROLE_LABELS.get(role, ''),
            'permissions':   get_permissions_for_role(role),
            'filiere':       '' if is_admin else data.get('filiere', '').strip(),
            'annee':         '' if is_admin else data.get('annee', '').strip(),
            'cin':           data.get('cin', '').upper(),
            'telephone':     '',
            'department':    data.get('department', '').strip(),
            'status':        'active',
        })
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email ou identifiant déjà utilisé.'}), 409

    log_audit(
        current.get('identifiant', ''), current.get('role', 'admin'),
        'create_user', target=identifiant,
        details=f"Compte créé avec rôle {data['role']}", severity='warning'
    )
    return jsonify({'success': True, 'identifiant': identifiant}), 201


@admin_bp.route('/api/admin/users/<identifiant>/role', methods=['PUT'])
@permission_required('manage_accounts')
def admin_update_role(identifiant):
    current = session.get('user')
    payload = request.get_json() or {}
    role = payload.get('role', '')
    if role not in ROLE_LABELS:
        return jsonify({'error': 'Rôle invalide'}), 400

    target = get_user_by_identifiant(identifiant)
    if not target:
        return jsonify({'error': 'Utilisateur introuvable'}), 404

    update_user_fields(identifiant, {
        'role': role,
        'role_label': ROLE_LABELS[role],
        'permissions': get_permissions_for_role(role),
    })
    log_audit(
        current.get('identifiant', ''), current.get('role', 'admin'),
        'update_role', target=identifiant,
        details=f'Rôle mis à jour vers {role}', severity='warning'
    )
    return jsonify({'success': True, 'user': get_admin_directory_entry(get_user_by_identifiant(identifiant))})


@admin_bp.route('/api/admin/users/<identifiant>', methods=['PUT'])
@permission_required('manage_accounts')
def admin_update_user(identifiant):
    current = session.get('user')
    payload = request.get_json(silent=True) or {}
    allowed = {'status', 'filiere', 'annee', 'department', 'role', 'role_label', 'telephone'}
    fields = {k: v for k, v in payload.items() if k in allowed}
    if not fields:
        return jsonify({'error': 'Aucun champ valide à mettre à jour'}), 400

    target = get_user_by_identifiant(identifiant)
    if not target:
        return jsonify({'error': 'Utilisateur introuvable'}), 404

    if 'role' in fields:
        fields['role_label'] = ROLE_LABELS.get(fields['role'], fields['role'])
        fields['permissions'] = get_permissions_for_role(fields['role'])
        if is_admin_role(fields['role']):
            fields['filiere'] = ''
            fields['annee'] = ''
            fields['telephone'] = ''

    update_user_fields(identifiant, fields)
    log_audit(
        current.get('identifiant', ''), current.get('role', 'admin'),
        'update_user', target=identifiant,
        details=str(fields), severity='info'
    )
    return jsonify({'success': True})


# ── Config persistante ─────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/config', methods=['GET'])
@permission_required('view_admin_dashboard')
def get_all_config_api():
    return jsonify(get_all_config())


@admin_bp.route('/api/admin/config/<key>', methods=['GET'])
@permission_required('view_admin_dashboard')
def get_config_api(key):
    return jsonify({'key': key, 'value': get_config(key)})


@admin_bp.route('/api/admin/config/<key>', methods=['PUT'])
@permission_required('view_admin_dashboard')
def set_config_api(key):
    current = session.get('user')
    data = request.get_json(silent=True) or {}
    value = str(data.get('value', ''))
    set_config(key, value)
    log_audit(
        current.get('identifiant', ''), current.get('role', 'admin'),
        'config_change', target=key,
        details=f'Valeur : {value}', severity='warning'
    )
    return jsonify({'success': True, 'key': key, 'value': value})


# ── Mode maintenance ───────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/maintenance', methods=['PUT'])
@permission_required('full_access')
def toggle_maintenance():
    current = session.get('user')
    data = request.get_json(silent=True) or {}
    active = str(data.get('active', 'false')).lower()
    set_config('maintenance_mode', active)
    log_audit(
        current.get('identifiant', ''), current.get('role', 'super_admin'),
        'maintenance_mode', target='system',
        details=f'Mode maintenance : {active}', severity='warning'
    )
    return jsonify({'success': True, 'maintenance_mode': active})


# ── Purge des logs ─────────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/logs/purgeable', methods=['GET'])
@permission_required('full_access')
def logs_purgeable():
    days = int(request.args.get('days', 90))
    return jsonify({'count': count_purgeable_logs(days), 'days': days})


@admin_bp.route('/api/admin/logs/purge', methods=['DELETE'])
@permission_required('full_access')
def logs_purge():
    current = session.get('user')
    days = int(request.args.get('days', 90))
    deleted = purge_old_logs(days)
    log_audit(
        current.get('identifiant', ''), current.get('role', 'super_admin'),
        'purge_logs', target='audit_logs',
        details=f'{deleted} lignes supprimées (>{days} jours)', severity='warning'
    )
    return jsonify({'success': True, 'deleted': deleted})


# ── Feedback ──────────────────────────────────────────────────────────────────

@admin_bp.route('/api/feedback', methods=['POST'])
@login_required
def feedback_api():
    user = session.get('user')
    payload = request.get_json() or {}
    rating = payload.get('rating', '').strip()
    if rating not in ('up', 'down'):
        return jsonify({'error': 'rating invalide'}), 400

    save_feedback(
        user.get('identifiant', ''),
        payload.get('question', '').strip(),
        payload.get('response', '').strip(),
        rating,
        payload.get('comment', '').strip()
    )
    log_audit(
        user.get('identifiant', ''), user.get('role', 'student'),
        'submit_feedback', target='ai_response',
        details=f'Feedback {rating}'
    )
    return jsonify({'success': True})
