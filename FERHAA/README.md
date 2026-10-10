# Conception d'un assistant IA génératif Edge pour un campus intelligent

**FERHAA** est un assistant IA pour les étudiants de l'ENSA Béni Mellal (ENSABM). Il répond aux questions académiques, s'appuie sur les supports de cours déposés par les administrateurs, et choisit automatiquement entre un modèle **cloud** (Groq) et un modèle **local** (Ollama) selon la sensibilité de la question et la disponibilité d'Internet.

- **Réalisé par** : Latouti Hassnae et Kouzi Ferdaous
- **Encadré par** : Pr. Touil
- **Module** : Technologies émergentes & quantum

## Fonctionnalités

- **Comptes et rôles** : inscription, connexion, profil. Quatre rôles (étudiant, admin pédagogique, admin IT, super admin) avec des permissions distinctes (RBAC). Les mots de passe sont stockés hachés.
- **Questions / réponses** : chat avec un modèle de langage, adapté à la filière et à l'année de l'étudiant. Quota journalier de questions par utilisateur.
- **Supports de cours** : les administrateurs déposent des PDF, dont des extraits sont ajoutés au contexte de la question (RAG simple).
- **Cache local** des réponses déjà générées.
- **Filtre de données personnelles** (`services/rgpd.py`) : détecte par expressions régulières les adresses e-mail, téléphones, longues suites de chiffres, mots de passe et numéros de CIN. Si une donnée est détectée, la question est traitée en local.
- **Routeur Cloud / Edge** (`services/router.py`) et **mode dégradé** : Groq, puis Ollama en local, puis réponse prédéfinie hors ligne.
- **Historique** des échanges, **journal d'audit**, **réclamations** (signalement d'une réponse erronée, avec notification e-mail optionnelle) et page de **gouvernance**.

## Architecture

```
Question de l'étudiant
        │
        ▼
  Filtre RGPD (regex) ──── donnée sensible ───► Edge (Ollama local)
        │ non
        ▼
  Cache local ── trouvé ──► réponse du cache
        │ non
        ▼
  Routeur : Internet disponible ? ── oui ──► Cloud (Groq, llama-3.1-8b-instant)
                                   └─ non ──► Edge (Ollama, llama3.2:3b)

  Échec du cloud  → Edge → réponse prédéfinie
```

Le détail de la structure des dossiers est dans [`ARCHITECTURE.md`](ARCHITECTURE.md). L'application principale est dans `backend/`. Les fichiers à la racine (`app.py`, `rgpd.py`, ...) sont les prototypes de la version 1, conservés pour la traçabilité.

## Où vont les données

| Donnée | Où elle est stockée / envoyée |
|---|---|
| Comptes, historique, audit, réclamations, cache | Base SQLite **locale** (`backend/data/`), jamais envoyée sur Internet |
| Mots de passe | Hachés (Werkzeug), jamais en clair |
| Question sans donnée sensible détectée | Envoyée à l'API **Groq (cloud)**, avec le prénom, la filière et l'année de l'étudiant dans le prompt système |
| Question avec donnée sensible détectée | Traitée par Ollama **en local** (voir les limites ci-dessous) |

Le projet **n'est donc pas « 100 % local »** : le cloud est le mode par défaut, et le local sert de repli ou de protection pour les données détectées comme sensibles.

## Installation

Prérequis : Python 3.10+. Ollama est optionnel (https://ollama.com), mais nécessaire pour le mode local (`ollama pull llama3.2:3b`).

```bash
cd backend
python -m venv venv
source venv/Scripts/activate      # Git Bash sous Windows (Linux/macOS : source venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env              # puis renseigner GROQ_API_KEY et SECRET_KEY
python app.py
```

Ouvrir ensuite `http://127.0.0.1:5000` dans le navigateur. Cette adresse n'est valable que sur la machine où l'application tourne.

Une clé Groq gratuite s'obtient sur https://console.groq.com. Ne publiez jamais le fichier `.env` (il est ignoré par Git).

Au premier lancement, la base est créée dans `backend/data/` et des comptes administrateurs par défaut sont ajoutés avec un mot de passe initial de démonstration. **Changez-le avant tout usage réel.**

## Tests

```bash
cd backend
pytest
```

Certains tests sont en retard sur le code : `tests/test_router.py` référence d'anciennes fonctions du routeur, et plusieurs tests de `tests/test_rgpd.py` attendent une détection des noms propres que le filtre actuel ne fait pas.

## Limites connues

- **Fuite possible vers le cloud** : si une donnée sensible est détectée mais qu'Ollama est indisponible alors qu'Internet fonctionne, le routeur retombe sur Groq. La question part alors dans le cloud.
- **Le filtre RGPD ne détecte pas les noms propres** (ni, de façon générale, ce qui n'a pas un format reconnaissable par expression régulière). Il réduit les fuites évidentes mais ne remplace pas une analyse complète.
- Le contexte de l'étudiant (prénom, filière, année) est envoyé à Groq à chaque requête cloud.
- L'application tourne avec `debug=True` : prévu pour le développement local, pas pour la production.
- SQLite et les sessions Flask conviennent à une démonstration, pas à un déploiement à grande échelle.
- Un petit modèle local (3 milliards de paramètres) et un modèle cloud de 8 milliards de paramètres peuvent produire des réponses inexactes : les réponses doivent être vérifiées. Le système de réclamations sert à les signaler.

## Aperçu

*(captures d'écran à ajouter dans `docs/`)*
