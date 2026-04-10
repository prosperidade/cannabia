"use client";

import { useState, useMemo, useEffect, useCallback } from "react";

import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { listAdminUsers, createAdminUser } from "@/lib/api";
import {
  Card,
  Badge,
  Button,
  StatCard,
  DataTable,
  SearchBar,
  MaterialIcon,
  Avatar,
  type DataTableColumn,
} from "@/components/ui-tw";

/* ================================================================== */
/*  TYPES                                                              */
/* ================================================================== */

type UserRole = "admin" | "medico" | "atendente" | "paciente";
type UserStatus = "ativo" | "inativo" | "pendente";

interface AdminUser {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  tenant: string;
  status: UserStatus;
  last_login: string | null;
  avatar?: string;
}

/* ================================================================== */
/*  BACKEND -> UI MAPPING                                              */
/* ================================================================== */

function normalizeRole(raw: string): UserRole {
  const lower = raw.toLowerCase();
  if (lower === "admin") return "admin";
  if (lower === "medico") return "medico";
  if (lower === "atendente") return "atendente";
  if (lower === "paciente") return "paciente";
  return "atendente"; // fallback
}

function mapBackendUser(raw: Record<string, unknown>): AdminUser {
  const fullName = raw.full_name as string | null;
  const username = raw.username as string | null;
  const email = raw.email as string | null;
  const isActive = raw.is_active as boolean;
  const clinics = (raw.clinics as { clinic_id: number; clinic_name: string; clinic_role: string }[]) ?? [];

  return {
    id: raw.id as number,
    name: fullName || username || "Sem nome",
    email: email || "",
    role: normalizeRole((raw.role as string) ?? ""),
    tenant: clinics[0]?.clinic_name ?? "Sem organizacao",
    status: isActive ? "ativo" : "inativo",
    last_login: (raw.updated_at as string) ?? null,
  };
}

/* ================================================================== */
/*  PERMISSIONS MATRIX                                                 */
/* ================================================================== */

type PermissionKey =
  | "dashboard"
  | "atendimentos"
  | "prescricoes"
  | "prontuarios"
  | "relatorios"
  | "admin"
  | "auditoria_ia";

const PERMISSION_LABELS: Record<PermissionKey, string> = {
  dashboard: "Painel",
  atendimentos: "Atendimentos",
  prescricoes: "Prescricoes",
  prontuarios: "Prontuarios",
  relatorios: "Relatorios",
  admin: "Admin",
  auditoria_ia: "Auditoria de IA",
};

const ROLE_PERMISSIONS: Record<UserRole, Record<PermissionKey, boolean>> = {
  admin: {
    dashboard: true,
    atendimentos: true,
    prescricoes: true,
    prontuarios: true,
    relatorios: true,
    admin: true,
    auditoria_ia: true,
  },
  medico: {
    dashboard: true,
    atendimentos: true,
    prescricoes: true,
    prontuarios: true,
    relatorios: true,
    admin: false,
    auditoria_ia: false,
  },
  atendente: {
    dashboard: true,
    atendimentos: true,
    prescricoes: false,
    prontuarios: false,
    relatorios: false,
    admin: false,
    auditoria_ia: false,
  },
  paciente: {
    dashboard: true,
    atendimentos: false,
    prescricoes: false,
    prontuarios: false,
    relatorios: false,
    admin: false,
    auditoria_ia: false,
  },
};

/* ================================================================== */
/*  RECENT ACTIVITY (static placeholder - no audit trail API yet)      */
/* ================================================================== */

interface ActivityEvent {
  id: number;
  icon: string;
  description: string;
  timestamp: string;
  type: "login" | "role_change" | "invite" | "deactivation";
}

