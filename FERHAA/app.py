import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
print("API KEY =", os.getenv("GROQ_API_KEY"))

from flask import Flask, request, jsonify, render_template_string
from rgpd import verifier_rgpd
from cache import init_cache, chercher_cache, sauvegarder_cache
from cloud import demander_cloud
from degrade import mode_degrade
from database import init_db, sauvegarder

app = Flask(__name__)

# --- Initialisation ---
init_db()
init_cache()

# --- HTML simple ---
HTML = '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Assistant Campus IA</title>
</head>
<body>
<h2>Assistant Campus IA</h2>
<input id="q" placeholder="Pose ta question..." onkeydown="if(event.key==='Enter') poser()">
<button onclick="poser()">Envoyer</button>
<pre id="rep"></pre>
<script>
async function poser() {
    const question = document.getElementById("q").value;
    if (!question.trim()) return;
    document.getElementById("rep").innerText = "Chargement...";
    try {
        const r = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: question })
        });
        const d = await r.json();
        document.getElementById("rep").innerText = d.erreur || d.reponse;
    } catch (e) {
        document.getElementById("rep").innerText = "Erreur de connexion.";
    }
}
</script>
</body>
</html>
'''

# --- Routes ---
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/ask', methods=['POST'])
def ask():
    try:
        question = request.json.get('question', '')

        # RGPD
        if verifier_rgpd(question):
            return jsonify({'erreur': 'Refus RGPD : donnee personnelle detectee'})

        # Cache
        cached = chercher_cache(question)
        if cached:
            return jsonify({'reponse': cached, 'source': 'cache_local', 'temps': 0.0})

        # Cloud avec fallback
        try:
            reponse, duree = demander_cloud(question)
            source = 'cloud_groq'
        except Exception as e:
            print("ERREUR CLOUD :", e)
            reponse, duree, source = mode_degrade(question)

        # Sauvegarde
        sauvegarder_cache(question, reponse)
        sauvegarder(question, reponse, '', duree, 0, source)

        return jsonify({'reponse': reponse, 'source': source, 'temps': duree})

    except Exception as e:
        print("ERREUR DANS /ask :", e)
        return jsonify({'erreur': str(e)})

# --- Lancement Flask ---
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)