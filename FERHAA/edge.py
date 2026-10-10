import requests, time

def demander_local(question):
    debut = time.time()
    resp = requests.post(
        'http://localhost:11434/api/generate',
        json={
            'model': 'llama3.2:3b',
            'prompt': question,
            'stream': False
        }
    )
    duree = round(time.time() - debut, 2)
    reponse = resp.json()['response']
    return reponse, duree