import os
import time
import requests

def demander_cloud(question: str):
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise ValueError('GROQ_API_KEY manquante dans .env')

    debut = time.time()
    resp = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'llama3-8b-8192',
            'messages': [{'role': 'user', 'content': question}],
            'max_tokens': 500
        },
        timeout=15
    )
    resp.raise_for_status()
    duree = round(time.time() - debut, 2)
    reponse = resp.json()['choices'][0]['message']['content']
    return reponse, duree