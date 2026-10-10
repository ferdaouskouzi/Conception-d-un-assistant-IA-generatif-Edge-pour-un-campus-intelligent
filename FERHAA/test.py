from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return "Serveur Flask OK"

@app.route('/ask', methods=['POST'])
def ask():
    return jsonify({"reponse": "Test OK", "source": "test", "temps": 0})

if __name__ == "__main__":
    app.run(debug=True)