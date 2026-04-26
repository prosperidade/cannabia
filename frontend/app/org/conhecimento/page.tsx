"use client";

import Link from "next/link";
import { Card, MaterialIcon } from "@/components/ui-tw";

/**
 * Base Cientifica para o tenant.
 *
 * Placeholder ate a Fase A2 final unificar a base de conhecimento
 * (artigos PubMed/Cochrane + legislacao via Google Files API) em uma
 * UI propria escopada ao tenant. Hoje a UI completa esta em
 * /admin/knowledge mas e visivel apenas pelo super admin.
 *
 * Acessivel por: Medico, AdminClinica (e Admin global, embora esse
 * ja tenha a versao /admin/knowledge).
 */
export default function ConhecimentoTenantPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl md:text-3xl font-headline font-extrabold tracking-tight text-on-surface">
          Base Cientifica
        </h1>
        <p className="text-sm text-stone-500 mt-1">
          Pesquisa em artigos cientificos, legislacao ANVISA/CFM e evidencias clinicas.
        </p>
      </header>

      <Card variant="glass" padding="lg" className="space-y-4">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary/15 flex items-center justify-center flex-shrink-0">
            <MaterialIcon icon="library_books" className="text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-bold font-headline text-on-surface">
              Em construcao
            </h3>
            <p className="text-sm text-stone-400 mt-1 leading-relaxed">
              A versao da base cientifica escopada para clinicas, associacoes e medicos
              esta sendo finalizada na proxima sprint. Vai incluir busca em PubMed/Cochrane,
              consulta integrada a legislacao (RDC 327, RDC 660, resolucoes CFM) e citacao
              automatica nos relatorios clinicos via agente Cientifico.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            href="/admin/knowledge"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg glass-panel hover:bg-white/5 text-sm font-medium text-on-surface transition-colors"
          >
            <MaterialIcon icon="open_in_new" size="sm" />
            Acessar versao do super admin
          </Link>
          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
            <MaterialIcon icon="info" size="sm" />
            Acesso restrito ao perfil Admin global por enquanto
          </span>
        </div>
      </Card>

      <Card padding="lg" className="bg-primary/5 border-primary/15">
        <div className="flex items-start gap-3">
          <MaterialIcon icon="auto_awesome" className="text-primary flex-shrink-0 mt-1" />
          <div className="text-sm text-stone-400 leading-relaxed">
            <p className="font-bold text-primary mb-1">Como o agente Cientifico vai usar isso</p>
            Ao gerar parecer clinico ou relatorio regulatorio, o agente consulta artigos da
            base e cita evidencias com link para a fonte original. A configuracao do tom de
            citacao fica em <em>Configuracoes &rarr; DNA do Negocio</em>.
          </div>
        </div>
      </Card>
    </section>
  );
}
