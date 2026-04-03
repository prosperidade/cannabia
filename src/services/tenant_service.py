# src/services/tenant_service.py
"""
Serviço de onboarding e gestão administrativa de Tenants (B2B).

Responsável por:
  - Criar novos tenants (clínicas, associações, médicos independentes)
  - Provisionar automaticamente: clinic legada, branding padrão, integração vazia
  - Convidar usuários ao tenant com role e vínculo em user_clinics + user_tenant_roles
  - Atualizar configurações do tenant (branding, dados cadastrais)

Cada tenant criado pela API gera:
  1. Registro em `tenants` com tipo e slug
  2. Registro espelho em `clinics` (compatibilidade legada)
  3. Registro em `tenant_branding` com valores padrão
  4. Registro em `tenant_integrations` vazio (pronto para configuração)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import bcrypt

from src.infra.database import db_cursor
from src.infra.audit import log_audit_event

logger = logging.getLogger("cannabia.tenant_service")


# ═══════════════════════════════════════════════════════════════════════════
# Utilitários
# ═══════════════════════════════════════════════════════════════════════════

def _slugify(text: str) -> str:
    """Gera slug URL-safe a partir de um nome."""
    slug = text.lower().strip()
    slug = re.sub(r"[àáâãäå]", "a", slug)
    slug = re.sub(r"[èéêë]", "e", slug)
    slug = re.sub(r"[ìíîï]", "i", slug)
    slug = re.sub(r"[òóôõö]", "o", slug)
    slug = re.sub(r"[ùúûü]", "u", slug)
    slug = re.sub(r"[ç]", "c", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:64]


def _ensure_unique_slug(base_slug: str) -> str:
    """Garante unicidade do slug adicionando sufixo numérico se necessário."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute("SELECT slug FROM tenants WHERE slug = %s", (base_slug,))
        if not cursor.fetchone():
            return base_slug

        # Tenta sufixos incrementais
        for i in range(2, 100):
            candidate = f"{base_slug}-{i}"[:64]
            cursor.execute("SELECT slug FROM tenants WHERE slug = %s", (candidate,))
            if not cursor.fetchone():
                return candidate

    raise ValueError(f"Não foi possível gerar slug único para '{base_slug}'")


# ═══════════════════════════════════════════════════════════════════════════
# Criação de Tenant
# ═══════════════════════════════════════════════════════════════════════════

