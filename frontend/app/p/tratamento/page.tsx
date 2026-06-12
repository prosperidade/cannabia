"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { getPatientTreatment } from "@/lib/api";
import { Card, Badge, MaterialIcon, ProgressBar, Button } from "@/components/ui-tw";

type Protocol = {
  id: number;
  name: string;
  status: string | null;
  phase: string | null;
  start_date: string | null;
  product: string | null;
  concentration: string | null;
  route: string | null;
  dose: string | null;
  frequency: string | null;
  cbd_ratio: number;
  thc_ratio: number;
  bottle_remaining: number | null;
  bottle_end_estimate: string | null;
  duration_days?: number | null;
};

type ScheduleSlot = {
  period: string;
  icon: string;
  time: string;
  dose: string;
  taken: boolean;
};

type Instructions = {
  doctor: string | null;
  notes: string | null;
  precautions: string[];
};

type Monitoring = {
  observe: string[];
  contact_when: string[];
};

type HistoryEntry = {
  date: string;
  change: string;
  reason: string;
};

type TreatmentData = {
  protocol: Protocol | null;
  schedule: ScheduleSlot[];
  instructions: Instructions;
  monitoring: Monitoring;
  history: HistoryEntry[];
};

export default function TratamentoPage() {
  const [data, setData] = useState<TreatmentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const res = await getPatientTreatment();
        if (cancelled) return;
        setData(res.data as unknown as TreatmentData);
      } catch {
        if (!cancelled)
          setError("Nao foi possivel carregar o tratamento. Tente novamente mais tarde.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchData();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando tratamento...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-md mx-auto py-16 text-center">
        <MaterialIcon icon="cloud_off" size="xl" className="text-error/50 mb-4" />
        <p className="text-on-surface-variant text-sm">
          {error ?? "Nenhum tratamento encontrado."}
        </p>
      </div>
    );
  }

  const protocol = data.protocol;
  if (!protocol) {
    return (
      <div className="max-w-md mx-auto py-16 text-center">
        <MaterialIcon icon="medication" size="xl" className="text-primary/40 mb-4" />
        <p className="text-on-surface-variant text-sm">
          Nenhum plano terapeutico ativo foi encontrado.
        </p>
      </div>
    );
  }

  const schedule = data.schedule ?? [];
  const instructions = data.instructions;
  const monitoring = data.monitoring;
  const history = data.history ?? [];
  const progress = protocol.bottle_remaining;
  const ratioTotal = protocol.cbd_ratio + protocol.thc_ratio;
  const hasRatio = ratioTotal > 0;
  const nextDose = schedule.find((slot) => !slot.taken) ?? schedule[0];
  const hasInstructions =
    Boolean(instructions?.notes) || (instructions?.precautions?.length ?? 0) > 0;
  const hasMonitoring =
    (monitoring?.observe?.length ?? 0) > 0 || (monitoring?.contact_when?.length ?? 0) > 0;

  return (
    <div className="max-w-md mx-auto space-y-6">
      {/* ── Header ── */}
      <section>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-headline font-extrabold tracking-tight text-on-surface">
            Meu Plano Terapeutico
          </h1>
          {protocol.status && <Badge tone="success">{protocol.status}</Badge>}
        </div>
        <p className="text-on-surface-variant text-sm mt-1">{protocol.name}</p>
      </section>

      {/* ── Next Dose Countdown ── */}
      {nextDose && (
        <Card variant="solid" padding="md" className="relative overflow-hidden">
          <div className="absolute -right-10 -top-10 w-32 h-32 bg-primary/20 blur-3xl rounded-full" />
          <div className="flex justify-between items-start mb-4 relative z-10">
            <div>
              <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                Proxima Dose
              </span>
              <h2 className="text-3xl font-extrabold tracking-tight text-primary mt-1 font-headline">
                {nextDose.time || nextDose.period}
              </h2>
              {nextDose.dose && (
                <p className="text-xs text-on-surface-variant mt-1">{nextDose.dose}</p>
              )}
            </div>
            <Badge tone={nextDose.taken ? "success" : "primary"}>
              {nextDose.taken ? "Registrada" : "Pendente"}
            </Badge>
          </div>
          <ProgressBar value={nextDose.taken ? 100 : 0} variant="primary" size="sm" />
        </Card>
      )}

      {/* ── CBD/THC Ratio Visual ── */}
      {hasRatio && (
        <Card variant="glass" padding="md" className="space-y-4">
          <h3 className="font-headline font-bold text-lg">Proporcao CBD:THC</h3>
          <div className="flex items-end gap-6 justify-center py-4">
            <div className="flex flex-col items-center">
              <span className="text-5xl font-black text-primary font-headline">
                {protocol.cbd_ratio}
              </span>
              <span className="text-xs font-bold text-primary mt-1">CBD</span>
            </div>
            <span className="text-2xl font-bold text-on-surface-variant pb-2">:</span>
            <div className="flex flex-col items-center">
              <span className="text-5xl font-black text-secondary font-headline">
                {protocol.thc_ratio}
              </span>
              <span className="text-xs font-bold text-secondary mt-1">THC</span>
            </div>
          </div>
          <div className="flex gap-1 h-3 rounded-full overflow-hidden">
            <div
              className="bg-primary rounded-l-full transition-all"
              style={{
                width: `${(protocol.cbd_ratio / ratioTotal) * 100}%`,
              }}
            />
            <div
              className="bg-secondary rounded-r-full transition-all"
              style={{
                width: `${(protocol.thc_ratio / ratioTotal) * 100}%`,
              }}
            />
          </div>
        </Card>
      )}

      {/* ── Dosage Details ── */}
      <Card variant="glass" padding="md" className="space-y-4">
        <h3 className="font-headline font-bold text-lg">Detalhes da Posologia</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-surface-container/40 p-4 rounded-lg border border-outline-variant/20">
            <div className="flex items-center gap-2 mb-2">
              <MaterialIcon icon="vaccines" size="sm" className="text-primary" />
              <span className="text-xs font-medium text-on-surface-variant">Produto</span>
            </div>
            <p className="text-sm font-bold">{protocol.product ?? "Nao informado"}</p>
          </div>
          <div className="bg-surface-container/40 p-4 rounded-lg border border-outline-variant/20">
            <div className="flex items-center gap-2 mb-2">
              <MaterialIcon icon="science" size="sm" className="text-primary" />
              <span className="text-xs font-medium text-on-surface-variant">Concentracao</span>
            </div>
            <p className="text-sm font-bold">{protocol.concentration ?? "Nao informada"}</p>
          </div>
          <div className="bg-surface-container/40 p-4 rounded-lg border border-outline-variant/20">
            <div className="flex items-center gap-2 mb-2">
              <MaterialIcon icon="water_drop" size="sm" className="text-primary" />
              <span className="text-xs font-medium text-on-surface-variant">Dosagem</span>
            </div>
            <p className="text-xl font-bold">{protocol.dose ?? "Nao informada"}</p>
          </div>
          <div className="bg-surface-container/40 p-4 rounded-lg border border-outline-variant/20">
            <div className="flex items-center gap-2 mb-2">
              <MaterialIcon icon="schedule" size="sm" className="text-primary" />
              <span className="text-xs font-medium text-on-surface-variant">Frequencia</span>
            </div>
            <p className="text-xl font-bold">{protocol.frequency ?? "Nao informada"}</p>
          </div>
        </div>
        <div className="bg-surface-container/40 p-4 rounded-lg border border-outline-variant/20">
          <div className="flex items-center gap-2 mb-2">
            <MaterialIcon icon="route" size="sm" className="text-primary" />
            <span className="text-xs font-medium text-on-surface-variant">
              Via de Administracao
            </span>
          </div>
          <p className="text-sm font-bold">{protocol.route ?? "Nao informada"}</p>
        </div>
      </Card>

      {/* ── Daily Schedule ── */}
      {schedule.length > 0 && (
        <Card variant="glass" padding="md" className="space-y-4">
          <h3 className="font-headline font-bold text-lg">Horarios do Dia</h3>
          <div className="space-y-3">
            {schedule.map((slot) => (
              <div
                key={slot.period}
                className={cn(
                  "flex items-center justify-between p-4 rounded-xl border transition-colors",
                  slot.taken
                    ? "bg-primary/5 border-primary/20"
                    : "bg-surface-container/40 border-outline-variant/20",
                )}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      "w-10 h-10 rounded-full flex items-center justify-center",
                      slot.taken ? "bg-primary/20" : "bg-surface-container-highest",
                    )}
                  >
                    <MaterialIcon
                      icon={slot.icon}
                      className={slot.taken ? "text-primary" : "text-on-surface-variant"}
                    />
                  </div>
                  <div>
                    <p className="text-sm font-bold">{slot.period}</p>
                    <p className="text-xs text-on-surface-variant">
                      {slot.time} &bull; {slot.dose}
                    </p>
                  </div>
                </div>
                {slot.taken ? (
                  <MaterialIcon icon="check_circle" filled className="text-primary" />
                ) : (
                  <Badge tone="warning">Pendente</Badge>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Bottle Status ── */}
      {progress !== null && (
        <Card variant="glass" padding="md" className="space-y-3">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <MaterialIcon icon="vaccines" size="sm" className="text-primary" />
              <span className="text-sm font-medium">Status do Frasco</span>
            </div>
            <span className="text-xs font-bold text-primary">{progress}% restante</span>
          </div>
          <div className="flex gap-1 h-2">
            {[1, 2, 3, 4, 5].map((seg) => (
              <div
                key={seg}
                className={cn(
                  "flex-1 rounded-sm",
                  seg <= Math.ceil(progress / 20) ? "bg-primary" : "bg-primary/20",
                  seg === 1 && "rounded-l-full",
                  seg === 5 && "rounded-r-full",
                )}
              />
            ))}
          </div>
          {protocol.bottle_end_estimate && (
            <p className="text-[10px] text-on-surface-variant leading-relaxed">
              Estimativa de termino: {protocol.bottle_end_estimate}.
            </p>
          )}
        </Card>
      )}

      {/* ── Doctor Instructions ── */}
      {hasInstructions && (
        <Card variant="glass" padding="md" className="space-y-4">
          <h3 className="font-headline font-bold text-lg">Orientacoes</h3>
          <div className="bg-secondary-container/10 border border-secondary/20 rounded-xl p-4 flex gap-4">
            <div className="shrink-0">
              <div className="w-10 h-10 rounded-full bg-secondary/20 flex items-center justify-center">
                <MaterialIcon icon="person" className="text-secondary" />
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] font-bold uppercase tracking-tighter text-secondary">
                Instrucoes {instructions.doctor ? `de ${instructions.doctor}` : "da equipe clinica"}
              </p>
              {instructions.notes && (
                <p className="text-sm italic text-on-surface leading-snug">
                  &ldquo;{instructions.notes}&rdquo;
                </p>
              )}
            </div>
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
              Precaucoes
            </p>
            {instructions.precautions.length > 0 && (
              <ul className="space-y-2">
                {instructions.precautions.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-on-surface">
                    <MaterialIcon icon="warning" size="sm" className="text-amber-400 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      )}

      {/* ── Monitoring ── */}
      {hasMonitoring && (
        <Card variant="glass" padding="md" className="space-y-4">
          <h3 className="font-headline font-bold text-lg">Monitoramento</h3>
          {monitoring.observe.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                O que observar
              </p>
              <ul className="space-y-2">
                {monitoring.observe.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-on-surface">
                    <MaterialIcon icon="visibility" size="sm" className="text-primary mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {monitoring.contact_when.length > 0 && (
            <div className="pt-3 border-t border-white/5">
              <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                Quando entrar em contato
              </p>
              <ul className="space-y-2">
                {monitoring.contact_when.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-on-surface">
                    <MaterialIcon icon="emergency" size="sm" className="text-error mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {/* ── Dosage History ── */}
      {history.length > 0 && (
        <section className="space-y-4 pb-4">
          <h2 className="font-headline font-bold text-lg">Historico de Ajustes</h2>
          <div className="space-y-3">
            {history.map((entry, i) => (
              <Card key={i} variant="solid" padding="sm" className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-on-surface-variant">{entry.date}</span>
                  {i === 0 && <Badge tone="neutral">Inicio</Badge>}
                  {i > 0 && <Badge tone="primary">Ajuste</Badge>}
                </div>
                <p className="text-sm font-bold text-on-surface">{entry.change}</p>
                <p className="text-xs text-on-surface-variant">{entry.reason}</p>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* ── Action Buttons ── */}
      <div className="space-y-3 pb-4">
        <Button icon="check_circle" className="w-full rounded-full">
          Confirmar Dose Agora
        </Button>
        <Button variant="secondary" icon="sentiment_satisfied" className="w-full rounded-full">
          Registrar Como Estou
        </Button>
      </div>
    </div>
  );
}
