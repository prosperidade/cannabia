# tests/test_permissions.py
"""Testes do framework de RBAC e permissões granulares."""

from unittest.mock import patch


def test_admin_has_all_permissions():
    """Admin deve ter todas as permissões definidas no sistema."""
    from src.infra.permissions import ROLE_PERMISSIONS, _ADMIN_PERMISSIONS

    admin_perms = ROLE_PERMISSIONS["Admin"]
    assert admin_perms == _ADMIN_PERMISSIONS
    assert "admin:metrics" in admin_perms
    assert "attendance:read" in admin_perms
    assert "medical_record:write" in admin_perms
    assert "ai:execute" in admin_perms


def test_medico_has_clinical_permissions():
    """Medico deve ter permissões clínicas mas não administrativas."""
    from src.infra.permissions import ROLE_PERMISSIONS

    medico_perms = ROLE_PERMISSIONS["Medico"]
    assert "attendance:read" in medico_perms
    assert "attendance:review" in medico_perms
    assert "medical_record:write" in medico_perms
    assert "ai:execute" in medico_perms
    # Não deve ter permissões de admin
    assert "admin:metrics" not in medico_perms
    assert "admin:users" not in medico_perms
    assert "admin:tenants" not in medico_perms


def test_atendente_has_limited_permissions():
    """Atendente deve ter apenas permissões de leitura e agendamento."""
    from src.infra.permissions import ROLE_PERMISSIONS

    atendente_perms = ROLE_PERMISSIONS["Atendente"]
    assert "message:read" in atendente_perms
    assert "appointment:read" in atendente_perms
    assert "appointment:write" in atendente_perms
    # Não deve ter permissões clínicas ou de admin
    assert "attendance:review" not in atendente_perms
    assert "medical_record:write" not in atendente_perms
    assert "ai:execute" not in atendente_perms
    assert "admin:metrics" not in atendente_perms


def test_recepcao_keeps_atendente_permissions_after_role_rename():
    """Recepcao e o nome canonico atual e deve manter as permissoes antigas."""
    from src.infra.permissions import ROLE_PERMISSIONS

    assert ROLE_PERMISSIONS["Recepcao"] == ROLE_PERMISSIONS["Atendente"]


def test_role_hierarchy_is_inclusive():
    """Cada role deve conter todas as permissões do nível inferior."""
    from src.infra.permissions import ROLE_PERMISSIONS

    atendente = ROLE_PERMISSIONS["Atendente"]
    medico = ROLE_PERMISSIONS["Medico"]
    admin = ROLE_PERMISSIONS["Admin"]

    assert atendente.issubset(medico), "Medico deve conter todas as permissões de Atendente"
    assert medico.issubset(admin), "Admin deve conter todas as permissões de Medico"


def test_get_user_permissions_returns_frozenset():
    """get_user_permissions deve retornar frozenset."""
    from src.infra.permissions import get_user_permissions

    with patch("src.infra.permissions.get_effective_roles", return_value=["Admin"]):
        perms = get_user_permissions()
        assert isinstance(perms, frozenset)
        assert len(perms) > 0


def test_has_permission_or_semantics():
    """has_permission com múltiplos args deve usar semântica OR."""
    from src.infra.permissions import has_permission

    with patch("src.infra.permissions.get_effective_roles", return_value=["Atendente"]):
        # Atendente tem message:read mas não medical_record:write
        assert has_permission("message:read", "medical_record:write") is True
        assert has_permission("admin:metrics") is False


def test_has_permission_accepts_recepcao_role():
    from src.infra.permissions import has_permission

    with patch("src.infra.permissions.get_effective_roles", return_value=["Recepcao"]):
        assert has_permission("message:read", "medical_record:write") is True
        assert has_permission("admin:metrics") is False


def test_has_all_permissions_and_semantics():
    """has_all_permissions com múltiplos args deve usar semântica AND."""
    from src.infra.permissions import has_all_permissions

    with patch("src.infra.permissions.get_effective_roles", return_value=["Medico"]):
        assert has_all_permissions("attendance:read", "attendance:review") is True
        assert has_all_permissions("attendance:read", "admin:metrics") is False


def test_unknown_role_has_no_permissions():
    """Role desconhecida não deve ter nenhuma permissão."""
    from src.infra.permissions import get_user_permissions

    with patch("src.infra.permissions.get_effective_roles", return_value=["RoleInexistente"]):
        perms = get_user_permissions()
        assert len(perms) == 0


def test_minimum_permission_count():
    """Sistema deve ter pelo menos 15 permissões granulares definidas."""
    from src.infra.permissions import _ADMIN_PERMISSIONS
    assert len(_ADMIN_PERMISSIONS) >= 15
