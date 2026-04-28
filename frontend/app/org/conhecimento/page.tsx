"use client";

import { KnowledgeBaseView } from "@/components/knowledge/knowledge-base-view";

/**
 * Base Cientifica do tenant — pool global colaborativo.
 *
 * Acessivel por: Admin global, AdminClinica e Medico.
 * (Recepcao, Financeiro e Paciente bloqueados no backend.)
 *
 * /admin/knowledge mantem a UI completa com gestao de monitors —
 * esta pagina e a versao focada em busca/leitura/adicao para os
 * profissionais credenciados do tenant.
 */
export default function ConhecimentoTenantPage() {
  return <KnowledgeBaseView />;
}
