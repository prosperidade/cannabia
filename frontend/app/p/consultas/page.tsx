"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPatientAppointments } from "@/lib/api";
import {
  Card,
  Badge,
  MaterialIcon,
} from "@/components/ui-tw";

type Appointment = {
  id: number;
  date: string;
  time: string;
  iso: string;
  status: string;
  doctor: string;
  modality: string;
  notes: string | null;
};

type AppointmentsData = {
  upcoming: Appointment[];
  past: Appointment[];
};

function statusTone(status: string): "primary" | "success" | "warning" | "danger" | "neutral" {
  const s = status.toLowerCase();
  if (s.includes("conclu") || s.includes("realiz") || s.includes("atendid")) return "success";
  if (s.includes("cancel")) return "danger";
  if (s.includes("aguard") || s.includes("pendent")) return "warning";
  return "primary";
}

function ApptCard({ appt }: { appt: Appointment }) {
  return (
    <Card variant="glass" padding="md" className="space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-primary/80">
            {appt.modality}
          </p>
          <h3 className="text-lg font-headline font-bold mt-1">
            {appt.date}
          </h3>
          <p className="text-sm text-on-surface-variant">
            {appt.time} &bull; {appt.doctor}
          </p>
        </div>
        <Badge tone={statusTone(appt.status)}>{appt.status}</Badge>
      </div>
      {appt.notes && (
        <p className="text-xs text-on-surface-variant border-t border-white/5 pt-3">
          {appt.notes}
        </p>
      )}
    </Card>
  );
}

export default function PatientConsultasPage() {
  const [data, setData] = useState<AppointmentsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const res = await getPatientAppointments();
        if (cancelled) return;
        const payload = res.data as AppointmentsData;
        setData(payload);
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar suas consultas.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchData();
    return () => { cancelled = true; };
  }, []);

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
          Minhas Consultas
        </h1>
        <p className="text-on-surface-variant text-sm mt-1">
          Agendamentos e histórico de atendimentos.
        </p>
      </section>

      {/* CTA: contato imediato */}
      <Card variant="glass" padding="md" className="border-primary/20">
        <div className="flex items-center gap-4">
          <div className="bg-primary/20 p-3 rounded-full">
            <MaterialIcon icon="support_agent" className="text-primary" />
          </div>
          <div className="flex-1">
            <h4 className="font-bold text-on-surface text-sm">Precisa de ajuda agora?</h4>
            <p className="text-on-surface-variant text-xs mt-1">
              Entre em contato com a recepção da sua clínica para suporte imediato.
            </p>
          </div>
        </div>
      </Card>

      {loading && (
        <div className="flex items-center justify-center py-10">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
      )}

      {error && !loading && (
        <Card variant="glass" padding="md">
          <div className="text-center text-sm text-on-surface-variant">
            <MaterialIcon icon="cloud_off" size="lg" className="text-error/50 mb-2" />
            <p>{error}</p>
          </div>
        </Card>
      )}

      {!loading && !error && data && (
        <>
          <section className="space-y-4">
            <h2 className="font-headline font-bold text-lg flex items-center gap-2">
              <MaterialIcon icon="event_upcoming" size="sm" className="text-primary" />
              Próximas
            </h2>
            {data.upcoming.length === 0 ? (
              <Card variant="glass" padding="md">
                <p className="text-sm text-on-surface-variant text-center">
                  Você não tem consultas agendadas.
                </p>
              </Card>
            ) : (
              <div className="space-y-3">
                {data.upcoming.map((a) => <ApptCard key={a.id} appt={a} />)}
              </div>
            )}
          </section>

          <section className="space-y-4 pb-4">
            <h2 className="font-headline font-bold text-lg flex items-center gap-2">
              <MaterialIcon icon="history" size="sm" className="text-on-surface-variant" />
              Histórico
            </h2>
            {data.past.length === 0 ? (
              <Card variant="glass" padding="md">
                <p className="text-sm text-on-surface-variant text-center">
                  Nenhum atendimento anterior registrado.
                </p>
              </Card>
            ) : (
              <div className="space-y-3">
                {data.past.map((a) => <ApptCard key={a.id} appt={a} />)}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
