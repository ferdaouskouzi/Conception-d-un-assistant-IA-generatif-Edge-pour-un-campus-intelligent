import sqlite3
import datetime

def init_db():
    conn = sqlite3.connect('donnees_locales.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS historique (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        rep_cloud TEXT,
        rep_locale TEXT,
        temps_cloud REAL,
        temps_local REAL,
        source TEXT,
        date TEXT)''')
    conn.commit()
    conn.close()

def sauvegarder(question, rc, rl, tc, tl, source):
    conn = sqlite3.connect('donnees_locales.db')
    cur = conn.cursor()
    cur.execute('INSERT INTO historique VALUES (NULL,?,?,?,?,?,?,?)',
        (question, rc, rl, tc, tl, source,
         datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()