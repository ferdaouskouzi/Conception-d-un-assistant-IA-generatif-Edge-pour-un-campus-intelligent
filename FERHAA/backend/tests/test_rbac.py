"""Tests unitaires du système de rôles et permissions (RBAC)."""
import pytest
from services.rbac import get_permissions_for_role, has_permission, ROLE_LABELS


# ── get_permissions_for_role ──────────────────────────────────────────────────

def test_student_peut_poser_question():
    perms = get_permissions_for_role('student')
    assert 'ask_ai' in perms

def test_student_ne_peut_pas_administrer():
    perms = get_permissions_for_role('student')
    assert 'manage_accounts' not in perms
    assert 'view_admin_dashboard' not in perms

def test_super_admin_a_full_access():
    perms = get_permissions_for_role('super_admin')
    assert 'full_access' in perms

def test_admin_it_peut_gerer_comptes():
    perms = get_permissions_for_role('admin_it')
    assert 'manage_accounts' in perms

def test_role_inconnu_retourne_permissions_student():
    perms = get_permissions_for_role('role_inexistant')
    assert perms == get_permissions_for_role('student')


# ── has_permission ────────────────────────────────────────────────────────────

def test_user_avec_permission_ok():
    user = {'role': 'student', 'permissions': ['ask_ai', 'view_personal_history']}
    assert has_permission(user, 'ask_ai') is True

def test_user_sans_permission():
    user = {'role': 'student', 'permissions': ['ask_ai']}
    assert has_permission(user, 'manage_accounts') is False

def test_full_access_passe_tout():
    """super_admin avec full_access peut tout faire."""
    user = {'role': 'super_admin', 'permissions': ['full_access']}
    assert has_permission(user, 'manage_accounts') is True
    assert has_permission(user, 'view_audit_logs') is True
    assert has_permission(user, 'n_importe_quoi') is True

def test_permissions_depuis_role_si_liste_vide():
    """Si la liste permissions est vide, on utilise le rôle."""
    user = {'role': 'admin_it', 'permissions': []}
    # has_permission fallback sur get_permissions_for_role
    assert has_permission(user, 'manage_accounts') is True

def test_permissions_absentes_utilise_role():
    user = {'role': 'admin_it'}
    assert has_permission(user, 'manage_accounts') is True


# ── ROLE_LABELS ───────────────────────────────────────────────────────────────

def test_tous_les_roles_ont_un_label():
    for role in ['student', 'admin_it', 'admin_pedagogique', 'super_admin']:
        assert role in ROLE_LABELS
        assert isinstance(ROLE_LABELS[role], str)
        assert len(ROLE_LABELS[role]) > 0


# ── Routes admin protégées ────────────────────────────────────────────────────

def test_dashboard_sans_connexion(client):
    resp = client.get('/api/admin/dashboard')
    assert resp.status_code == 401

def test_dashboard_avec_student(auth_client):
    resp = auth_client.get('/api/admin/dashboard')
    assert resp.status_code == 403

def test_dashboard_avec_admin(admin_client):
    resp = admin_client.get('/api/admin/dashboard')
    assert resp.status_code == 200

def test_gestion_comptes_sans_permission(auth_client):
    """Un étudiant ne peut pas accéder à la liste des utilisateurs."""
    resp = auth_client.get('/api/admin/users')
    assert resp.status_code == 403
