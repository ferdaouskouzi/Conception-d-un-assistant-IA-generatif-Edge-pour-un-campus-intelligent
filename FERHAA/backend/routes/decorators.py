"""
Décorateurs d'autorisation centralisés.

Usage :
    @login_required
    def ma_route(): ...

    @permission_required('manage_accounts')
    def route_admin(): ...

Les routes API (/api/...) reçoivent une réponse JSON.
Les routes page redirigent vers / ou /chat.
"""
from functools import wraps

from flask import jsonify, redirect, request, session

from services.rbac import has_permission


def _is_api():
    return request.path.startswith('/api/')


def login_required(f):
    """Vérifie qu'un utilisateur est connecté."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user'):
            if _is_api():
                return jsonify({'error': 'non connecte'}), 401
            return redirect('/')
        return f(*args, **kwargs)
    return wrapper


def permission_required(permission):
    """
    Vérifie qu'un utilisateur est connecté ET possède la permission donnée.
    Combine login_required + vérification RBAC en un seul décorateur.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = session.get('user')
            if not user:
                if _is_api():
                    return jsonify({'error': 'non connecte'}), 401
                return redirect('/')
            if not has_permission(user, permission):
                if _is_api():
                    return jsonify({'error': 'acces refuse'}), 403
                return redirect('/chat')
            return f(*args, **kwargs)
        return wrapper
    return decorator
