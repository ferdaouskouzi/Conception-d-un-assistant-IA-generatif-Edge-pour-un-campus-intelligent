"""Tests unitaires du système de cache."""
import pytest
from services.cache import _cle_cache, chercher_cache, sauvegarder_cache


# ── Clé de cache ──────────────────────────────────────────────────────────────

def test_cle_normalise_casse():
    """La même question en majuscules ou minuscules donne la même clé."""
    assert _cle_cache("Machine Learning") == _cle_cache("machine learning")

def test_cle_normalise_espaces():
    """Les espaces multiples sont normalisés."""
    assert _cle_cache("deep  learning") == _cle_cache("deep learning")

def test_cle_different_contexte():
    """Deux contextes différents donnent des clés différentes."""
    assert _cle_cache("IA", "INFO|CI1") != _cle_cache("IA", "PEDA|CP2")

def test_cle_meme_contexte_meme_resultat():
    assert _cle_cache("IA", "INFO|CI1") == _cle_cache("IA", "INFO|CI1")

def test_cle_sans_contexte():
    """Sans contexte, la clé est uniquement la question normalisée."""
    cle = _cle_cache("deep learning", '')
    assert 'deep learning' in cle


# ── Stockage et récupération ──────────────────────────────────────────────────

def test_cache_miss():
    """Une question inconnue retourne None."""
    assert chercher_cache("question inexistante xyz", "CTX|1") is None

def test_cache_hit(tmp_path, monkeypatch):
    """Une réponse sauvegardée est retrouvée avec le même contexte."""
    import services.cache as cache_mod
    original = cache_mod.DB_PATH
    cache_mod.DB_PATH = str(tmp_path / 'test_cache.db')
    cache_mod.init_cache()
    try:
        sauvegarder_cache("qu est ce que le ml", "C'est du machine learning", "INFO|CI1")
        result = chercher_cache("qu est ce que le ml", "INFO|CI1")
        assert result == "C'est du machine learning"
    finally:
        cache_mod.DB_PATH = original

def test_cache_isole_par_contexte(tmp_path, monkeypatch):
    """La réponse d'Alice (INFO|CI1) n'est pas servie à Bob (PEDA|CP2)."""
    import services.cache as cache_mod
    original = cache_mod.DB_PATH
    cache_mod.DB_PATH = str(tmp_path / 'test_cache2.db')
    cache_mod.init_cache()
    try:
        sauvegarder_cache("résume mes cours", "Cours d'Alice...", "INFO|CI1")
        assert chercher_cache("résume mes cours", "PEDA|CP2") is None
    finally:
        cache_mod.DB_PATH = original

def test_cache_partage_meme_contexte(tmp_path):
    """Deux étudiants du même groupe partagent le cache sur une question générique."""
    import services.cache as cache_mod
    original = cache_mod.DB_PATH
    cache_mod.DB_PATH = str(tmp_path / 'test_cache3.db')
    cache_mod.init_cache()
    try:
        sauvegarder_cache("définition IA", "L'IA c'est...", "INFO|CI1")
        assert chercher_cache("définition IA", "INFO|CI1") == "L'IA c'est..."
    finally:
        cache_mod.DB_PATH = original
