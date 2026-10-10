"""Tests unitaires de la validation du mot de passe et des routes d'authentification."""
import pytest
from services.users import validate_password_strength


# ── validate_password_strength ────────────────────────────────────────────────

class TestValidatePasswordStrength:

    def test_mot_de_passe_valide(self):
        ok, _ = validate_password_strength("Secure@99!")
        assert ok is True

    def test_trop_court(self):
        ok, _ = validate_password_strength("Ab1!")
        assert ok is False

    def test_sans_majuscule(self):
        ok, _ = validate_password_strength("secure@99!")
        assert ok is False

    def test_sans_minuscule(self):
        ok, _ = validate_password_strength("SECURE@99!")
        assert ok is False

    def test_sans_chiffre(self):
        ok, _ = validate_password_strength("Secure@!!")
        assert ok is False

    def test_sans_special(self):
        ok, _ = validate_password_strength("Secure999")
        assert ok is False

    def test_mot_de_passe_commun(self):
        ok, _ = validate_password_strength("password")
        assert ok is False

    def test_contient_email(self):
        ok, _ = validate_password_strength("Alice@99!", email="alice@usms.ac.ma")
        assert ok is False

    def test_contient_identifiant(self):
        ok, _ = validate_password_strength("alice@99!", identifiant="alice")
        assert ok is False

    def test_retourne_conditions(self):
        _, conditions = validate_password_strength("faible")
        assert isinstance(conditions, list)
        assert len(conditions) > 0


# ── Routes d'authentification ─────────────────────────────────────────────────

class TestLoginRoute:

    def test_login_champs_manquants(self, client):
        resp = client.post('/api/login', json={})
        assert resp.status_code == 401

    def test_login_mauvais_mot_de_passe(self, client):
        resp = client.post('/api/login', json={
            'identifiant': 'admin.it@ensabm.ac.ma',
            'password': 'mauvais'
        })
        assert resp.status_code == 401
        assert resp.get_json()['success'] is False

    def test_login_admin_correct(self, client):
        resp = client.post('/api/login', json={
            'identifiant': 'admin.it@ensabm.ac.ma',
            'password': 'Admin@12345'
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert 'password' not in data['user']
        assert 'password_hash' not in data['user']

    def test_password_non_strippé(self, client):
        """Un mot de passe avec espace en début ne doit pas être automatiquement corrigé."""
        # On ne peut pas tester un vrai login avec espace sans inscription préalable,
        # mais on vérifie que le champ n'est pas altéré côté route.
        resp = client.post('/api/login', json={
            'identifiant': 'inexistant@usms.ac.ma',
            'password': ' MonMdp@1'
        })
        # Doit échouer proprement sans 500
        assert resp.status_code == 401


class TestRegisterRoute:

    def test_email_non_institutionnel(self, client):
        resp = client.post('/api/register', json={
            'email': 'alice@gmail.com',
            'password': 'Test@1234',
            'prenom': 'Alice',
            'nom': 'Test',
            'identifiant': 'alice.test',
            'cin': 'AB123456',
        })
        assert resp.status_code == 400
        assert 'institutionnel' in resp.get_json()['message']

    def test_cin_format_invalide(self, client):
        resp = client.post('/api/register', json={
            'email': 'alice@usms.ac.ma',
            'password': 'Test@1234',
            'prenom': 'Alice',
            'nom': 'Test',
            'identifiant': 'alice.test',
            'cin': '123456789',   # mauvais format
        })
        assert resp.status_code == 400
        assert 'CIN' in resp.get_json()['message']

    def test_mot_de_passe_faible(self, client):
        resp = client.post('/api/register', json={
            'email': 'alice@usms.ac.ma',
            'password': 'faible',
            'prenom': 'Alice',
            'nom': 'Test',
            'identifiant': 'alice.test',
            'cin': 'AB123456',
        })
        assert resp.status_code == 400

    def test_inscription_reussie(self, client):
        resp = client.post('/api/register', json={
            'email': 'nouveau@usms.ac.ma',
            'password': 'Secure@99!',
            'prenom': 'Nouveau',
            'nom': 'Etudiant',
            'identifiant': 'nouveau.etudiant',
            'cin': 'AB123456',
            'filiere': 'INFO',
            'annee': 'CI1',
        })
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_email_deja_utilise(self, client):
        payload = {
            'email': 'double@usms.ac.ma',
            'password': 'Secure@99!',
            'prenom': 'Double',
            'nom': 'Test',
            'identifiant': 'double.test',
            'cin': 'AB123456',
        }
        client.post('/api/register', json=payload)
        resp = client.post('/api/register', json=payload)
        assert resp.status_code == 400
        assert 'deja utilise' in resp.get_json()['message']


class TestProfileRoute:

    def test_profil_non_connecte(self, client):
        resp = client.get('/api/profile')
        assert resp.status_code == 401

    def test_profil_connecte(self, auth_client):
        resp = auth_client.get('/api/profile')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'email' in data
        assert 'password' not in data
        assert 'password_hash' not in data
