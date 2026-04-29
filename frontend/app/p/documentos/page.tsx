"use client";

import Link from "next/link";
import {
  Card,
  MaterialIcon,
} from "@/components/ui-tw";

type DocCategory = {
  key: string;
  title: string;
  description: string;
  icon: string;
  color: string;
};

const CATEGORIES: DocCategory[] = [
  {
    key: "receitas",
    title: "Receitas",
    description: "Prescrições emitidas pelo seu médico.",
    icon: "medication",
    color: "text-secondary",
  },
  {
    key: "atestados",
    title: "Atestados",
    description: "Documentos clínicos para empresa, escola ou seguro.",
    icon: "description",
    color: "text-primary",
  },
  {
    key: "exames",
    title: "Exames",
    description: "Resultados laboratoriais e exames de imagem.",
    icon: "biotech",
    color: "text-tertiary",
  },
  {
    key: "contratos",
    title: "Termos e contratos",
    description: "Termo de consentimento, contrato com a clínica.",
    icon: "draw",
    color: "text-primary",
  },
];

export default function PatientDocumentosPage() {
  return (
    <div className="max-w-md mx-auto space-y-6">
      <section>
        <Link
          href="/p/dashboard"
          className="inline-flex items-center gap-1 text-xs text-on-surface-variant hover:text-primary"
        >
          <MaterialIcon icon="arrow_back" size="sm" />
          Voltar
        </Link>
        <h1 className="text-2xl font-headline font-extrabold tracking-tight text-on-surface mt-2">
          Meus Documentos
        </h1>
        <p className="text-on-surface-variant text-sm mt-1">
          Documentos clínicos e administrativos da sua jornada.
        </p>
      </section>

      <Card variant="glass" padding="md" className="border-primary/20">
        <div className="flex items-center gap-4">
          <div className="bg-primary/20 p-3 rounded-full">
            <MaterialIcon icon="schedule" className="text-primary" />
          </div>
          <div className="flex-1">
            <h4 className="font-bold text-on-surface text-sm">
              Em construção
            </h4>
            <p className="text-on-surface-variant text-xs mt-1">
              A central de documentos está sendo preparada. Por enquanto, peça à recepção da sua clínica.
            </p>
          </div>
        </div>
      </Card>

      <section className="space-y-4 pb-4">
        <h2 className="font-headline font-bold text-lg">Categorias previstas</h2>
        <div className="grid grid-cols-1 gap-3">
          {CATEGORIES.map((cat) => (
            <Card
              key={cat.key}
              variant="glass"
              padding="md"
              className="opacity-60"
            >
              <div className="flex items-center gap-4">
                <div className="bg-surface-container/40 p-3 rounded-lg">
                  <MaterialIcon icon={cat.icon} className={cat.color} />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-on-surface text-sm">{cat.title}</h3>
                  <p className="text-on-surface-variant text-xs mt-1">
                    {cat.description}
                  </p>
                </div>
                <MaterialIcon icon="lock" size="sm" className="text-on-surface-variant/50" />
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
