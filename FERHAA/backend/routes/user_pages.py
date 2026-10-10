from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session

from routes.decorators import login_required
from services.conversations import (
    delete_all_conversations,
    delete_conversation,
    delete_error_conversations,
    get_log_files_for_user,
    is_conversation_usable,
    load_conversations,
    sync_conversations,
)
from services.database import (
    delete_all_history_for_user,
    delete_history_item,
    get_full_history_for_export,
    get_history_for_user,
)
from services.users import is_admin_role

user_pages_bp = Blueprint('user_pages', __name__)


def _history_allowed():
    user = session.get('user') or {}
    return not is_admin_role(user.get('role'))


@user_pages_bp.route('/historique')
@login_required
def history_page():
    if not _history_allowed():
        return redirect('/admin')
    return render_template('historique.html')


@user_pages_bp.route('/profile')
@login_required
def profile_page():
    return render_template('profile.html')


@user_pages_bp.route('/api/historique')
@login_required
def history_api():
    if not _history_allowed():
        return jsonify({'error': 'historique indisponible pour les administrateurs'}), 403
    user = session.get('user')
    user_identifiant = user.get('identifiant', '')
    history = get_history_for_user(user_identifiant)
    conversations = load_conversations(user_identifiant)
    return jsonify({
        'items': history,
        'count': len(history),
        'conversations': conversations,
        'conversation_count': len(conversations),
        'usable_conversation_count': sum(1 for item in conversations if is_conversation_usable(item)),
        'logs': get_log_files_for_user(user_identifiant),
    })


@user_pages_bp.route('/api/conversations', methods=['GET'])
@login_required
def conversations_api():
    user = session.get('user')
    user_identifiant = user.get('identifiant', '')
    conversations = load_conversations(user_identifiant)
    return jsonify({
        'items': conversations,
        'count': len(conversations),
        'usable_count': sum(1 for item in conversations if is_conversation_usable(item)),
        'logs': get_log_files_for_user(user_identifiant),
    })


@user_pages_bp.route('/api/conversations/sync', methods=['POST'])
@login_required
def conversations_sync_api():
    user = session.get('user')
    payload = request.get_json() or {}
    conversations = payload.get('conversations', [])
    if not isinstance(conversations, list):
        return jsonify({'error': 'format invalide'}), 400

    merged = sync_conversations(user.get('identifiant', ''), conversations)
    return jsonify({
        'success': True,
        'items': merged,
        'count': len(merged),
        'logs': get_log_files_for_user(user.get('identifiant', '')),
    })


@user_pages_bp.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation_api(conversation_id):
    user = session.get('user')
    remaining = delete_conversation(user.get('identifiant', ''), conversation_id)
    return jsonify({
        'success': True,
        'items': remaining,
        'count': len(remaining),
        'logs': get_log_files_for_user(user.get('identifiant', '')),
    })


@user_pages_bp.route('/api/historique/<int:item_id>', methods=['DELETE'])
@login_required
def delete_history_item_api(item_id):
    if not _history_allowed():
        return jsonify({'error': 'historique indisponible pour les administrateurs'}), 403
    user = session.get('user')
    deleted = delete_history_item(user.get('identifiant', ''), item_id)
    if not deleted:
        return jsonify({'error': 'introuvable'}), 404
    return jsonify({'success': True, 'deleted_id': item_id})


@user_pages_bp.route('/api/historique/export', methods=['GET'])
@login_required
def export_history_api():
    if not _history_allowed():
        return jsonify({'error': 'historique indisponible pour les administrateurs'}), 403
    user = session.get('user')
    rows = get_full_history_for_export(user.get('identifiant', ''))
    return jsonify({
        'success': True,
        'identifiant': user.get('identifiant', ''),
        'export_date': datetime.utcnow().isoformat(),
        'history': rows,
        'count': len(rows),
    })


@user_pages_bp.route('/api/historique/all', methods=['DELETE'])
@login_required
def delete_all_history_api():
    if not _history_allowed():
        return jsonify({'error': 'historique indisponible pour les administrateurs'}), 403
    user = session.get('user')
    identifiant = user.get('identifiant', '')
    deleted_sql = delete_all_history_for_user(identifiant)
    deleted_conv = delete_all_conversations(identifiant)
    return jsonify({'success': True, 'deleted': deleted_sql, 'deleted_conversations': deleted_conv})


@user_pages_bp.route('/api/conversations/all', methods=['DELETE'])
@login_required
def delete_all_conversations_api():
    user = session.get('user')
    deleted = delete_all_conversations(user.get('identifiant', ''))
    return jsonify({'success': True, 'deleted': deleted})


@user_pages_bp.route('/api/conversations/errors', methods=['DELETE'])
@login_required
def delete_error_conversations_api():
    if not _history_allowed():
        return jsonify({'error': 'historique indisponible pour les administrateurs'}), 403
    user = session.get('user')
    remaining, removed = delete_error_conversations(user.get('identifiant', ''))
    return jsonify({
        'success': True,
        'removed': removed,
        'items': remaining,
        'count': len(remaining),
        'logs': get_log_files_for_user(user.get('identifiant', '')),
    })
