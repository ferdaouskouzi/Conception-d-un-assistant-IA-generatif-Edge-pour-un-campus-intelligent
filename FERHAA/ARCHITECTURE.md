# Architecture du projet FERHAA

## Structure réelle

```
mon_projet/
├── backend/              ← APPLICATION PRINCIPALE (version finale)
│   ├── app.py            ← Point d'entrée Flask
│   ├── .env              ← Variables d'environnement (non versionné)
│   ├── .env.example      ← Modèle de configuration
│   ├── routes/           ← Blueprints Flask
│   │   ├── auth.py       ← Inscription / connexion / profil
│   │   ├── ask.py        ← Route principale IA
│   │   ├── admin.py      ← Tableau de bord administrateur
│   │   ├── governance.py ← Gouvernance et conformité
│   │   └── user_pages.py ← Historique, conversations
│   ├── services/         ← Logique métier
│   │   ├── users.py      ← Gestion des utilisateurs (SQLite)
│   │   ├── database.py   ← Historique, audit, feedback (SQLite)
│   │   ├── cache.py      ← Cache des réponses (SQLite)
│   │   ├── cloud.py      ← API Groq (LLM cloud)
│   │   ├── degrade.py    ← Mode hors-ligne (Ollama + fallback)
│   │   ├── rgpd.py       ← Filtre données personnelles
│   │   ├── rbac.py       ← Rôles et permissions
│   │   └── governance.py ← Snapshot de gouvernance
│   └── data/             ← Bases SQLite (non versionnées)
│
├── frontend/             ← Interface utilisateur
│   ├── templates/        ← Pages HTML (Jinja2)
│   └── static/           ← CSS, JS, images
│
├── app.py                ← Prototype v1 (conservé pour traçabilité)
├── rgpd.py               ← Prototype v1 — remplacé par backend/services/rgpd.py
├── cache.py              ← Prototype v1 — remplacé par backend/services/cache.py
├── cloud.py              ← Prototype v1 — remplacé par backend/services/cloud.py
├── database.py           ← Prototype v1 — remplacé par backend/services/database.py
└── degrade.py            ← Prototype v1 — remplacé par backend/services/degrade.py
```

## Évolution du projet

| Phase | Description |
|---|---|
| **v1 — Prototype** | Un seul fichier `app.py` à la racine, sans authentification, sans base de données structurée. Objectif : valider le concept (API Groq + fallback Ollama). |
| **v2 — Production** | Refactoring complet dans `backend/`. Ajout : authentification, rôles (RBAC), SQLite pour les utilisateurs et l'historique, filtre RGPD amélioré, limite de quota, warmup Ollama, audit log. |

Les fichiers à la racine (`app.py`, `rgpd.py`, etc.) sont le **prototype v1**, conservés
pour montrer la progression du projet. Ils ne sont pas utilisés en production.

## Lancer l'application

```bash
cd backend
pip install -r requirements.txt
python app.py
```

## Mode dégradé (sans internet)

| Source dans l'historique | Signification |
|---|---|
| `cloud_groq` | Réponse du LLM Groq (cloud) |
| `degrade_local` | Réponse d'Ollama en local (`llama3.2:3b`) |
| `fallback_predefined` | Réponse prédéfinie par mots-clés (Ollama absent) |
| `cache_local` | Réponse servie depuis le cache SQLite |