const MOCK_ACTIVITY: ActivityEvent[] = [
  {
    id: 1,
    icon: "login",
    description: "Dr. Ricardo Silveira fez login",
    timestamp: "2026-04-07T12:30:00Z",
    type: "login",
  },
  {
    id: 2,
    icon: "person_add",
    description: "Juliana Reis foi convidada como Atendente",
    timestamp: "2026-04-07T11:00:00Z",
    type: "invite",
  },
  {
    id: 3,
    icon: "swap_horiz",
    description: "Bruno Almeida alterado de Medico para Admin",
    timestamp: "2026-04-06T15:30:00Z",
    type: "role_change",
  },
  {
    id: 4,
    icon: "login",
    description: "Marcos Oliveira fez login",
    timestamp: "2026-04-07T14:02:00Z",
    type: "login",
  },
  {
    id: 5,
    icon: "person_off",
    description: "Camila Ferreira foi desativada",
    timestamp: "2026-04-01T09:00:00Z",
    type: "deactivation",
  },
  {
    id: 6,
    icon: "person_add",
    description: "Patricia Lima foi convidada como Medico",
    timestamp: "2026-04-05T14:00:00Z",
    type: "invite",
  },
];

/* ================================================================== */
/*  HELPERS                                                            */
/* ================================================================== */

const ROLE_LABEL: Record<UserRole, string> = {
  admin: "Admin",
  medico: "Medico",
  atendente: "Atendente",
  paciente: "Paciente",
};

const ROLE_BADGE_TONE: Record<UserRole, "primary" | "success" | "info" | "neutral"> = {
  admin: "primary",
  medico: "success",
  atendente: "info",
  paciente: "neutral",
};

const STATUS_LABEL: Record<UserStatus, string> = {
  ativo: "Ativo",
  inativo: "Inativo",
  pendente: "Pendente",
};

const STATUS_BADGE_TONE: Record<UserStatus, "success" | "neutral" | "warning"> = {
  ativo: "success",
  inativo: "neutral",
  pendente: "warning",
};

function formatRelativeDate(iso: string | null): string {
  if (!iso) return "Nunca";
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMin / 60);
  const diffD = Math.floor(diffH / 24);

  if (diffMin < 60) return `Ha ${Math.max(1, diffMin)} min`;
  if (diffH < 24) return `Ha ${diffH}h`;
  if (diffD < 30) return `Ha ${diffD}d`;
  return date.toLocaleDateString("pt-BR");
}

function formatActivityTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ================================================================== */
/*  INVITE MODAL                                                       */
/* ================================================================== */

