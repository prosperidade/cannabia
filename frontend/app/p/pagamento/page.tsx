"use client";

import { useState } from "react";
import { Button, Card, Input, MaterialIcon } from "@/components/ui-tw";
import { cn } from "@/lib/cn";

type PaymentMethod = "card" | "pix";
type Step = "info" | "payment" | "confirm" | "success";

export default function PagamentoPage() {
  const [step, setStep] = useState<Step>("payment");
  const [selectedMethod, setSelectedMethod] = useState<PaymentMethod>("card");
  const [couponCode, setCouponCode] = useState("");
  const [couponApplied, setCouponApplied] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  // Card form state
  const [cardName, setCardName] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvv, setCardCvv] = useState("");

  const originalPrice = 450;
  const currentPrice = 89;

  function handleApplyCoupon() {
    if (couponCode.trim()) {
      setCouponApplied(true);
    }
  }

  function handleFinalizePurchase() {
    setStep("confirm");
  }

  function handleConfirm() {
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
      setStep("success");
    }, 1500);
  }

  // ── Success Step ──
  if (step === "success") {
    return (
      <div className="min-h-screen bg-background text-on-background font-body flex flex-col">
        {/* Top Bar */}
        <header className="fixed top-0 w-full z-50 border-b border-white/5 bg-zinc-950/80 backdrop-blur-md flex items-center justify-between px-6 h-16">
          <div className="flex items-center gap-2">
            <MaterialIcon icon="eco" filled size="md" className="text-primary" />
            <span className="font-headline uppercase tracking-widest text-xs font-bold text-primary">
              Cannab&apos;IA
            </span>
          </div>
          <div className="w-8" />
        </header>

        <main className="pt-16 flex-1 flex items-center justify-center px-6">
          <div className="max-w-md w-full text-center space-y-8">
            {/* Checkmark */}
            <div className="mx-auto w-24 h-24 rounded-full bg-primary/10 border-2 border-primary/30 flex items-center justify-center">
              <MaterialIcon
                icon="check_circle"
                filled
                size="xl"
                className="text-primary"
              />
            </div>

            <div className="space-y-3">
              <h1 className="font-headline text-2xl font-extrabold text-on-surface">
                Tudo pronto! Agora faca sua consulta
              </h1>
              <p className="text-on-surface-variant text-sm leading-relaxed">
                Um medico ja esta aguardando voce
              </p>
            </div>

            <Card variant="glass" padding="md" className="text-left space-y-3">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <MaterialIcon icon="chat" size="sm" className="text-primary" />
                </div>
                <div>
                  <p className="text-sm font-bold text-on-surface">
                    A sua consulta sera por chat
                  </p>
                  <p className="text-xs text-on-surface-variant">
                    Responda no seu tempo, sem pressa
                  </p>
                </div>
              </div>
            </Card>

            <Button
              variant="primary"
              size="lg"
              icon="arrow_forward"
              className="w-full rounded-full py-5 text-lg"
              onClick={() => {
                // Navigate to consultation - placeholder
                window.location.href = "/p/consulta";
              }}
            >
              Proximo
            </Button>
          </div>
        </main>
      </div>
    );
  }

  // ── Confirmation Step ──
  if (step === "confirm") {
    return (
      <div className="min-h-screen bg-background text-on-background font-body flex flex-col">
        {/* Top Bar */}
        <header className="fixed top-0 w-full z-50 border-b border-white/5 bg-zinc-950/80 backdrop-blur-md flex items-center justify-between px-6 h-16">
          <button
            onClick={() => setStep("payment")}
            className="hover:opacity-80 transition-opacity active:scale-95"
          >
            <MaterialIcon icon="arrow_back" className="text-primary" />
          </button>
          <h1 className="text-lg font-bold tracking-tighter text-primary font-headline">
            Confirmar Pagamento
          </h1>
          <div className="w-6" />
        </header>

        <main className="pt-20 flex-1 flex items-center justify-center px-6">
          <div className="max-w-md w-full space-y-8">
            <Card variant="glass" padding="lg" className="text-center space-y-6">
              <div className="space-y-2">
                <p className="text-sm text-on-surface-variant uppercase tracking-widest font-bold">
                  Valor atual da consulta
                </p>
                <p className="text-lg text-on-surface-variant">
                  Apenas
                </p>
                <p className="font-headline text-5xl font-extrabold text-primary tracking-tighter">
                  R$ {currentPrice}
                </p>
              </div>

              <div className="border-t border-white/5 pt-6 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-secondary-container flex items-center justify-center flex-shrink-0">
                    <MaterialIcon
                      icon="medical_services"
                      size="sm"
                      className="text-on-secondary-container"
                    />
                  </div>
                  <p className="text-sm text-on-surface-variant text-left leading-relaxed">
                    Voce tera acesso a uma consulta completa com um medico especialista em medicina canabinoide.
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-secondary-container flex items-center justify-center flex-shrink-0">
                    <MaterialIcon
                      icon="verified_user"
                      size="sm"
                      className="text-on-secondary-container"
                    />
                  </div>
                  <p className="text-sm text-on-surface-variant text-left leading-relaxed">
                    Ambiente seguro e em conformidade com as normas de saude.
                  </p>
                </div>
              </div>
            </Card>

            <Button
              variant="primary"
              size="lg"
              loading={isProcessing}
              className="w-full rounded-full py-5 text-lg bg-[#b8e046] hover:bg-primary text-on-primary-container"
              onClick={handleConfirm}
            >
              {isProcessing ? "Processando..." : "Entendi e quero aproveitar"}
            </Button>

            <button
              onClick={() => setStep("payment")}
              className="w-full text-center text-sm text-stone-500 hover:text-stone-300 transition-colors"
            >
              Voltar
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ── Payment Step (main checkout) ──
  return (
    <div className="min-h-screen bg-background text-on-background font-body">
      {/* Top Bar */}
      <header className="fixed top-0 w-full z-50 border-b border-white/5 bg-zinc-950/80 backdrop-blur-md flex items-center justify-between px-6 h-16">
        <button className="hover:opacity-80 transition-opacity active:scale-95">
          <MaterialIcon icon="arrow_back" className="text-primary" />
        </button>
        <h1 className="text-lg font-bold tracking-tighter text-primary font-headline">
          Pagamento
        </h1>
        <div className="w-6" />
      </header>

      <main className="pt-20 pb-12 px-4 sm:px-6 max-w-4xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* ── Left Column ── */}
          <div className="lg:col-span-7 space-y-6">
            {/* Hero / Header */}
            <section className="space-y-3">
              <h2 className="font-headline text-xl sm:text-2xl font-extrabold text-on-surface leading-tight">
                Voce nao precisa agendar: faca agora a sua consulta por chat
              </h2>
              <p className="text-on-surface-variant text-sm">
                Complete o pagamento para iniciar sua consulta com um especialista.
              </p>
            </section>

            {/* Price Display */}
            <Card variant="glass" padding="md" className="flex items-center gap-4">
              <div className="h-14 w-14 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <MaterialIcon
                  icon="medical_services"
                  size="lg"
                  className="text-primary"
                />
              </div>
              <div className="flex-1">
                <h3 className="font-headline font-bold text-on-surface">
                  Consulta com Especialista
                </h3>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  Medicina canabinoide por chat
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-stone-500 line-through">
                  R$ {originalPrice}
                </p>
                <p className="font-headline font-extrabold text-2xl text-primary tracking-tighter">
                  R$ {currentPrice}
                </p>
              </div>
            </Card>

            {/* Coupon */}
            <section className="space-y-2">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <div className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-500">
                    <MaterialIcon icon="confirmation_number" size="sm" />
                  </div>
                  <input
                    type="text"
                    value={couponCode}
                    onChange={(e) => setCouponCode(e.target.value)}
                    placeholder="Inserir cupom de desconto"
                    className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT pl-10 pr-4 py-3 text-on-surface placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors text-sm"
                  />
                </div>
                <button
                  onClick={handleApplyCoupon}
                  className="bg-surface-container-highest px-5 py-3 rounded-DEFAULT text-sm font-bold text-primary hover:bg-surface-bright transition-colors"
                >
                  Aplicar
                </button>
              </div>
              {couponApplied && (
                <div className="flex items-center gap-2 text-xs text-emerald-400">
                  <MaterialIcon icon="check_circle" size="sm" />
                  <span>Cupom aplicado com sucesso!</span>
                </div>
              )}
            </section>

            {/* Payment Method Toggle */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-widest text-stone-400 px-1">
                Escolha a forma de pagamento
              </h3>
              <div className="flex p-1 bg-surface-container-highest rounded-full">
                <button
                  onClick={() => setSelectedMethod("card")}
                  className={cn(
                    "flex-1 py-2.5 rounded-full text-sm font-bold flex items-center justify-center gap-2 transition-all",
                    selectedMethod === "card"
                      ? "bg-primary-container text-on-primary-container"
                      : "text-stone-500 hover:text-stone-300"
                  )}
                >
                  <MaterialIcon icon="credit_card" size="sm" />
                  Cartao de credito
                </button>
                <button
                  onClick={() => setSelectedMethod("pix")}
                  className={cn(
                    "flex-1 py-2.5 rounded-full text-sm font-bold flex items-center justify-center gap-2 transition-all",
                    selectedMethod === "pix"
                      ? "bg-primary-container text-on-primary-container"
                      : "text-stone-500 hover:text-stone-300"
                  )}
                >
                  <MaterialIcon icon="qr_code_2" size="sm" />
                  Pix
                </button>
              </div>
            </section>

            {/* Payment Form */}
            {selectedMethod === "card" ? (
              <Card variant="glass" padding="md" className="space-y-4">
                <Input
                  label="Nome no cartao"
                  placeholder="Nome completo"
                  value={cardName}
                  onChange={(e) => setCardName(e.target.value)}
                />
                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                    Numero do cartao
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={cardNumber}
                      onChange={(e) => setCardNumber(e.target.value)}
                      placeholder="0000 0000 0000 0000"
                      className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 pr-12 py-3 text-on-surface placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors"
                    />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2">
                      <MaterialIcon icon="credit_card" size="sm" className="text-stone-500" />
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="Validade"
                    placeholder="MM/AA"
                    value={cardExpiry}
                    onChange={(e) => setCardExpiry(e.target.value)}
                  />
                  <Input
                    label="CVV"
                    placeholder="***"
                    type="password"
                    value={cardCvv}
                    onChange={(e) => setCardCvv(e.target.value)}
                  />
                </div>
              </Card>
            ) : (
              <Card variant="glass" padding="md" className="space-y-6">
                {/* PIX QR Code placeholder */}
                <div className="flex flex-col items-center space-y-4">
                  <p className="text-sm text-on-surface-variant text-center">
                    Escaneie o QR Code abaixo ou copie o codigo PIX
                  </p>
                  <div className="w-48 h-48 bg-white rounded-lg flex items-center justify-center">
                    <MaterialIcon
                      icon="qr_code_2"
                      size="xl"
                      className="text-stone-800 !text-[120px]"
                    />
                  </div>
                  <p className="text-xs text-stone-500 text-center">
                    O pagamento sera confirmado automaticamente
                  </p>
                </div>

                <button
                  onClick={() => {
                    // Placeholder: copy PIX code
                  }}
                  className="w-full flex items-center justify-center gap-2 bg-surface-container-highest hover:bg-surface-bright py-3 rounded-DEFAULT text-sm font-bold text-primary transition-colors"
                >
                  <MaterialIcon icon="content_copy" size="sm" />
                  Copiar codigo PIX
                </button>
              </Card>
            )}
          </div>

          {/* ── Right Column (Order Summary, desktop only) ── */}
          <aside className="lg:col-span-5 space-y-6 hidden lg:block">
            <div className="sticky top-24 space-y-6">
              <Card variant="glass" padding="lg" className="space-y-6">
                <h2 className="font-headline text-xl font-bold text-on-surface">
                  Resumo do pedido
                </h2>

                {/* Product detail */}
                <div className="flex gap-4">
                  <div className="h-14 w-14 bg-primary/10 rounded-lg flex items-center justify-center text-primary flex-shrink-0">
                    <MaterialIcon icon="medical_services" size="lg" />
                  </div>
                  <div>
                    <h3 className="font-bold text-on-surface">Consulta Premium</h3>
                    <p className="text-sm text-on-surface-variant">
                      Medico Especialista
                    </p>
                    <p className="text-xs text-primary mt-1">Consulta por chat</p>
                  </div>
                </div>

                {/* Price breakdown */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-stone-400">Valor original</span>
                    <span className="text-stone-500 line-through">
                      R$ {originalPrice},00
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-sm text-primary">
                    <span className="flex items-center gap-1">
                      <MaterialIcon icon="local_offer" size="sm" />
                      Desconto promocional
                    </span>
                    <span className="font-medium">
                      -R$ {originalPrice - currentPrice},00
                    </span>
                  </div>
                  {couponApplied && (
                    <div className="flex justify-between items-center text-sm text-emerald-400">
                      <span className="flex items-center gap-1">
                        <MaterialIcon icon="confirmation_number" size="sm" />
                        Cupom ({couponCode})
                      </span>
                      <span className="font-medium">Aplicado</span>
                    </div>
                  )}
                  <div className="pt-4 border-t border-white/5 flex justify-between items-end">
                    <span className="text-on-surface-variant font-headline uppercase tracking-widest text-xs">
                      Total
                    </span>
                    <span className="text-3xl font-extrabold text-primary tracking-tighter font-headline">
                      R$ {currentPrice},00
                    </span>
                  </div>
                </div>

                {/* CTA */}
                <Button
                  variant="primary"
                  size="lg"
                  icon="arrow_forward"
                  className="w-full rounded-full py-4 text-lg shadow-xl shadow-primary/10"
                  onClick={handleFinalizePurchase}
                >
                  Finalizar pagamento
                </Button>

                {/* Secure badge */}
                <div className="flex items-center justify-center gap-2 text-stone-500 text-[10px] uppercase tracking-widest font-headline">
                  <MaterialIcon icon="encrypted" size="sm" />
                  Transacao criptografada
                </div>
              </Card>

              {/* Help card */}
              <Card variant="glass" padding="md" className="flex items-start gap-4">
                <div className="bg-secondary-container p-2 rounded-full flex-shrink-0">
                  <MaterialIcon
                    icon="help_outline"
                    size="sm"
                    className="text-on-secondary-container"
                  />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-on-surface">
                    Precisa de ajuda?
                  </h4>
                  <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                    Nossa equipe de suporte esta disponivel para ajudar durante todo o
                    processo de pagamento.
                  </p>
                </div>
              </Card>
            </div>
          </aside>
        </div>

        {/* ── Mobile-only bottom section ── */}
        <div className="lg:hidden space-y-6 mt-6">
          {/* Total and Security */}
          <section className="space-y-6">
            <div className="flex justify-between items-end border-t border-white/5 pt-6">
              <div>
                <p className="text-stone-500 text-sm">Valor total</p>
                <p className="text-xs text-stone-600 italic">
                  Taxas inclusas
                </p>
              </div>
              <div className="text-right">
                <p className="text-4xl font-headline font-extrabold text-primary tracking-tighter">
                  R$ {currentPrice}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-center gap-4 py-2 opacity-60">
              <div className="flex items-center gap-1.5">
                <MaterialIcon
                  icon="verified_user"
                  size="sm"
                  className="text-primary text-[14px]"
                />
                <span className="text-[10px] uppercase tracking-widest font-bold">
                  Criptografado
                </span>
              </div>
              <div className="h-1 w-1 bg-stone-700 rounded-full" />
              <div className="flex items-center gap-1.5">
                <MaterialIcon
                  icon="lock"
                  size="sm"
                  className="text-primary text-[14px]"
                />
                <span className="text-[10px] uppercase tracking-widest font-bold">
                  SSL Seguro
                </span>
              </div>
            </div>
          </section>

          {/* Security message */}
          <Card variant="glass" padding="sm" className="flex items-center gap-3">
            <MaterialIcon
              icon="shield"
              size="sm"
              className="text-primary flex-shrink-0"
            />
            <p className="text-xs text-on-surface-variant leading-relaxed">
              Ambiente de atendimento seguro e em conformidade com as normas de saude
            </p>
          </Card>

          {/* CTA button */}
          <div className="pb-8">
            <Button
              variant="primary"
              size="lg"
              icon="arrow_forward"
              className="w-full rounded-lg py-5 text-lg shadow-[0_12px_40px_rgba(163,201,58,0.2)]"
              onClick={handleFinalizePurchase}
            >
              Finalizar pagamento
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
