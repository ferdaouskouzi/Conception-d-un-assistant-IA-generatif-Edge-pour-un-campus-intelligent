import time
import requests

def demander_local(question: str):
    debut = time.time()
    resp = requests.post(
        'http://localhost:11434/api/generate',
        json={
            'model': 'llama3.2:3b',
            'prompt': question,
            'stream': False
        },
        timeout=30
    )
    duree = round(time.time() - debut, 2)
    reponse = resp.json()['response']
    return reponse, duree


def mode_degrade(question: str):
    try:
        reponse, duree = demander_local(question)
        return reponse, duree, 'degrade_local'
    except Exception as e:
        print("ERREUR OLLAMA :", e)  
        return (
            "Service temporairement indisponible. Veuillez réessayer plus tard.",
            0.0,
            'degrade_fallback'
        )