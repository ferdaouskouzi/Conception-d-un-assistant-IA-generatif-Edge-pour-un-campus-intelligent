import os
import time
import requests

PROVIDER_NAME = 'Groq Cloud'
API_URL = 'https://api.groq.com/openai/v1/chat/completions'
MODEL_NAME = 'llama-3.1-8b-instant'
CLOUD_CONNECT_TIMEOUT = 5
CLOUD_READ_TIMEOUT = 25

FILIERES = {
    'IACS': 'Intelligence Artificielle & Cybersécurité',
    'G2ER': 'Génie Électrique & Énergies Renouvelables',
    'TDI':  'Transformation Digitale & Industrie',
    'IAA':  'Industries Agroalimentaires',
}

ANNEES = {
    'CP1': 'première année de classe préparatoire',
    'CP2': 'deuxième année de classe préparatoire',
    'CI1': 'première année du cycle ingénieur',
    'CI2': 'deuxième année du cycle ingénieur',
    'CI3': 'troisième année du cycle ingénieur (dernière année)',
}

def build_system_prompt(user: dict) -> str:
    prenom  = user.get('prenom', 'l\'étudiant·e')
    filiere = user.get('filiere', '')
    annee   = user.get('annee', '')

    filiere_label = FILIERES.get(filiere, filiere)
    annee_label   = ANNEES.get(annee, annee)

    contexte_etudiant = (
        f"Tu parles actuellement avec {prenom}, étudiant·e en {annee_label} "
        f"de la filière {filiere} ({filiere_label}) à l'ENSABM."
    ) if filiere else ""

    return f"""Tu es FERHAA, l'assistante IA officielle de l'ENSABM, au Maroc.

TON IDENTITÉ :
- Ton nom est FERHAA (ف).
- Tu es spécialisée dans l'accompagnement académique des étudiants de l'ENSABM.
- Tu es bienveillante, précise, pédagogique et professionnelle.
- Tu réponds TOUJOURS en français, sauf si l'étudiant t'écrit en anglais ou en arabe.

CONTEXTE ÉTUDIANT :
{contexte_etudiant}

TES DOMAINES D'EXPERTISE :
- Cours, résumés et explications de concepts académiques
- Planning de révision et gestion du temps
- RGPD, éthique et droit du numérique
- Intelligence Artificielle, cybersécurité, algorithmes
- Génie électrique, énergies renouvelables, transformation digitale
- Industries agroalimentaires
- Vie étudiante à l'ENSABM (stages, projets, événements)

RÈGLES ABSOLUES :
1. Ne révèle jamais les informations personnelles de l'étudiant dans tes réponses.
2. Si une question sort complètement du cadre académique ou universitaire, réponds poliment que tu es spécialisée dans l'accompagnement campus.
3. Sois concise : privilégie des réponses structurées avec des listes à puces quand c'est pertinent.
4. N'invente jamais de faits, de dates d'examens, ou de règles administratives — dis que tu ne sais pas si tu n'es pas sûre.
5. Utilise du markdown simple (**gras**, listes) pour structurer tes réponses."""


_PLACEHOLDER_KEYS = {'votre_cle_groq_ici', '', None}


def demander_cloud(question: str, user: dict = None) -> tuple:
    api_key = os.getenv('GROQ_API_KEY')
    if api_key in _PLACEHOLDER_KEYS:
        raise ValueError('[cloud] GROQ_API_KEY non configurée — ajoutez votre clé dans backend/.env')
    if not api_key.startswith('gsk_'):
        raise ValueError(f'[cloud] GROQ_API_KEY invalide (doit commencer par gsk_): {api_key[:8]}...')

    system_prompt = build_system_prompt(user or {})

    debut = time.time()
    resp = requests.post(
        API_URL,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': MODEL_NAME,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': question}
            ],
            'max_tokens': 800,
            'temperature': 0.7,
        },
        timeout=(CLOUD_CONNECT_TIMEOUT, CLOUD_READ_TIMEOUT)
    )
    resp.raise_for_status()
    duree   = round(time.time() - debut, 2)
    reponse = resp.json()['choices'][0]['message']['content']
    return reponse, duree