function InviteModal({
  open,
  onClose,
  csrfToken,
  onUserCreated,
}: {
  open: boolean;
  onClose: () => void;
  csrfToken: string;
  onUserCreated: () => void;
}) {
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("medico");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await createAdminUser(csrfToken, {
        username: username.trim(),
        full_name: fullName.trim() || null,
        email: email.trim() || null,
        password,
        role: role.charAt(0).toUpperCase() + role.slice(1), // "medico" -> "Medico"
      });
      setUsername("");
      setFullName("");
      setEmail("");
      setPassword("");
      setRole("medico");
      onUserCreated();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao criar usuario.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <Card variant="solid" padding="lg" className="w-full max-w-lg relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-stone-500 hover:text-stone-300 transition-colors"
        >
          <MaterialIcon icon="close" size="md" />
        </button>

        <h2 className="text-xl font-extrabold font-headline tracking-tight text-on-surface mb-1">
          Convidar Usuario
        </h2>
        <p className="text-sm text-on-surface-variant mb-6">
          Envie um convite para um novo membro da equipe.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-error/10 text-error text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
              Nome de usuario
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Ex: dr.maria"
              className="w-full glass-panel rounded-xl px-4 py-3 text-on-surface placeholder:text-stone-600 focus:outline-none focus:border-primary-container transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
              Nome completo
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ex: Dr. Maria Silva"
              className="w-full glass-panel rounded-xl px-4 py-3 text-on-surface placeholder:text-stone-600 focus:outline-none focus:border-primary-container transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@cannabia.com"
              className="w-full glass-panel rounded-xl px-4 py-3 text-on-surface placeholder:text-stone-600 focus:outline-none focus:border-primary-container transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
              Senha
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Senha do novo usuario"
              className="w-full glass-panel rounded-xl px-4 py-3 text-on-surface placeholder:text-stone-600 focus:outline-none focus:border-primary-container transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
              Papel
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full glass-panel rounded-xl px-4 py-3 text-on-surface bg-transparent focus:outline-none focus:border-primary-container transition-colors cursor-pointer"
            >
              <option value="admin">Admin</option>
              <option value="medico">Medico</option>
              <option value="atendente">Atendente</option>
              <option value="paciente">Paciente</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-8">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon="send"
            onClick={handleSubmit}
            disabled={submitting || !username.trim() || !password}
          >
            {submitting ? "Criando..." : "Enviar Convite"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */

export default function UsuariosPage() {
  const session = useApiSession();
  const csrfToken = session.data?.csrf_token ?? "";

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<"todos" | UserRole>("todos");
  const [tenantFilter, setTenantFilter] = useState<string>("todos");
  const [inviteOpen, setInviteOpen] = useState(false);

  /* ── Fetch users from API ── */
  const fetchUsers = useCallback(async () => {
    setLoadingUsers(true);
    setFetchError(null);
    try {
      const result = await listAdminUsers();
      const mapped = (result.data ?? []).map(mapBackendUser);
      setUsers(mapped);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao carregar usuarios.";
      setFetchError(msg);
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  /* ── Derive unique tenants from real data ── */
  const tenants = useMemo(() => {
    const set = new Set(users.map((u) => u.tenant));
    return Array.from(set).sort();
  }, [users]);

  /* ── Filtering ── */
  const filtered = useMemo(() => {
    return users.filter((u) => {
      const matchSearch =
        !search ||
        u.name.toLowerCase().includes(search.toLowerCase()) ||
        u.email.toLowerCase().includes(search.toLowerCase());
      const matchRole = roleFilter === "todos" || u.role === roleFilter;
      const matchTenant = tenantFilter === "todos" || u.tenant === tenantFilter;
      return matchSearch && matchRole && matchTenant;
    });
  }, [users, search, roleFilter, tenantFilter]);

  /* ── Stats ── */
  const stats = useMemo(
    () => ({
      total: users.length,
      ativos: users.filter((u) => u.status === "ativo").length,
      inativos: users.filter((u) => u.status === "inativo").length,
      pendentes: users.filter((u) => u.status === "pendente").length,
    }),
    [users],
  );

  /* ── Table columns ── */
  const columns: DataTableColumn[] = useMemo(
    () => [
      {
        key: "name",
        label: "Usuario",
        sortable: true,
        render: (_val, row) => {
          const user = row as unknown as AdminUser;
          return (
            <div className="flex items-center gap-3">
              <div className="relative">
                <Avatar name={user.name} size="md" src={user.avatar} />
                {user.status === "ativo" && (
                  <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-surface" />
                )}
              </div>
              <div>
                <p className="font-bold text-on-surface text-sm">{user.name}</p>
                <p className="text-xs text-stone-500">{user.email}</p>
              </div>
            </div>
          );
        },
      },
      {
        key: "role",
        label: "Papel",
        sortable: true,
        render: (_val, row) => {
          const user = row as unknown as AdminUser;
          return (
            <Badge tone={ROLE_BADGE_TONE[user.role]}>
              {ROLE_LABEL[user.role]}
            </Badge>
          );
        },
      },
      {
        key: "tenant",
        label: "Organizacao",
        sortable: true,
        render: (_val, row) => (
          <span className="text-sm text-on-surface-variant">
            {String(row.tenant)}
          </span>
        ),
      },
      {
        key: "status",
        label: "Status",
        sortable: true,
        render: (_val, row) => {
          const user = row as unknown as AdminUser;
          return (
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "w-2 h-2 rounded-full",
                  user.status === "ativo" &&
                    "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]",
                  user.status === "inativo" && "bg-stone-600",
                  user.status === "pendente" &&
                    "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]",
                )}
              />
              <Badge tone={STATUS_BADGE_TONE[user.status]} className="bg-transparent px-0">
                {STATUS_LABEL[user.status]}
              </Badge>
            </div>
          );
        },
      },
      {
        key: "last_login",
        label: "Ultimo Acesso",
        sortable: true,
        render: (_val, row) => {
          const user = row as unknown as AdminUser;
          return (
            <span className="text-sm text-stone-400">
              {formatRelativeDate(user.last_login)}
            </span>
          );
        },
      },
      {
        key: "actions",
        label: "Acoes",
        render: () => (
          <button className="p-2 text-stone-500 hover:text-primary transition-colors">
            <MaterialIcon icon="edit" size="md" />
          </button>
        ),
      },
    ],
    [],
  );

  const tableData = useMemo(
    () =>
      filtered.map((u) => ({
        ...u,
        id: u.id,
        name: u.name,
        role: u.role,
        tenant: u.tenant,
        status: u.status,
        last_login: u.last_login,
      })) as unknown as Record<string, unknown>[],
    [filtered],
  );

  const roleOptions: { value: "todos" | UserRole; label: string }[] = [
    { value: "todos", label: "Todos" },
    { value: "admin", label: "Admin" },
    { value: "medico", label: "Medico" },
    { value: "atendente", label: "Atendente" },
    { value: "paciente", label: "Paciente" },
  ];

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tighter text-on-surface mb-2">
            Gestao de Usuarios
            <span className="text-primary"> e Permissoes</span>
          </h1>
          <p className="text-on-surface-variant max-w-xl">
            Configure acessos, defina permissoes por papel e gerencie a equipe clinica da
            plataforma Cannab&apos;IA.
          </p>
        </div>
        <Button
          variant="primary"
          icon="person_add"
          onClick={() => setInviteOpen(true)}
          className="shrink-0"
        >
          Convidar Usuario
        </Button>
      </header>

      {/* ── Stats ── */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="group" label="Total Usuarios" value={stats.total} />
        <StatCard
          icon="check_circle"
          label="Ativos"
          value={stats.ativos}
          delta={stats.total > 0 ? `${Math.round((stats.ativos / stats.total) * 100)}%` : "0%"}
          deltaType="up"
        />
        <StatCard icon="person_off" label="Inativos" value={stats.inativos} />
        <StatCard
          icon="mail"
          label="Pendentes Convite"
          value={stats.pendentes}
          delta={String(stats.pendentes)}
          deltaType="neutral"
        />
      </section>

      {/* ── Filters ── */}
      <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar usuarios..."
          className="flex-1 max-w-md"
        />

        {/* Role filter pills */}
        <div className="flex gap-2 flex-wrap">
          {roleOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setRoleFilter(opt.value)}
              className={cn(
                "px-4 py-1.5 rounded-full text-xs font-bold transition-all",
                roleFilter === opt.value
                  ? "bg-primary text-on-primary"
                  : "text-stone-400 hover:bg-white/5",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Tenant filter */}
        <div className="glass-panel px-4 py-2 rounded-full flex items-center gap-2 text-sm">
          <MaterialIcon icon="apartment" size="sm" className="text-primary" />
          <select
            value={tenantFilter}
            onChange={(e) => setTenantFilter(e.target.value)}
            className="bg-transparent border-none focus:ring-0 text-on-surface cursor-pointer font-medium text-sm"
          >
            <option value="todos">Todas as Organizacoes</option>
            {tenants.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Main content grid ── */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
        {/* User Table */}
        <section className="xl:col-span-8">
          <div className="glass-panel rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-white/5 bg-white/5 flex items-center justify-between">
              <span className="text-sm text-stone-500">
                {loadingUsers
                  ? "Carregando usuarios..."
                  : `Mostrando ${filtered.length} de ${users.length} usuarios`}
              </span>
            </div>

            {loadingUsers ? (
              <div className="flex items-center justify-center py-20">
                <div className="flex flex-col items-center gap-4">
                  <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  <p className="text-sm text-stone-500">Carregando usuarios...</p>
                </div>
              </div>
            ) : fetchError ? (
              <div className="flex flex-col items-center justify-center py-20 gap-4">
                <MaterialIcon icon="error" size="lg" className="text-error" />
                <p className="text-sm text-error">{fetchError}</p>
                <Button variant="ghost" size="sm" icon="refresh" onClick={fetchUsers}>
                  Tentar novamente
                </Button>
              </div>
            ) : (
              <DataTable
                columns={columns}
                data={tableData}
                emptyMessage="Nenhum usuario encontrado."
                className="rounded-none border-none"
              />
            )}
          </div>
        </section>

        {/* Permissions Matrix + Activity */}
        <section className="xl:col-span-4 space-y-6">
          {/* Permissions matrix */}
          <Card variant="glass" padding="md" className="overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-extrabold font-headline tracking-tight text-on-surface">
                Matriz de Permissoes
              </h2>
              <MaterialIcon icon="admin_panel_settings" className="text-primary" />
            </div>
            <p className="text-xs text-on-surface-variant mb-6 leading-relaxed">
              Visao geral dos privilegios de acesso por papel.
            </p>

            {/* Matrix table */}
            <div className="overflow-x-auto -mx-6 px-6">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="py-2 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                      Modulo
                    </th>
                    {(["admin", "medico", "atendente"] as UserRole[]).map(
                      (role) => (
                        <th
                          key={role}
                          className="py-2 text-[10px] font-bold uppercase tracking-widest text-stone-500 text-center"
                        >
                          {ROLE_LABEL[role]}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {(Object.keys(PERMISSION_LABELS) as PermissionKey[]).map(
                    (perm) => (
                      <tr
                        key={perm}
                        className="hover:bg-white/5 transition-colors"
                      >
                        <td className="py-3 text-sm text-on-surface">
                          {PERMISSION_LABELS[perm]}
                        </td>
                        {(["admin", "medico", "atendente"] as UserRole[]).map(
                          (role) => (
                            <td key={role} className="py-3 text-center">
                              {ROLE_PERMISSIONS[role][perm] ? (
                                <MaterialIcon
                                  icon="check_circle"
                                  filled
                                  size="sm"
                                  className="text-primary"
                                />
                              ) : (
                                <MaterialIcon
                                  icon="cancel"
                                  size="sm"
                                  className="text-stone-600"
                                />
                              )}
                            </td>
                          ),
                        )}
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Recent activity */}
          <Card variant="glass" padding="md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-extrabold font-headline tracking-tight text-on-surface">
                Atividade Recente
              </h2>
              <MaterialIcon icon="history" className="text-primary" />
            </div>

            <div className="space-y-3 max-h-[400px] overflow-y-auto">
              {MOCK_ACTIVITY.map((evt) => (
                <div
                  key={evt.id}
                  className="flex items-start gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                >
                  <div
                    className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                      evt.type === "login" && "bg-primary/10",
                      evt.type === "invite" && "bg-blue-400/10",
                      evt.type === "role_change" && "bg-amber-400/10",
                      evt.type === "deactivation" && "bg-error/10",
                    )}
                  >
                    <MaterialIcon
                      icon={evt.icon}
                      size="sm"
                      className={cn(
                        evt.type === "login" && "text-primary",
                        evt.type === "invite" && "text-blue-400",
                        evt.type === "role_change" && "text-amber-400",
                        evt.type === "deactivation" && "text-error",
                      )}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-on-surface leading-snug">
                      {evt.description}
                    </p>
                    <p className="text-[10px] text-stone-500 mt-1">
                      {formatActivityTime(evt.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </section>
      </div>

      {/* ── Invite Modal ── */}
      <InviteModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        csrfToken={csrfToken}
        onUserCreated={fetchUsers}
      />
    </div>
  );
}
