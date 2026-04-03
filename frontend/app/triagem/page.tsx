"use client";

import { useState, useCallback } from "react";
import { AnimatePresence } from "framer-motion";
import {
  ChatCanvas,
  ChatHeader,
  ChatThread,
  ChatBubble,
  ChatInput,
  TypingIndicator,
  SliderPicker,
  ConditionSelector,
  type ConditionOption,
} from "../../components/chat";

/* ─── Demo data ─────────────────────────────────────────────────────── */

const PAIN_CONDITIONS: ConditionOption[] = [
  { id: "headache", label: "Cefaleia", emoji: "\u{1F915}" },
  { id: "back", label: "Lombalgia", emoji: "\u{1F9B4}" },
  { id: "joint", label: "Articular", emoji: "\u{1F9BE}" },
  { id: "neuropathic", label: "Neuropática", emoji: "\u26A1" },
  { id: "muscular", label: "Muscular", emoji: "\u{1F4AA}" },
  { id: "abdominal", label: "Abdominal", emoji: "\u{1F922}" },
];

type MessageRole = "ai" | "patient";

interface Message {
  id: number;
  role: MessageRole;
  text: string;
  timestamp: string;
  widget?: "pain-slider" | "conditions";
}

const now = () =>
  new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

const INITIAL_MESSAGES: Message[] = [
  {
    id: 1,
    role: "ai",
    text: "Olá! Sou a assistente de triagem da sua clínica. Vou te fazer algumas perguntas para entender melhor o que você está sentindo. Tudo pronto?",
    timestamp: now(),
  },
];

/* ─── Page ──────────────────────────────────────────────────────────── */

export default function TriagemPage() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [typing, setTyping] = useState(false);
  const [step, setStep] = useState(0);

  const addMessage = useCallback(
    (role: MessageRole, text: string, widget?: Message["widget"]) => {
      setMessages((prev) => [
        ...prev,
        { id: prev.length + 1, role, text, timestamp: now(), widget },
      ]);
    },
    [],
  );

  const simulateAi = useCallback(
    (text: string, widget?: Message["widget"], delay = 1200) => {
      setTyping(true);
      setTimeout(() => {
        setTyping(false);
        addMessage("ai", text, widget);
      }, delay);
    },
    [addMessage],
  );

  const handleSend = useCallback(
    (text: string) => {
      addMessage("patient", text);

      if (step === 0) {
        setStep(1);
        simulateAi(
          "Entendi! Você mencionou dores. Pode selecionar abaixo os tipos que mais se aplicam?",
          "conditions",
        );
      } else if (step >= 2) {
        simulateAi(
          "Obrigada pelas informações! Estou compilando seu resumo de triagem para o médico revisar.",
        );
      }
    },
    [step, addMessage, simulateAi],
  );

  const handleConditionsConfirm = useCallback(
    (selected: string[]) => {
      const labels = selected
        .map((id) => PAIN_CONDITIONS.find((c) => c.id === id)?.label)
        .filter(Boolean);
      addMessage("patient", `Selecionei: ${labels.join(", ")}`);
      setStep(2);
      simulateAi(
        "Qual a intensidade média da dor que você sente no dia a dia?",
        "pain-slider",
      );
    },
    [addMessage, simulateAi],
  );

  const handleSliderConfirm = useCallback(
    (value: number) => {
      addMessage("patient", `Intensidade: ${value}/10`);
      setStep(3);
      simulateAi(
        "Obrigada! Isso já me dá um panorama importante. Mais alguma informação que gostaria de adicionar?",
      );
    },
    [addMessage, simulateAi],
  );

  return (
    <ChatCanvas>
      <ChatHeader clinicName="Cannab'IA Triagem" clinicInitials="CA" />

      <ChatThread>
        {messages.map((msg) => (
          <ChatBubble key={msg.id} role={msg.role} timestamp={msg.timestamp}>
            {msg.text}
            {msg.widget === "conditions" && (
              <div style={{ marginTop: 12 }}>
                <ConditionSelector
                  title="Tipo de dor"
                  options={PAIN_CONDITIONS}
                  maxSelections={3}
                  onConfirm={handleConditionsConfirm}
                />
              </div>
            )}
            {msg.widget === "pain-slider" && (
              <div style={{ marginTop: 12 }}>
                <SliderPicker
                  label="Escala de Dor"
                  hints={["Leve", "Intensa"]}
                  onConfirm={handleSliderConfirm}
                />
              </div>
            )}
          </ChatBubble>
        ))}

        <AnimatePresence>{typing && <TypingIndicator />}</AnimatePresence>
      </ChatThread>

      <ChatInput onSend={handleSend} disabled={typing} />
    </ChatCanvas>
  );
}
