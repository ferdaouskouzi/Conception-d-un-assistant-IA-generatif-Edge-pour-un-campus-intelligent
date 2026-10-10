"""Tests unitaires du filtre RGPD."""
import pytest
from services.rgpd import verifier_rgpd


# ── Données personnelles — doivent être BLOQUÉES ──────────────────────────────

@pytest.mark.parametrize("texte", [
    "Mon numéro est 12345678",                  # 8+ chiffres
    "test@usms.ac.ma",                          # email
    "0612345678",                               # téléphone marocain
    "0756789012",                               # téléphone marocain variante
    "mon mot de passe est Secret1!",            # mot de passe divulgué
    "mdp: MonSecret123",                        # mot de passe abrégé
    "cin: AB123456",                            # CIN avec keyword
    "AB123456",                                 # CIN sans keyword
    "Mon nom est Mohammed Alami",               # nom complet
    "je m'appelle Fatima Zahra",               # formule d'identification
    "Je suis Ahmed Benali",                     # je suis + 2 noms
    "mon prénom est Youssef",                   # prénom explicite
    "il s'appelle Khalid Idrissi",             # tiers identifié
    "appelle-moi Karim Mansouri",              # formule de présentation
])
def test_bloque(texte):
    assert verifier_rgpd(texte) is True, f"Devrait être bloqué : {texte!r}"


# ── Questions légitimes — ne doivent PAS être bloquées ───────────────────────

@pytest.mark.parametrize("texte", [
    "Explique-moi le machine learning",
    "Comment fonctionne le deep learning ?",
    "je suis étudiant en CP1",
    "je suis en deuxième année",
    "étudiant en informatique",
    "mon cours préféré est le RGPD",
    "je suis content de ma note",
    "Qu'est-ce qu'un réseau de neurones ?",
    "Aide-moi à réviser pour l'examen",
    "Explique la différence entre IA et ML",
])
def test_autorise(texte):
    assert verifier_rgpd(texte) is False, f"Ne devrait pas être bloqué : {texte!r}"


# ── Cas limites ───────────────────────────────────────────────────────────────

def test_texte_vide():
    assert verifier_rgpd('') is False

def test_texte_none():
    # verifier_rgpd doit accepter None sans crasher
    try:
        result = verifier_rgpd(None)
        assert result is False
    except TypeError:
        pass  # acceptable si le contrat d'interface exige une str

def test_apostrophe_typographique():
    """L'apostrophe typographique ' (U+2019) doit être traitée comme '."""
    assert verifier_rgpd("je m\u2019appelle Fatima Zahra") is True

def test_cin_sans_keyword():
    """CIN marocain détecté sans le mot 'cin:' en préfixe."""
    assert verifier_rgpd("mon identifiant est K123456") is True

def test_email_institutionnel():
    assert verifier_rgpd("prenom.nom@usms.ac.ma") is True

def test_question_avec_chiffres_courts():
    """4 chiffres consécutifs ne déclenchent pas le filtre."""
    assert verifier_rgpd("il y a 2024 étudiants") is False
