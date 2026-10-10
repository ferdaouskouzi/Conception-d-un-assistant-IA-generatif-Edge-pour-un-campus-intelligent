"""Tests unitaires du routeur Cloud/Edge."""
import pytest
from unittest.mock import patch, MagicMock
from services.router import _choisir_backend, _est_complexe, _est_simple, router_status


# ── Détecteurs de complexité ──────────────────────────────────────────────────

class TestComplexite:

    def test_question_courte_est_simple(self):
        assert _est_simple("c'est quoi le ML") is True

    def test_question_longue_nest_pas_simple(self):
        assert _est_simple("Explique-moi en détail comment fonctionne un réseau de neurones convolutif") is False

    def test_mot_cle_complexe(self):
        assert _est_complexe("résume le cours de deep learning") is True
        assert _est_complexe("explique la différence entre IA et ML") is True
        assert _est_complexe("planifie mes révisions pour le semestre") is True

    def test_question_simple_pas_complexe(self):
        assert _est_complexe("bonjour") is False
        assert _est_complexe("c'est quoi python") is False

    def test_seuil_mots(self):
        # 8 mots ou moins → simple
        assert _est_simple("définition de l'intelligence artificielle en bref") is True
        # 9 mots sans mot-clé simple → pas simple
        assert _est_simple("je veux comprendre le fonctionnement des réseaux de neurones") is False


# ── Décision de routage ───────────────────────────────────────────────────────

class TestDecision:

    def test_sans_internet_va_edge(self):
        backend, raison = _choisir_backend("question quelconque", False, edge_ok=True, net_ok=False)
        assert backend == 'edge'
        assert raison == 'internet_indisponible'

    def test_sans_ollama_va_cloud(self):
        backend, raison = _choisir_backend("question quelconque", False, edge_ok=False, net_ok=True)
        assert backend == 'cloud'
        assert raison == 'ollama_indisponible'

    def test_question_simple_va_edge(self):
        backend, raison = _choisir_backend("c'est quoi le ML", False, edge_ok=True, net_ok=True)
        assert backend == 'edge'
        assert raison == 'question_simple'

    def test_question_complexe_va_cloud(self):
        backend, raison = _choisir_backend(
            "résume-moi tout le cours de deep learning en détail", False, edge_ok=True, net_ok=True
        )
        assert backend == 'cloud'
        assert raison == 'question_complexe'

    def test_donnees_sensibles_forcent_edge(self):
        """Peu importe la connectivité, les données sensibles restent en local."""
        backend, raison = _choisir_backend("ma question sensible", True, edge_ok=True, net_ok=True)
        assert backend == 'edge'
        assert raison == 'donnees_sensibles'


# ── Basculement automatique ───────────────────────────────────────────────────

class TestBascule:

    @patch('services.router.ollama_disponible', return_value=True)
    @patch('services.router._internet_disponible', return_value=True)
    @patch('services.router.demander_cloud', side_effect=Exception("timeout cloud"))
    @patch('services.router.demander_local', return_value=("Réponse locale", 1.0))
    def test_cloud_echoue_bascule_edge(self, mock_local, mock_cloud, mock_net, mock_ollama):
        from services.router import router
        rep, duree, source, raison = router("résume le cours de machine learning")
        assert source == 'degrade_local'
        assert 'cloud_failed' in raison

    @patch('services.router.ollama_disponible', return_value=False)
    @patch('services.router._internet_disponible', return_value=True)
    @patch('services.router.demander_cloud', return_value=("Réponse cloud", 2.5))
    def test_edge_absent_utilise_cloud(self, mock_cloud, mock_net, mock_ollama):
        from services.router import router
        rep, duree, source, raison = router("c'est quoi le ML")
        # Sans Ollama, même question simple → cloud
        assert source == 'cloud_groq'

    @patch('services.router.ollama_disponible', return_value=False)
    @patch('services.router._internet_disponible', return_value=False)
    def test_tout_indisponible_fallback_predefini(self, mock_net, mock_ollama):
        from services.router import router
        rep, duree, source, raison = router("c'est quoi le deep learning")
        assert source == 'fallback_predefined'


# ── router_status ─────────────────────────────────────────────────────────────

def test_router_status_structure():
    status = router_status()
    assert 'internet' in status
    assert 'ollama' in status
    assert 'decision_actuelle' in status
    assert status['decision_actuelle'] in ('cloud', 'edge')
    assert 'raison' in status
