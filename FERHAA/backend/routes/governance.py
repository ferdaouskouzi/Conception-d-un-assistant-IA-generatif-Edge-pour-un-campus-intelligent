from flask import Blueprint, jsonify, render_template, session

from services.degrade import ollama_status
from services.governance import build_governance_snapshot
from services.router import router_status

governance_bp = Blueprint('governance', __name__)


@governance_bp.route('/gouvernance')
def governance_page():
    if not session.get('user'):
        return render_template('login.html')
    return render_template('gouvernance.html')


@governance_bp.route('/api/gouvernance')
def governance_api():
    if not session.get('user'):
        return jsonify({'error': 'non connecte'}), 401
    return jsonify(build_governance_snapshot())


@governance_bp.route('/api/status/ollama')
def ollama_status_api():
    """Endpoint de diagnostic : état d'Ollama et du modèle local."""
    if not session.get('user'):
        return jsonify({'error': 'non connecte'}), 401
    return jsonify(ollama_status())


@governance_bp.route('/api/status/router')
def router_status_api():
    """Endpoint de diagnostic : décision actuelle du routeur Cloud/Edge."""
    if not session.get('user'):
        return jsonify({'error': 'non connecte'}), 401
    return jsonify(router_status())
