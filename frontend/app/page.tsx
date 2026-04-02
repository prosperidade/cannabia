import Link from "next/link";

export default function HomePage() {
  return (
    <div className="marketing-shell">
      <section className="hero-panel">
        <div className="hero-grid">
          <div>
            <p className="hero-kicker">Next.js migration runway</p>
            <h1 className="hero-title">Novo frontend da CannabIA, iniciado sem travar o backend.</h1>
            <p className="hero-copy">
              Este bootstrap ja nasce orientado a sessao, atendimento, timeline e prontuario.
              A camada Flask continua como backend de dominio e a interface passa a
              evoluir aqui.
            </p>
            <div className="hero-actions">
              <Link className="button-primary" href="/dashboard">
                Entrar no cockpit
              </Link>
              <Link className="button-secondary" href="/agendamentos">
                Ver agenda
              </Link>
            </div>
          </div>

          <div className="support-card">
            <strong>Primeira entrega do frontend novo</strong>
            <p className="support-copy">
              Shell autenticado, login por sessao/cookie e jornada clinica inicial dos
              atendimentos integrados a API v1.
            </p>
            <div className="hero-metrics">
              <div className="metric-card">
                <span>Stack</span>
                <strong>Next.js</strong>
              </div>
              <div className="metric-card">
                <span>Contrato</span>
                <strong>API v1</strong>
              </div>
              <div className="metric-card">
                <span>Entrada</span>
                <strong>Login</strong>
              </div>
              <div className="metric-card">
                <span>Dominio</span>
                <strong>Dashboard</strong>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
