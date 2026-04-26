/**
 * Catalogo central de navegacao do app.
 *
 * Cada item declara *para quem* ele e visivel (`visibleFor`). O
 * `filterNav()` recebe o contexto do usuario logado (role,
 * is_clinic_admin, tenant_type) e retorna apenas os items que ele
 * pode ver.
 *
 * 3 catalogos:
 *   - ADMIN_NAV: super admin global (/admin/*)
 *   - ORG_NAV:   app unificado da clinica/associacao (/org/* + /med/*
 *                para AdminClinica e medico-dono)
 *   - MED_NAV:   subset focado em "Modo Medico" para medico assalariado
 *                que entra direto em /med (sem privilegios de admin)
 *
 * Quando a Fase A2 consolidar /med dentro de /org, o MED_NAV some
 * (vira filtro do ORG_NAV).
 */
import type { SidebarNavItem } from "@/components/layouts/sidebar-layout";

/** Roles canonicos do backend (espelha src/infra/security.py ROLE_ALIASES). */
export type AppRole =
  | "Admin"
  | "AdminClinica"
  | "Medico"
  | "Recepcao"
  | "Financeiro"
  | "Paciente";

export type TenantType = "clinic" | "association" | "doctor" | string;

export type NavVisibility = {
  /** Se preenchido, qualquer role da lista ve. */
  roles?: AppRole[];
  /** Se true, basta ter is_clinic_admin=true (combina via OR com roles). */
  orClinicAdmin?: boolean;
  /** Se preenchido, item so aparece para tenant_type da lista. */
  tenantTypes?: TenantType[];
};

export type CatalogItem = SidebarNavItem & {
  visibleFor?: NavVisibility;
};

export type NavContext = {
  role: AppRole | string | null | undefined;
  isClinicAdmin: boolean;
  tenantType?: TenantType | null;
};

// ---------------------------------------------------------------------------
// Catalogos
// ---------------------------------------------------------------------------

/** Painel /admin — super admin global apenas. */
export const ADMIN_NAV: CatalogItem[] = [
  { label: "Visao Geral",     icon: "dashboard",        href: "/admin",            visibleFor: { roles: ["Admin"] } },
  { label: "Organizacoes",    icon: "apartment",        href: "/admin/tenants",    visibleFor: { roles: ["Admin"] } },
  { label: "Usuarios",        icon: "manage_accounts",  href: "/admin/usuarios",   visibleFor: { roles: ["Admin"] } },
  { label: "Auditoria IA",    icon: "monitoring",       href: "/admin/auditoria",  visibleFor: { roles: ["Admin"] } },
  { label: "Agentes IA",      icon: "smart_toy",        href: "/admin/agentes",    visibleFor: { roles: ["Admin"] } },
  { label: "Base Cientifica", icon: "library_books",    href: "/admin/knowledge",  visibleFor: { roles: ["Admin"] } },
  { label: "Sandbox",         icon: "account_balance",  href: "/admin/sandbox",    visibleFor: { roles: ["Admin"] } },
];

/**
 * Painel /org — app unificado da clinica/associacao.
 *
 * Permissoes do sidebar (resumido):
 *   - Geral (Painel/Agenda/Mensagens/Pacientes): todos do tenant
 *   - Acompanhamento: Medico, Recepcao, AdminClinica
 *   - Modo Medico (Fila/Consulta/Prescricao/...): Medico (e dono)
 *   - Operacao (Estoque/Faturamento/Financeiro/Campanhas):
 *       Financeiro, AdminClinica
 *       (Estoque so aparece se tenant_type = 'association')
 *   - Conformidade (Compliance/Sandbox/Relatorios): Medico (read),
 *       AdminClinica (gerir)
 *   - Base Cientifica: Medico, AdminClinica
 *   - Configuracoes: AdminClinica
 *   - Equipe / Medicos: AdminClinica
 */
