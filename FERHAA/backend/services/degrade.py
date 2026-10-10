import os
import time

import requests

from services.cloud import build_system_prompt

PROVIDER_NAME = 'Ollama local'
API_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
MODEL_NAME = os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')

# Délai de connexion court (Ollama tourne en local)
LOCAL_CONNECT_TIMEOUT = 3
# Délai de lecture long : le premier appel charge le modèle en RAM (~40s)
# Les appels suivants sont rapides (~300ms)
LOCAL_READ_TIMEOUT = 120
LOCAL_MAX_PREDICT = 220


# ── Health check ─────────────────────────────────────────────────────────────

def ollama_disponible() -> bool:
    """Vérifie si Ollama répond sur son port (sans charger le modèle)."""
    try:
        resp = requests.get(f'{API_URL}/api/tags', timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def ollama_status() -> dict:
    """
    Retourne un dictionnaire décrivant l'état d'Ollama.
    Utilisé par la route de gouvernance pour répondre au professeur.
    """
    try:
        resp = requests.get(f'{API_URL}/api/tags', timeout=2)
        if resp.status_code != 200:
            return {'disponible': False, 'modele': MODEL_NAME, 'modeles_installes': []}
        modeles = [m['name'] for m in resp.json().get('models', [])]
        modele_present = MODEL_NAME in modeles
        return {
            'disponible': True,
            'modele': MODEL_NAME,
            'modele_present': modele_present,
            'modeles_installes': modeles,
            'url': API_URL,
        }
    except Exception as e:
        return {
            'disponible': False,
            'modele': MODEL_NAME,
            'modeles_installes': [],
            'erreur': str(e),
        }


# ── Warmup ────────────────────────────────────────────────────────────────────

def warmup_ollama():
    """
    Pré-charge le modèle en RAM au démarrage du serveur.
    Évite le cold start de 40s sur la première question d'un étudiant.
    Appelé une seule fois depuis app.py.
    """
    if not ollama_disponible():
        print(f'[ollama] Service non détecté sur {API_URL} — mode dégradé fallback activé.')
        return

    print(f'[ollama] Chargement du modèle {MODEL_NAME} en mémoire...')
    debut = time.time()
    try:
        requests.post(
            f'{API_URL}/api/generate',
            json={
                'model': MODEL_NAME,
                'prompt': 'Bonjour',
                'stream': False,
                'options': {'num_predict': 1},
            },
            timeout=(LOCAL_CONNECT_TIMEOUT, LOCAL_READ_TIMEOUT),
        )
        duree = round(time.time() - debut, 1)
        print(f'[ollama] Modèle prêt en {duree}s.')
    except Exception as e:
        print(f'[ollama] Warmup échoué : {e}')


# ── Génération locale ─────────────────────────────────────────────────────────

def demander_local(question: str, user: dict = None) -> tuple:
    system = build_system_prompt(user or {})
    prompt = (
        f'{system}\n\n'
        'Réponds de façon utile, concise et rapide. '
        'Va à l\'essentiel et privilégie 3 à 6 points maximum.\n\n'
        f'Question de l\'étudiant : {question}'
    )

    debut = time.time()
    resp = requests.post(
        f'{API_URL}/api/generate',
        json={
            'model': MODEL_NAME,
            'prompt': prompt,
            'stream': False,
            'options': {
                'num_predict': LOCAL_MAX_PREDICT,
                'temperature': 0.4,
            },
        },
        timeout=(LOCAL_CONNECT_TIMEOUT, LOCAL_READ_TIMEOUT),
    )
    resp.raise_for_status()
    duree = round(time.time() - debut, 2)
    reponse = resp.json()['response']
    return reponse, duree


# ── Réponses prédéfinies (si Ollama absent) ───────────────────────────────────

def _campus_fallback_response(question: str, user: dict = None) -> str:
    question_lower = (question or '').lower()
    prenom = (user or {}).get('prenom') or 'etudiant'

    keyword_answers = [
        (
            ['deep learning', 'apprentissage profond', 'reseau de neurones'],
            '**Deep learning** : branche du machine learning basée sur des **réseaux de neurones à plusieurs couches**.\n\n'
            '- Apprend à partir de grandes quantités de données\n'
            '- Utilisé pour images, texte, audio\n'
            '- Exemples : reconnaissance faciale, traduction, assistants IA\n\n'
            'Je peux aussi comparer avec le machine learning classique.',
        ),
        (
            ['machine learning', ' ml '],
            '**Machine learning** : méthode permettant à un système de trouver des modèles dans les données.\n\n'
            '- Apprentissage supervisé\n'
            '- Apprentissage non supervisé\n'
            '- Apprentissage par renforcement',
        ),
        (
            ['rgpd', 'donnees personnelles', 'vie privee'],
            '**RGPD** : cadre de protection des données personnelles.\n\n'
            '- Minimisation des données\n'
            '- Transparence du traitement\n'
            '- Droit d\'accès, rectification et suppression',
        ),
        (
            ['planning', 'revision', 'organiser'],
            f'{prenom}, voici une méthode pour organiser vos révisions :\n\n'
            '- Classez les matières par priorité\n'
            '- Blocs de 45 à 60 minutes\n'
            '- Alternez théorie et exercices\n'
            '- Pauses courtes et régulières',
        ),
        (
            ['stage', 'pfe', 'projet'],
            '**Conseils pour stage / projet** :\n\n'
            '- Définir clairement l\'objectif\n'
            '- Lister les compétences à mobiliser\n'
            '- Planifier les livrables semaine par semaine\n'
            '- Documenter les difficultés et les solutions',
        ),
    ]

    for keywords, answer in keyword_answers:
        if any(keyword in question_lower for keyword in keywords):
            return answer

    return (
        'Le service IA local est temporairement indisponible.\n\n'
        f'Votre question : **{question}**\n\n'
        '- Précisez la matière ou le contexte\n'
        '- Indiquez si c\'est un besoin de cours, révision ou projet\n'
        '- Ajoutez votre niveau (CP1, CP2, CI1, CI2, CI3)\n\n'
        'Je pourrai vous fournir une réponse plus ciblée.'
    )


# ── Point d'entrée principal ──────────────────────────────────────────────────

def mode_degrade(question: str, user: dict = None) -> tuple:
    debut = time.time()

    # 1. Tenter Ollama local
    if ollama_disponible():
        try:
            reponse, duree = demander_local(question, user=user)
            return reponse, duree, 'degrade_local'
        except Exception as error:
            print(f'[ollama] Erreur génération : {error}')

    # 2. Fallback sur réponses prédéfinies (pattern matching, pas de modèle IA)
    return (
        _campus_fallback_response(question, user=user),
        round(time.time() - debut, 2),
        'fallback_predefined',
    )
