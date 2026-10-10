"""Tests unitaires du mode dégradé."""
import pytest
from unittest.mock import patch, MagicMock
from services.degrade import _campus_fallback_response, mode_degrade, ollama_status


# ── _campus_fallback_response ─────────────────────────────────────────────────

class TestFallbackPredefined:

    def test_repond_deep_learning(self):
        rep = _campus_fallback_response("c'est quoi le deep learning ?")
        assert 'deep learning' in rep.lower() or 'Deep learning' in rep

    def test_repond_machine_learning(self):
        rep = _campus_fallback_response("explique le machine learning")
        assert 'machine learning' in rep.lower() or 'Machine learning' in rep

    def test_repond_rgpd(self):
        rep = _campus_fallback_response("qu'est-ce que le RGPD ?")
        assert 'RGPD' in rep or 'rgpd' in rep.lower()

    def test_repond_planning(self):
        rep = _campus_fallback_response("aide-moi à organiser mes révisions")
        assert len(rep) > 50

    def test_question_inconnue_repond_quand_meme(self):
        rep = _campus_fallback_response("question totalement inconnue xyz abc")
        assert isinstance(rep, str)
        assert len(rep) > 20

    def test_inclut_prenom(self):
        rep = _campus_fallback_response(
            "aide-moi à organiser mes révisions",
            user={'prenom': 'Youssef'}
        )
        assert 'Youssef' in rep


# ── ollama_status ─────────────────────────────────────────────────────────────

def test_ollama_status_structure():
    """La fonction retourne toujours un dict avec les clés attendues."""
    status = ollama_status()
    assert isinstance(status, dict)
    assert 'disponible' in status
    assert 'modele' in status

@patch('services.degrade.requests.get')
def test_ollama_status_disponible(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {'models': [{'name': 'llama3.2:3b'}]}
    )
    status = ollama_status()
    assert status['disponible'] is True
    assert status['modele_present'] is True

@patch('services.degrade.requests.get', side_effect=Exception("connexion refusée"))
def test_ollama_status_indisponible(mock_get):
    status = ollama_status()
    assert status['disponible'] is False
    assert 'erreur' in status


# ── mode_degrade ──────────────────────────────────────────────────────────────

@patch('services.degrade.ollama_disponible', return_value=False)
def test_mode_degrade_sans_ollama(mock_dispo):
    """Sans Ollama, le fallback prédefini est utilisé."""
    rep, duree, source = mode_degrade("qu'est-ce que le ML ?")
    assert source == 'fallback_predefined'
    assert isinstance(rep, str)
    assert duree >= 0

@patch('services.degrade.ollama_disponible', return_value=True)
@patch('services.degrade.demander_local', return_value=("Réponse Ollama", 1.5))
def test_mode_degrade_avec_ollama(mock_local, mock_dispo):
    """Avec Ollama disponible, la réponse locale est utilisée."""
    rep, duree, source = mode_degrade("explique le ML")
    assert source == 'degrade_local'
    assert rep == "Réponse Ollama"

@patch('services.degrade.ollama_disponible', return_value=True)
@patch('services.degrade.demander_local', side_effect=Exception("timeout"))
def test_mode_degrade_ollama_echoue(mock_local, mock_dispo):
    """Si Ollama est disponible mais échoue, on tombe sur le fallback prédefini."""
    rep, duree, source = mode_degrade("question quelconque")
    assert source == 'fallback_predefined'