export const ORG_NAV: CatalogItem[] = [
  // ── Geral
  { label: "Painel",            icon: "dashboard",        href: "/org/dashboard",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico", "Recepcao", "Financeiro"], orClinicAdmin: true } },
  { label: "Agendamentos",      icon: "calendar_month",   href: "/org/agendamentos",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico", "Recepcao"], orClinicAdmin: true } },
  { label: "Mensagens",         icon: "chat",             href: "/org/mensagens",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico", "Recepcao"], orClinicAdmin: true } },
  { label: "Pacientes",         icon: "group",            href: "/org/pacientes",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico", "Recepcao"], orClinicAdmin: true } },

  // ── Acompanhamento (cuidado continuo + agentes)
  { label: "Acompanhamento",    icon: "favorite",         href: "/org/acompanhamento",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico", "Recepcao"], orClinicAdmin: true } },

  // ── Modo Medico (so medico ve)
  { label: "Fila do dia",       icon: "queue",            href: "/med/fila",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Atendimentos",      icon: "assignment",       href: "/med/atendimentos",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Prescricoes",       icon: "prescriptions",    href: "/med/prescricao",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Retornos",          icon: "event_repeat",     href: "/med/retornos",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Inteligencia Clinica", icon: "psychology",    href: "/med/inteligencia",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Laboratorio IA",    icon: "biotech",          href: "/med/lab-ai",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Ensaios Clinicos",  icon: "science",          href: "/med/ensaios",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Precisao Botanica", icon: "eco",              href: "/med/botanical",
    visibleFor: { roles: ["Admin", "Medico"] } },

  // ── Base Cientifica (medico + admin clinica)
  { label: "Base Cientifica",   icon: "library_books",    href: "/org/conhecimento",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico"], orClinicAdmin: true } },

  // ── Operacao (financeiro + admin clinica)
  { label: "Estoque",           icon: "inventory_2",      href: "/org/estoque",
    visibleFor: { roles: ["Admin", "AdminClinica", "Financeiro"], orClinicAdmin: true, tenantTypes: ["association"] } },
  { label: "Faturamento",       icon: "receipt_long",     href: "/org/faturamento",
    visibleFor: { roles: ["Admin", "AdminClinica", "Financeiro"], orClinicAdmin: true } },
  { label: "Financeiro",        icon: "payments",         href: "/org/financeiro",
    visibleFor: { roles: ["Admin", "AdminClinica", "Financeiro"], orClinicAdmin: true } },
  { label: "Campanhas",         icon: "campaign",         href: "/org/campanhas",
    visibleFor: { roles: ["Admin", "AdminClinica", "Financeiro"], orClinicAdmin: true } },

  // ── Conformidade (medico read, admin clinica gerir)
  { label: "Relatorios",        icon: "analytics",        href: "/org/relatorios",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico"], orClinicAdmin: true } },
  { label: "Conformidade",      icon: "verified_user",    href: "/org/compliance",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico"], orClinicAdmin: true } },
  { label: "Sandbox",           icon: "account_balance",  href: "/org/sandbox/governance",
    visibleFor: { roles: ["Admin", "AdminClinica", "Medico"], orClinicAdmin: true, tenantTypes: ["association"] } },

  // ── Gestao da equipe (admin clinica)
  { label: "Medicos",           icon: "medical_services", href: "/org/medicos",
    visibleFor: { roles: ["Admin", "AdminClinica"], orClinicAdmin: true } },

  // ── Configuracoes (admin clinica)
  { label: "Configuracoes",     icon: "settings",         href: "/org/configuracoes",
    visibleFor: { roles: ["Admin", "AdminClinica"], orClinicAdmin: true } },
];

/**
 * Painel /med — Fase intermediaria. Quando a Fase A2 consolidar /med
 * dentro de /org, esse catalogo some. Por enquanto, medico assalariado
 * (sem is_clinic_admin) cai aqui com sidebar focado em "modo medico".
 */
export const MED_NAV: CatalogItem[] = [
  { label: "Painel",            icon: "dashboard",        href: "/med/dashboard",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Fila do dia",       icon: "queue",            href: "/med/fila",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Atendimentos",      icon: "assignment",       href: "/med/atendimentos",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Prescricoes",       icon: "prescriptions",    href: "/med/prescricao",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Meus Pacientes",    icon: "group",            href: "/med/pacientes",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Retornos",          icon: "event_repeat",     href: "/med/retornos",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Acompanhamento",    icon: "favorite",         href: "/org/acompanhamento",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Mensagens",         icon: "chat",             href: "/org/mensagens",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Inteligencia Clinica", icon: "psychology",    href: "/med/inteligencia",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Laboratorio IA",    icon: "biotech",          href: "/med/lab-ai",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Ensaios Clinicos",  icon: "science",          href: "/med/ensaios",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Precisao Botanica", icon: "eco",              href: "/med/botanical",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Base Cientifica",   icon: "library_books",    href: "/med/conhecimento",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Conformidade",      icon: "verified_user",    href: "/org/compliance",
    visibleFor: { roles: ["Admin", "Medico"] } },
  { label: "Configuracoes",     icon: "settings",         href: "/org/configuracoes",
    visibleFor: { roles: ["Admin", "Medico"], orClinicAdmin: true } },
];

// ---------------------------------------------------------------------------
// Filtro
// ---------------------------------------------------------------------------

function isVisible(item: CatalogItem, ctx: NavContext): boolean {
  const v = item.visibleFor;
  if (!v) return true; // sem regra = visivel para todos os autenticados

  // tenant_type filtro hard (se a regra existe e nao bate, esconde)
  if (v.tenantTypes && v.tenantTypes.length > 0) {
    if (!ctx.tenantType || !v.tenantTypes.includes(ctx.tenantType)) {
      return false;
    }
  }

  // role match OU clinic_admin (combinam via OR)
  const roleMatches = !!(
    v.roles &&
    v.roles.length > 0 &&
    ctx.role &&
    v.roles.includes(ctx.role as AppRole)
  );
  const adminMatches = !!(v.orClinicAdmin && ctx.isClinicAdmin);

  if (!v.roles && !v.orClinicAdmin) return true;
  return roleMatches || adminMatches;
}

/** Aplica o filtro a um catalogo e devolve no shape esperado pelo SidebarLayout. */
export function filterNav(
  catalog: CatalogItem[],
  ctx: NavContext,
): SidebarNavItem[] {
  return catalog
    .filter((item) => isVisible(item, ctx))
    .map(({ visibleFor: _v, ...rest }) => rest);
}

// ---------------------------------------------------------------------------
// Redirect pos-login por role
// ---------------------------------------------------------------------------

/**
 * Decide para onde mandar o usuario depois do login bem-sucedido.
 *
 * Regra geral:
 *   - Admin global -> /admin
 *   - Paciente     -> /p/dashboard
 *   - Medico-dono  -> /org/dashboard (tem privilegio admin local, ve tudo)
 *   - Medico puro  -> /med/dashboard (sidebar focado em modo medico)
 *   - Recepcao     -> /org/acompanhamento (tela inicial = trabalho do dia)
 *   - Financeiro   -> /org/financeiro
 *   - AdminClinica -> /org/dashboard
 */
export function getRoleRedirect(
  role: string | null | undefined,
  isClinicAdmin: boolean = false,
): string {
  const r = role?.toLowerCase();
  if (r === "admin") return "/admin";
  if (r === "paciente") return "/p/dashboard";
  if (r === "recepcao") return "/org/acompanhamento";
  if (r === "financeiro") return "/org/financeiro";
  if (r === "adminclinica" || r === "admin_clinica") return "/org/dashboard";
  if (r === "medico") return isClinicAdmin ? "/org/dashboard" : "/med/dashboard";
  return "/med/dashboard";
}
