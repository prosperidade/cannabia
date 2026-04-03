"use client";

import { useSystemStatus } from "@/lib/use-system-status";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";

function StatCard({
  label,
  value,
  delta,
}: {
  label: string;
  value: string | number;
  delta?: { label: string; direction: "up" | "down" };
}) {
  return (
    <div className="ds-stat">
      <span className="ds-stat__label">{label}</span>
      <span className="ds-stat__value">{value}</span>
      {delta ? (
        <span className={`ds-stat__delta ds-stat__delta--${delta.direction}`}>
          {delta.direction === "up" ? "↑" : "↓"} {delta.label}
        </span>
      ) : null}
    </div>
  );
}

export default function AdminOverviewPage() {
  const status = useSystemStatus();

  return (
    <>
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Administração</p>
          <h1>Visão geral da plataforma</h1>
          <p className="lead">
            Painel B2B para gestão de tenants, clínicas e saúde do sistema.
          </p>
        </div>
        <Button asChild variant="secondary" size="sm">
          <Link href="/admin/tenants">Gerenciar tenants</Link>
        </Button>
      </header>

      {/* KPIs */}
      <section aria-label="Métricas da plataforma" className="ds-stat-row">
        <StatCard label="Tenants ativos" value="—" />
        <StatCard label="Clínicas" value="—" />
        <StatCard label="Usuários" value="—" />
        <StatCard label="Execuções IA (hoje)" value="—" />
      </section>

      {/* System health */}
      <section aria-label="Saúde do sistema" className="ds-admin-grid">
        <Card>
          <CardHeader
            eyebrow="Infraestrutura"
            title="Saúde dos componentes"
            subtitle="Dados vindos do health check em tempo real (/api/v1/health)"
            actions={
              <Button onClick={status.refresh} size="sm" variant="ghost">
                Atualizar
              </Button>
            }
          />
          {Object.keys(status.components).length > 0 ? (
            <div style={{ display: "grid", gap: "10px" }}>
              {Object.entries(status.components).map(([name, comp]) => (
                <div
                  key={name}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 14px",
                    borderRadius: "12px",
                    border: "1px solid var(--line)",
                    background: "rgba(255,255,255,0.02)",
                  }}
                >
                  <span style={{ fontWeight: 600, fontSize: "14px" }}>{name}</span>
                  <span style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    {comp.latency_ms != null ? (
                      <span className="mono" style={{ fontSize: "12px", color: "var(--muted)" }}>
                        {comp.latency_ms}ms
                      </span>
                    ) : null}
                    <Badge
                      pulse={comp.status !== "healthy"}
                      tone={
                        comp.status === "healthy"
                          ? "success"
                          : comp.status === "degraded"
                            ? "warning"
                            : "danger"
                      }
                    >
                      {comp.status}
                    </Badge>
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="lead">
              {status.overall === "unknown"
                ? "Verificando conexão com o backend..."
                : "Nenhum dado de componentes disponível."}
            </p>
          )}
          {status.lastChecked ? (
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>
              Última verificação: {status.lastChecked.toLocaleTimeString("pt-BR")}
            </span>
          ) : null}
        </Card>

        <Card>
          <CardHeader
            eyebrow="Plataforma"
            title="Próximas capacidades"
            subtitle="Features da Fase 5 em preparação no backend"
          />
          <div style={{ display: "grid", gap: "12px" }}>
            {[
              { label: "Onboarding de Tenants (5.2)", status: "Em desenvolvimento" },
              { label: "Billing / Planos (5.3)", status: "Em desenvolvimento" },
              { label: "Templates de Campanhas (5.4)", status: "Planejado" },
              { label: "Modo Degradação Graceful (5.5)", status: "Frontend pronto" },
            ].map((item) => (
              <div
                key={item.label}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "14px",
                }}
              >
                <span>{item.label}</span>
                <Badge tone={item.status === "Frontend pronto" ? "success" : "info"}>
                  {item.status}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
