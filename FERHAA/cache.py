import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'cache.db')

def init_cache():
    """Initialise la base de données du cache"""
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

def chercher_cache(question):
    """Cherche une question dans le cache"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT reponse FROM cache WHERE question = ?', (question,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def sauvegarder_cache(question, reponse):
    """Sauvegarde une question/réponse dans le cache"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO cache (question, reponse) VALUES (?, ?)
    ''', (question, reponse))
    conn.commit()
    conn.close()