def create_tenant(
    legal_name: str,
    display_name: str,
    tenant_type_slug: str = "clinic",
    *,
    custom_slug: Optional[str] = None,
) -> dict[str, Any]:
    """
    Cria um novo tenant com provisão completa.

    Fluxo transacional:
      1. Resolve tenant_type_id a partir do slug
      2. Insere em `tenants`
      3. Insere clínica legada em `clinics` e vincula ao tenant
      4. Insere branding padrão em `tenant_branding`
      5. Insere registro vazio em `tenant_integrations`

    Args:
        legal_name:        Razão social / nome legal
        display_name:      Nome de exibição
        tenant_type_slug:  Tipo do tenant (clinic, association, doctor)
        custom_slug:       Slug customizado (opcional; gerado do display_name se omitido)

    Returns:
        Dict com tenant_id, clinic_id, slug e dados criados

    Raises:
        ValueError: se dados inválidos ou tipo de tenant inexistente
    """
    if not legal_name or not legal_name.strip():
        raise ValueError("legal_name é obrigatório.")
    if not display_name or not display_name.strip():
        raise ValueError("display_name é obrigatório.")

    legal_name = legal_name.strip()
    display_name = display_name.strip()

    # Resolve tipo
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT id FROM tenant_types WHERE slug = %s",
            (tenant_type_slug,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Tipo de tenant '{tenant_type_slug}' não existe.")
        tenant_type_id = row["id"]

    # Gera slug único
    base_slug = _slugify(custom_slug or display_name)
    if not base_slug:
        raise ValueError("Não foi possível gerar slug a partir do nome fornecido.")
    slug = _ensure_unique_slug(base_slug)

    # Transação atômica: tenant + clinic legada + branding + integrations
    with db_cursor(dictionary=True) as (conn, cursor):
        # 1. Cria o tenant
        cursor.execute(
            """
            INSERT INTO tenants (tenant_type_id, legal_name, display_name, slug, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING id, slug, status, created_at
            """,
            (tenant_type_id, legal_name, display_name, slug),
        )
        tenant = cursor.fetchone()
        tenant_id = tenant["id"]

        # 2. Cria clínica espelho (compatibilidade legada)
        cursor.execute(
            """
            INSERT INTO clinics (name, slug, is_active, tenant_id)
            VALUES (%s, %s, TRUE, %s)
            RETURNING id
            """,
            (display_name, slug, tenant_id),
        )
        clinic = cursor.fetchone()
        clinic_id = clinic["id"]

        # Vincula tenant à clínica legada
        cursor.execute(
            "UPDATE tenants SET legacy_clinic_id = %s WHERE id = %s",
            (clinic_id, tenant_id),
        )

        # 3. Branding padrão
        cursor.execute(
            """
            INSERT INTO tenant_branding (tenant_id, brand_name)
            VALUES (%s, %s)
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            (tenant_id, display_name),
        )

        # 4. Integrations vazio (pronto para configurar)
        cursor.execute(
            """
            INSERT INTO tenant_integrations (tenant_id)
            VALUES (%s)
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            (tenant_id,),
        )

        conn.commit()

    log_audit_event(
        action="tenant_created",
        resource_type="tenant",
        resource_id=str(tenant_id),
        details={
            "legal_name": legal_name,
            "display_name": display_name,
            "slug": slug,
            "tenant_type": tenant_type_slug,
            "clinic_id": clinic_id,
        },
    )

    logger.info("Tenant criado: id=%d slug=%s clinic_id=%d", tenant_id, slug, clinic_id)

    return {
        "tenant_id": tenant_id,
        "clinic_id": clinic_id,
        "slug": slug,
        "legal_name": legal_name,
        "display_name": display_name,
        "tenant_type": tenant_type_slug,
        "status": "active",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Atualização de Tenant
# ═══════════════════════════════════════════════════════════════════════════

def update_tenant(
    tenant_id: int,
    *,
    legal_name: Optional[str] = None,
    display_name: Optional[str] = None,
    status: Optional[str] = None,
) -> dict[str, Any]:
    """
    Atualiza campos editáveis de um tenant existente.
    Apenas campos fornecidos (não-None) são atualizados.

    Returns:
        Dict com dados atualizados do tenant

    Raises:
        ValueError: se tenant não encontrado ou status inválido
    """
    valid_statuses = {"active", "inactive", "suspended"}
    if status and status not in valid_statuses:
        raise ValueError(f"Status inválido. Valores aceitos: {valid_statuses}")

    sets = []
    params = []

    if legal_name is not None:
        sets.append("legal_name = %s")
        params.append(legal_name.strip())
    if display_name is not None:
        sets.append("display_name = %s")
        params.append(display_name.strip())
    if status is not None:
        sets.append("status = %s")
        params.append(status)

    if not sets:
        raise ValueError("Nenhum campo para atualizar.")

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(tenant_id)

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            f"""
            UPDATE tenants SET {', '.join(sets)}
            WHERE id = %s
            RETURNING id, legal_name, display_name, slug, status, updated_at
            """,
            params,
        )
        updated = cursor.fetchone()
        if not updated:
            raise ValueError(f"Tenant {tenant_id} não encontrado.")
        conn.commit()

    log_audit_event(
        action="tenant_updated",
        resource_type="tenant",
        resource_id=str(tenant_id),
        details={"fields_updated": [s.split(" = ")[0] for s in sets if "updated_at" not in s]},
    )

    return dict(updated)


# ═══════════════════════════════════════════════════════════════════════════
# Convite de Usuário ao Tenant
# ═══════════════════════════════════════════════════════════════════════════

def invite_user_to_tenant(
    tenant_id: int,
    username: str,
    password: str,
    role: str = "Medico",
) -> dict[str, Any]:
    """
    Cria (ou reutiliza) um usuário e o vincula ao tenant com a role especificada.

    Fluxo:
      1. Verifica que o tenant existe e está ativo
      2. Cria usuário em `users` (ou reutiliza se username já existe)
      3. Vincula em `user_clinics` (tabela legada) com a clínica do tenant
      4. Vincula em `user_tenant_roles` com a role do tenant

    Args:
        tenant_id: ID do tenant alvo
        username:  Nome de usuário (único global)
        password:  Senha em texto plano (será hasheada)
        role:      Role no tenant (Admin, Medico, Atendente)

    Returns:
        Dict com user_id, tenant_id, clinic_id, role

    Raises:
        ValueError: tenant não encontrado/inativo, ou username já vinculado ao tenant
    """
    if not username or not username.strip():
        raise ValueError("username é obrigatório.")
    if not password or len(password) < 6:
        raise ValueError("password deve ter no mínimo 6 caracteres.")

    username = username.strip()
    valid_roles = {"Admin", "Medico", "Atendente"}
    if role not in valid_roles:
        raise ValueError(f"Role inválida. Valores aceitos: {valid_roles}")

    # Verifica tenant
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT t.id, t.status, t.legacy_clinic_id
            FROM tenants t
            WHERE t.id = %s
            """,
            (tenant_id,),
        )
        tenant = cursor.fetchone()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} não encontrado.")
        if tenant["status"] != "active":
            raise ValueError(f"Tenant {tenant_id} não está ativo (status: {tenant['status']}).")

    clinic_id = tenant["legacy_clinic_id"]

    # Cria ou reutiliza usuário
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            user_id = existing_user["id"]
        else:
            password_hash = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")

            cursor.execute(
                """
                INSERT INTO users (username, password_hash, role, is_active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id
                """,
                (username, password_hash, role),
            )
            user_id = cursor.fetchone()["id"]

        # Vínculo legado em user_clinics
        cursor.execute(
            """
            INSERT INTO user_clinics (user_id, clinic_id, role, is_default)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (user_id, clinic_id) DO UPDATE SET role = EXCLUDED.role
            """,
            (user_id, clinic_id, role.lower()),
        )

        # Vínculo de tenant em user_tenant_roles
        cursor.execute(
            """
            INSERT INTO user_tenant_roles (user_id, tenant_id, role, is_default, source_clinic_id)
            VALUES (%s, %s, %s, TRUE, %s)
            ON CONFLICT (user_id, tenant_id, role) DO NOTHING
            """,
            (user_id, tenant_id, role.lower(), clinic_id),
        )

        conn.commit()

    log_audit_event(
        action="user_invited_to_tenant",
        resource_type="user_tenant_roles",
        resource_id=str(user_id),
        details={
            "tenant_id": tenant_id,
            "clinic_id": clinic_id,
            "username": username,
            "role": role,
            "is_new_user": existing_user is None,
        },
    )

    logger.info(
        "Usuário vinculado ao tenant: user_id=%d tenant_id=%d role=%s",
        user_id, tenant_id, role,
    )

    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "clinic_id": clinic_id,
        "username": username,
        "role": role,
        "is_new_user": existing_user is None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Listagem
# ═══════════════════════════════════════════════════════════════════════════

def list_tenants(
    *,
    status: Optional[str] = None,
    tenant_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Lista tenants com filtros opcionais por status e tipo.

    Returns:
        Lista de dicts com dados resumidos do tenant
    """
    conditions = []
    params: list[Any] = []

    if status:
        conditions.append("t.status = %s")
        params.append(status)
    if tenant_type:
        conditions.append("tt.slug = %s")
        params.append(tenant_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params.extend([limit, offset])

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            f"""
            SELECT
                t.id,
                t.legal_name,
                t.display_name,
                t.slug,
                t.status,
                t.legacy_clinic_id AS clinic_id,
                tt.slug AS tenant_type,
                tb.brand_name,
                t.created_at
            FROM tenants t
            JOIN tenant_types tt ON tt.id = t.tenant_type_id
            LEFT JOIN tenant_branding tb ON tb.tenant_id = t.id
            {where}
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        return cursor.fetchall()


def get_tenant_detail(tenant_id: int) -> Optional[dict[str, Any]]:
    """Retorna detalhes completos de um tenant, incluindo branding e contagem de usuários."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                t.id,
                t.legal_name,
                t.display_name,
                t.slug,
                t.status,
                t.legacy_clinic_id AS clinic_id,
                tt.slug AS tenant_type,
                tb.brand_name,
                tb.logo_url,
                tb.primary_color,
                tb.secondary_color,
                tb.subdomain,
                t.created_at,
                t.updated_at,
                (SELECT COUNT(*) FROM user_tenant_roles utr WHERE utr.tenant_id = t.id) AS user_count
            FROM tenants t
            JOIN tenant_types tt ON tt.id = t.tenant_type_id
            LEFT JOIN tenant_branding tb ON tb.tenant_id = t.id
            WHERE t.id = %s
            """,
            (tenant_id,),
        )
        return cursor.fetchone()
