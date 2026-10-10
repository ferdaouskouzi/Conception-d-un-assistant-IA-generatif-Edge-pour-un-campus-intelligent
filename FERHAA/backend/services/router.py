"""
Routeur Cloud / Edge — décide quel backend IA utiliser pour chaque question.

Architecture :
    Cloud (Groq llama3-8b) — priorité principale, meilleure qualité de réponse
    Edge  (Ollama llama3.2:3b) — fallback local, fonctionne sans internet

Règle de décision (dans l'ordre de priorité) :
    1. Données sensibles détectées         → Edge  (sécurité, jamais envoyé au cloud)
    2. Internet indisponible               → Edge  (pas le choix)
    3. Défaut                              → Cloud (toujours prioritaire)

Fallback à l'exécution :
    Cloud échoue → Edge si disponible → Fallback prédéfini
"""

import os
import socket
import time

from services.degrade import demander_local, ollama_disponible
from services.cloud import demander_cloud

_PLACEHOLDER_KEYS = {'votre_cle_groq_ici', '', None}


def _valider_cle_groq() -> bool:
    """Vérifie que GROQ_API_KEY est configurée avec une vraie valeur."""
    key = os.getenv('GROQ_API_KEY')
    if key in _PLACEHOLDER_KEYS or not str(key or '').startswith('gsk_'):
        print(f'[router] ⚠ GROQ_API_KEY non configurée ou invalide — Cloud désactivé, bascule Edge')
        return False
    return True

# ── Paramètres réseau ─────────────────────────────────────────────────────────

INTERNET_CHECK_HOST = ('8.8.8.8', 53)
INTERNET_TIMEOUT    = 2.0          # secondes — check TCP rapide


# ── Détecteur de connectivité ─────────────────────────────────────────────────

def _internet_disponible() -> bool:
    """Teste la connectivité réseau avec une connexion TCP rapide vers 8.8.8.8:53."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(INTERNET_TIMEOUT)
            s.connect(INTERNET_CHECK_HOST)
        return True
    except OSError:
        return False


# ── Décision de routage ───────────────────────────────────────────────────────

def _choisir_backend(donnees_sensibles: bool,
                     net_ok: bool) -> tuple[str, str]:
    """
    Retourne (backend, raison) où backend ∈ {'cloud', 'edge'}.

    Ordre de priorité :
      1. Données sensibles → Edge (sécurité locale)
      2. Pas d'internet    → Edge (forcé)
      3. Défaut            → Cloud (toujours prioritaire)
    """
    if donnees_sensibles:
        return 'edge', 'donnees_sensibles'

    if not net_ok:
        return 'edge', 'internet_indisponible'

    return 'cloud', 'cloud_prioritaire'


# ── Point d'entrée principal ──────────────────────────────────────────────────

def router(question: str, user: dict = None, donnees_sensibles: bool = False) -> tuple:
    """
    Choisit le bon backend et exécute la requête.

    Ordre d'exécution :
      1. Backend décidé par _choisir_backend()
      2. Si cloud → tente cloud ; sur échec → fallback edge si dispo
      3. Si edge  → tente edge  ; sur échec → tente cloud si internet dispo
      4. Dernier recours → réponse prédéfinie

    Retourne (reponse, duree, source, raison) où source est l'une de :
        'cloud_groq'          — réponse Groq cloud
        'degrade_local'       — réponse Ollama local
        'fallback_predefined' — réponse prédéfinie (hors ligne et edge absent)
    """
    # Calculer la disponibilité une seule fois pour cohérence décision/exécution
    edge_ok = ollama_disponible()
    net_ok  = _internet_disponible()
    debut   = time.time()

    backend, raison = _choisir_backend(donnees_sensibles, net_ok)

    if backend == 'cloud':
        try:
            reponse, duree = demander_cloud(question, user=user)
            return reponse, duree, 'cloud_groq', raison
        except Exception as cloud_err:
            print(f'[router] Cloud Groq échoué ({type(cloud_err).__name__}: {cloud_err}) — bascule Edge local')
            # Cloud échoue → fallback Edge si disponible
            if edge_ok:
                try:
                    reponse, duree = demander_local(question, user=user)
                    return reponse, duree, 'degrade_local', 'cloud_echec→edge_local'
                except Exception as edge_err:
                    print(f'[router] Edge local échoué aussi ({type(edge_err).__name__}: {edge_err}) — fallback prédéfini')
            else:
                print(f'[router] Edge non disponible — fallback prédéfini')
        return _fallback(question, user, debut) + ('cloud_echec→fallback_predefined',)

    else:  # backend == 'edge' (données sensibles ou pas d'internet)
        if edge_ok:
            try:
                reponse, duree = demander_local(question, user=user)
                return reponse, duree, 'degrade_local', raison
            except Exception as edge_err:
                print(f'[router] Edge local échoué ({type(edge_err).__name__}: {edge_err})')
        else:
            print(f'[router] Edge non disponible — raison: {raison}')
        # Edge indisponible ou en échec → tenter Cloud si internet dispo
        if net_ok:
            try:
                reponse, duree = demander_cloud(question, user=user)
                return reponse, duree, 'cloud_groq', 'edge_echec→cloud'
            except Exception as cloud_err:
                print(f'[router] Cloud Groq échoué en fallback ({type(cloud_err).__name__}: {cloud_err})')
        return _fallback(question, user, debut) + ('edge_echec→fallback_predefined',)


def _fallback(question: str, user: dict, debut: float) -> tuple:
    from services.degrade import _campus_fallback_response
    return (
        _campus_fallback_response(question, user=user),
        round(time.time() - debut, 2),
        'fallback_predefined',
    )


# ── Diagnostic (pour la gouvernance et le dashboard admin) ───────────────────

def router_status(question_exemple: str = 'test') -> dict:
    """Retourne l'état du routeur pour /api/status/router."""
    edge_ok = ollama_disponible()
    net_ok  = _internet_disponible()
    backend, raison = _choisir_backend(donnees_sensibles=False, net_ok=net_ok)

    labels = {
        'cloud_prioritaire':   'Cloud Groq (prioritaire)',
        'internet_indisponible': 'Mode local (pas d\'internet)',
        'donnees_sensibles':   'Mode local (données sensibles)',
    }

    return {
        'internet':           net_ok,
        'ollama':             edge_ok,
        'decision_actuelle':  backend,
        'raison':             raison,
        'raison_label':       labels.get(raison, raison),
        'politique':          'Cloud prioritaire — Edge uniquement en fallback',
    }
