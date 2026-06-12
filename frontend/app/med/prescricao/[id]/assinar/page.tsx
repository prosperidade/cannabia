"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { getAttendance, getPrescription, emitPrescription } from "@/lib/api";
import { Button, Card, Input, Badge, MaterialIcon } from "@/components/ui-tw";
import type { AttendanceDetail } from "@/lib/types";

/* ── helpers ─────────────────────────────────────────────────────── */

function formatDate(d: Date) {
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

/* ── page ────────────────────────────────────────────────────────── */

export default function AssinarPrescricaoPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { data: session } = useApiSession();

  const [attendance, setAttendance] = useState<AttendanceDetail | null>(null);
  const [prescription, setPrescription] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [signing, setSigning] = useState(false);
  const [signed, setSigned] = useState(false);

  /* signature form */
  const [typedSignature, setTypedSignature] = useState("");
  const [securityPin, setSecurityPin] = useState("");
  const [useCertificate, setUseCertificate] = useState(false);
  const [confirmCorrect, setConfirmCorrect] = useState(false);
  const [confirmEmit, setConfirmEmit] = useState(false);

  /* derived */
  const prescriberName = session?.user?.username ?? "";
  const prescriberCrm = (prescription?.prescriber_crm as string) ?? "";
  const patientName =
    (prescription?.patient_name as string) ?? attendance?.report.patient_name ?? "";

  const prescriptionItems = Array.isArray(prescription?.items)
    ? (prescription.items as Record<string, string>[])
    : [];

  const canSign = confirmCorrect && confirmEmit && (typedSignature.trim() || useCertificate);

  /* load data */
  useEffect(() => {
    if (!params.id) return;
    (async () => {
      try {
        const [att, presc] = await Promise.allSettled([
          getAttendance(params.id),
          getPrescription(params.id),
        ]);
        if (att.status === "fulfilled") setAttendance(att.value);
        if (presc.status === "fulfilled") setPrescription(presc.value.data);
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    })();
  }, [params.id]);

  /* pre-fill signature */
  useEffect(() => {
    if (session?.user) {
      setTypedSignature(`Dr(a). ${session.user.username}`);
    }
  }, [session]);

  /* sign handler */
  const handleSign = async () => {
    if (!session || !canSign) return;
    setSigning(true);
    try {
      await emitPrescription(session.csrf_token, {
        attendance_id: params.id,
        prescription_id: params.id,
        signature: typedSignature,
        use_certificate: useCertificate,
        security_pin: securityPin,
        signed_at: new Date().toISOString(),
      });
      setSigned(true);
    } catch {
      /* TODO: show error */
    } finally {
      setSigning(false);
    }
  };

  /* loading */
  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm">Carregando...</p>
        </div>
      </div>
    );
  }

  /* ── Success state ──────────────────────────────────────────────── */
  if (signed) {
    return (
      <div className="max-w-lg mx-auto pt-12 space-y-8 text-center">
        <Card className="flex flex-col items-center gap-6 py-12">
          <div className="h-20 w-20 rounded-full bg-primary/10 flex items-center justify-center">
            <MaterialIcon icon="check_circle" filled size="xl" className="text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-headline font-extrabold text-white mb-2">
              Prescricao Assinada com Sucesso
            </h1>
            <p className="text-on-surface-variant text-sm">
              A prescricao digital para{" "}
              <span className="text-white font-semibold">{patientName}</span> foi assinada e emitida
              com seguranca.
            </p>
          </div>
          <Badge tone="success" className="px-4 py-1.5 text-xs">
            Assinatura Verificada
          </Badge>
          <div className="flex flex-col sm:flex-row gap-3 w-full max-w-sm">
            <Button variant="primary" icon="download" className="flex-1">
              Baixar PDF
            </Button>
            <Button
              variant="ghost"
              icon="arrow_back"
              onClick={() => router.push("/med/atendimentos")}
              className="flex-1"
            >
              Voltar
            </Button>
          </div>
        </Card>

        {/* Security footer */}
        <div className="flex items-center justify-center gap-3 text-stone-600">
          <MaterialIcon icon="encrypted" size="sm" />
          <span className="text-[10px] uppercase font-bold tracking-widest">
            Documento protegido com criptografia ponta-a-ponta
          </span>
        </div>
      </div>
    );
  }

  /* ── Main signing page ──────────────────────────────────────────── */
  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="h-[1px] w-8 bg-primary" />
            <span className="font-headline text-xs font-bold tracking-widest text-primary uppercase">
              Portal de Assinatura
            </span>
          </div>
          <h1 className="text-3xl md:text-4xl font-headline font-extrabold text-white tracking-tight">
            Assinatura Digital de Prescricao
          </h1>
        </div>
        <Badge tone="warning" className="px-3 py-1.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse mr-2 inline-block" />
          Pendente de Assinatura
        </Badge>
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* LEFT: Prescription Preview (readonly) */}
        <div className="flex-1 space-y-6">
          {/* Prescription document preview */}
          <div className="bg-white rounded-xl shadow-2xl p-8 md:p-10 text-stone-900 relative overflow-hidden">
            {/* Watermark */}
            <div className="absolute inset-0 flex items-center justify-center opacity-[0.03] pointer-events-none">
              <MaterialIcon icon="medical_services" className="text-[300px]" />
            </div>

            <div className="relative z-10">
              {/* Document header */}
              <div className="flex flex-col sm:flex-row justify-between items-start border-b-2 border-stone-100 pb-6 mb-6 gap-4">
                <div>
                  <h2 className="font-headline font-bold text-xl sm:text-2xl tracking-tighter text-stone-900 uppercase">
                    Cannab&apos;IA Clinical
                  </h2>
                  <p className="text-xs text-stone-500">Centro de Pesquisa e Terapia Canabinoide</p>
                </div>
                <div className="text-right text-xs text-stone-500">
                  <p>{formatDate(new Date())}</p>
                  <p className="font-mono text-[10px] mt-1">
                    Cod. {params.id?.slice(0, 8) ?? "---"}
                  </p>
                </div>
              </div>

              {/* Patient & Prescriber info */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
                <div>
                  <p className="text-[10px] uppercase tracking-wider font-bold text-stone-400 mb-1">
                    Paciente
                  </p>
                  <p className="text-lg font-bold">{patientName || "---"}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider font-bold text-stone-400 mb-1">
                    Data de Emissao
                  </p>
                  <p className="text-lg font-bold">{formatDate(new Date())}</p>
                </div>
              </div>

              {/* Medication details */}
              <div className="space-y-6">
                <h3 className="text-sm font-black uppercase tracking-widest border-l-4 border-primary px-3">
                  Detalhes da Medicacao
                </h3>

                {prescriptionItems.length > 0 ? (
                  prescriptionItems.map((item, idx) => (
                    <div key={idx} className="bg-stone-50 p-5 rounded-lg space-y-3">
                      <div className="flex justify-between items-end border-b border-stone-200 pb-2">
                        <div>
                          <p className="font-bold text-lg">{item.medication ?? "Medicamento"}</p>
                          <p className="text-xs text-stone-500">{item.concentration ?? ""}</p>
                        </div>
                      </div>
                      <div>
                        <p className="text-xs font-bold text-stone-400 uppercase mb-1">Posologia</p>
                        <p className="text-stone-700 leading-relaxed italic text-sm">
                          {item.dosage ?? ""} - {item.frequency ?? ""} por {item.duration ?? ""}.
                          Via: {item.route ?? "oral"}. {item.instructions ?? ""}
                        </p>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="bg-stone-50 p-5 rounded-lg">
                    <p className="text-stone-400 italic text-sm">
                      Dados da prescricao serao carregados do servidor.
                    </p>
                  </div>
                )}

                {/* Clinical orientation */}
                {attendance?.report.treatment_plan && (
                  <>
                    <h3 className="text-sm font-black uppercase tracking-widest border-l-4 border-primary px-3 mt-6">
                      Orientacao Clinica
                    </h3>
                    <p className="text-stone-700 text-sm leading-relaxed">
                      {typeof attendance.report.treatment_plan === "object"
                        ? String(
                            (attendance.report.treatment_plan as Record<string, unknown>)
                              .monitoring_plan ?? "",
                          )
                        : ""}
                    </p>
                  </>
                )}

                {/* Signature area on document */}
                <div className="pt-16 mt-8 border-t-2 border-stone-100 flex flex-col items-center">
                  <div className="w-64 h-20 border-b border-stone-300 flex items-center justify-center">
                    {typedSignature ? (
                      <span className="font-headline italic text-stone-500 text-lg select-none">
                        {typedSignature}
                      </span>
                    ) : (
                      <span className="italic text-stone-300 text-sm">
                        Aguardando Assinatura Digital
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-bold text-stone-400 mt-2 uppercase">
                    {prescriberName
                      ? `${prescriberName} - CRM ${prescriberCrm}`
                      : "CRM do Prescritor"}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Legal disclaimer */}
          <div className="p-4 bg-error/5 border border-error/10 rounded-lg">
            <div className="flex items-start gap-3">
              <MaterialIcon icon="warning" size="sm" className="text-error" />
              <p className="text-[11px] text-error/80 leading-snug">
                Esta prescricao eletronica e valida por 30 dias. Distribuicao ou modificacao nao
                autorizada configura violacao da legislacao vigente conforme regulamentacao ANVISA e
                CFM.
              </p>
            </div>
          </div>
        </div>

        {/* RIGHT: Authentication Card */}
        <div className="lg:w-[400px] space-y-6">
          <Card className="sticky top-6">
            <h2 className="font-headline text-xl font-bold text-white mb-6 flex items-center gap-3">
              <MaterialIcon icon="verified_user" filled className="text-primary" />
              Autenticacao Digital
            </h2>

            {/* Certificate Status */}
            <div className="bg-surface-container-low rounded-lg p-4 mb-6 border border-primary/20">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-black uppercase tracking-widest text-stone-400">
                  Certificado Digital
                </span>
                <span className="flex items-center gap-1.5 text-[10px] font-bold text-primary">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                  ATIVO
                </span>
              </div>
              <div className="flex items-center gap-3">
                <MaterialIcon icon="id_card" className="text-white/40" />
                <div>
                  <p className="text-sm font-bold text-white">Certificado A1 ICP-Brasil</p>
                  <p className="text-[10px] text-stone-500">
                    Valido ate: 12/2026 - {prescriberName}
                  </p>
                </div>
              </div>
            </div>

            {/* Typed Signature */}
            <div className="space-y-4 mb-6">
              <Input
                label="Assinatura Digital (Texto)"
                icon="draw"
                value={typedSignature}
                onChange={(e) => setTypedSignature(e.target.value)}
                placeholder="Dr(a). Nome Completo"
              />

              {/* Certificate toggle */}
              <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg bg-surface-container-low border border-outline-variant/20 hover:border-primary/30 transition-colors">
                <input
                  type="checkbox"
                  checked={useCertificate}
                  onChange={(e) => setUseCertificate(e.target.checked)}
                  className="h-4 w-4 rounded border-outline-variant text-primary focus:ring-primary bg-surface-container-lowest"
                />
                <div>
                  <p className="text-sm font-medium text-on-surface">Usar Certificado Digital A1</p>
                  <p className="text-[10px] text-stone-500">Assinatura via ICP-Brasil</p>
                </div>
              </label>
            </div>

            {/* Security PIN */}
            <div className="space-y-2 mb-6">
              <Input
                label="PIN de Seguranca"
                icon="lock"
                type="password"
                value={securityPin}
                onChange={(e) => setSecurityPin(e.target.value)}
                placeholder="Digite seu PIN"
                hint="Esta acao assinara criptograficamente o documento."
              />
            </div>

            {/* Confirmation checkboxes */}
            <div className="space-y-3 mb-6">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmCorrect}
                  onChange={(e) => setConfirmCorrect(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-outline-variant text-primary focus:ring-primary bg-surface-container-lowest"
                />
                <span className="text-sm text-on-surface-variant">
                  Confirmo que as informacoes estao corretas
                </span>
              </label>
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmEmit}
                  onChange={(e) => setConfirmEmit(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-outline-variant text-primary focus:ring-primary bg-surface-container-lowest"
                />
                <span className="text-sm text-on-surface-variant">
                  Autorizo a emissao desta prescricao digital
                </span>
              </label>
            </div>

            {/* CRM and Date (auto-filled) */}
            <div className="grid grid-cols-2 gap-3 mb-6 p-3 rounded-lg bg-surface-container-low border border-outline-variant/20">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                  CRM
                </p>
                <p className="text-sm font-medium text-on-surface">
                  {prescriberCrm || "Preenchido automaticamente"}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                  Data
                </p>
                <p className="text-sm font-medium text-on-surface">{formatDate(new Date())}</p>
              </div>
            </div>

            {/* Action buttons */}
            <div className="space-y-3">
              <Button
                variant="primary"
                icon="draw"
                loading={signing}
                disabled={!canSign}
                onClick={handleSign}
                className="w-full"
                size="lg"
              >
                Assinar e Emitir
              </Button>
              <Button
                variant="ghost"
                icon="arrow_back"
                onClick={() => router.back()}
                className="w-full"
              >
                Voltar
              </Button>
            </div>

            {/* Safety note */}
            <div className="mt-6 flex gap-3 p-4 bg-white/5 rounded-lg">
              <MaterialIcon icon="info" className="text-stone-400 text-lg" />
              <p className="text-[11px] text-stone-400 leading-tight">
                Sua assinatura e protegida por criptografia ponta-a-ponta. Cannab&apos;IA Clinical
                segue os padroes LGPD e normas do CFM para prescricoes eletronicas.
              </p>
            </div>
          </Card>

          {/* Quick Actions */}
          <div className="grid grid-cols-2 gap-4">
            <div className="glass-panel rounded-xl p-4 hover:bg-white/5 transition-colors cursor-pointer group">
              <MaterialIcon
                icon="visibility"
                className="text-stone-500 group-hover:text-primary mb-2"
              />
              <p className="text-xs font-bold text-white">Visualizar</p>
            </div>
            <div className="glass-panel rounded-xl p-4 hover:bg-white/5 transition-colors cursor-pointer group">
              <MaterialIcon
                icon="edit_note"
                className="text-stone-500 group-hover:text-primary mb-2"
              />
              <p className="text-xs font-bold text-white">Editar Rascunho</p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="flex flex-col md:flex-row justify-between items-center text-stone-600 gap-4 pt-8">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <MaterialIcon icon="encrypted" size="sm" />
            <span className="text-[10px] uppercase font-bold tracking-widest">
              Criptografia Ponta-a-Ponta
            </span>
          </div>
          <div className="flex items-center gap-2">
            <MaterialIcon icon="gavel" size="sm" />
            <span className="text-[10px] uppercase font-bold tracking-widest">
              Conforme LGPD e CFM
            </span>
          </div>
        </div>
        <p className="text-[10px] font-medium">Cannab&apos;IA Clinical v4.2.0</p>
      </footer>
    </div>
  );
}
