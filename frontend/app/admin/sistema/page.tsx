"use client";

import Link from "next/link";
import { Card, MaterialIcon } from "@/components/ui-tw";

/**
 * Placeholder de /admin/sistema enquanto a area de "Configuracoes do
 * Sistema" e movida para a aba consolidada em /org/configuracoes (Fase A2).
 *
 * Antes da Fase A2 final, esta pagina existe para evitar 404 do item de
 * sidebar "Sistema" no painel admin. Apos A2 a integracao completa
 * substitui esta tela ou redireciona.
 */
export default function AdminSistemaPlaceholder() {
  return (
    <section className="p-4 md:p-8 space-y-6">
      <div>
        <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
          Sistema e Configuracoes
        </h2>
        <p className="text-stone-500 font-medium text-sm mt-1">Em reorganizacao</p>
      </div>

      <Card variant="glass" padding="lg" className="space-y-4 max-w-2xl">
        <div className="flex items-start gap-4">
          <MaterialIcon icon="construction" size="lg" className="text-amber-400" />
          <div className="space-y-2">
            <h3 className="text-lg font-bold text-on-surface font-headline">Em consolidacao</h3>
            <p className="text-sm text-stone-400 leading-relaxed">
              As configuracoes do sistema estao sendo agrupadas no painel da clinica/associacao em
              uma area unica. Quando concluido, esta tela vai abrir automaticamente a aba certa em{" "}
              <code className="text-primary">/org/configuracoes</code> de acordo com o seu papel.
            </p>
            <p className="text-xs text-stone-500 mt-3">
              Sprint atual: Fase A2 (refatoracao do app unificado).
            </p>
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/admin"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg glass-panel hover:bg-white/5 text-sm font-medium text-on-surface transition-colors"
        >
          <MaterialIcon icon="arrow_back" size="sm" />
          Voltar ao Painel
        </Link>
        <Link
          href="/admin/agentes"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg glass-panel hover:bg-white/5 text-sm font-medium text-on-surface transition-colors"
        >
          <MaterialIcon icon="smart_toy" size="sm" />
          Agentes IA
        </Link>
        <Link
          href="/admin/knowledge"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg glass-panel hover:bg-white/5 text-sm font-medium text-on-surface transition-colors"
        >
          <MaterialIcon icon="library_books" size="sm" />
          Base Cientifica
        </Link>
      </div>
    </section>
  );
}
