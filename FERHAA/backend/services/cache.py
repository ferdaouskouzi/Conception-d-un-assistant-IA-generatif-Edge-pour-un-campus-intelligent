import sqlite3
import os
import re

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'cache.db')


def normaliser_question(question):
    texte = (question or '').strip().lower()
    return re.sub(r'\s+', ' ', texte)

def init_cache():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT UNIQUE,
            reponse TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("[Cache] Initialise.")

def _cle_cache(question, user_context=''):
    """
    Clé de cache = question normalisée + contexte utilisateur (filiere, annee).
    On n'utilise pas l'identifiant complet pour permettre le partage entre
    étudiants de la même filière posant la même question générique.
    """
    return normaliser_question(question) + '||' + str(user_context or '')


def chercher_cache(question, user_context=''):
    cle = _cle_cache(question, user_context)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT reponse FROM cache WHERE question = ?', (cle,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def sauvegarder_cache(question, reponse, user_context=''):
    cle = _cle_cache(question, user_context)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO cache (question, reponse) VALUES (?, ?)',
        (cle, reponse)
    )
    conn.commit()
    conn.close()
