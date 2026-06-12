"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const widgetMotion = {
  hidden: { opacity: 0, y: 16, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 340, damping: 26, delay: 0.1 },
  },
  exit: { opacity: 0, scale: 0.95, transition: { duration: 0.15 } },
};

const chipMotion = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: (i: number) => ({
    opacity: 1,
    scale: 1,
    transition: { delay: 0.15 + i * 0.04, type: "spring" as const, stiffness: 400, damping: 24 },
  }),
};

export interface ConditionOption {
  id: string;
  label: string;
  emoji?: string;
}

interface ConditionSelectorProps {
  /** Title shown in widget header */
  title: string;
  /** Icon in header */
  icon?: string;
  /** Available conditions to choose from */
  options: ConditionOption[];
  /** Max selections allowed (0 = unlimited) */
  maxSelections?: number;
  /** Called when user confirms */
  onConfirm?: (selected: string[]) => void;
  /** Show/hide */
  visible?: boolean;
}

export function ConditionSelector({
  title,
  icon = "\u{1FA7A}",
  options,
  maxSelections = 0,
  onConfirm,
  visible = true,
}: ConditionSelectorProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [submitted, setSubmitted] = useState(false);

  const toggle = (id: string) => {
    if (submitted) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (maxSelections > 0 && next.size >= maxSelections) return prev;
        next.add(id);
      }
      return next;
    });
  };

  const handleConfirm = () => {
    if (selected.size === 0) return;
    setSubmitted(true);
    onConfirm?.(Array.from(selected));
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="ds-chat-widget"
          variants={widgetMotion}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          <h4 className="ds-chat-widget__title">
            <span className="ds-chat-widget__icon">{icon}</span>
            {title}
          </h4>

          <div className="ds-condition-grid">
            {options.map((opt, i) => {
              const active = selected.has(opt.id);
              return (
                <motion.button
                  key={opt.id}
                  className={`ds-condition-chip${active ? " ds-condition-chip--active" : ""}`}
                  onClick={() => toggle(opt.id)}
                  variants={chipMotion}
                  initial="hidden"
                  animate="visible"
                  custom={i}
                  whileTap={{ scale: 0.96 }}
                  disabled={submitted}
                  type="button"
                  aria-pressed={active}
                >
                  <span className="ds-condition-chip__check">
                    {active && (
                      <motion.svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={3}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ type: "spring" as const, stiffness: 500, damping: 20 }}
                      >
                        <path d="M20 6 9 17l-5-5" />
                      </motion.svg>
                    )}
                  </span>
                  {opt.emoji && <span className="ds-condition-chip__emoji">{opt.emoji}</span>}
                  {opt.label}
                </motion.button>
              );
            })}
          </div>

          {maxSelections > 0 && (
            <p style={{ fontSize: 12, color: "var(--ch-text-muted)", margin: 0 }}>
              Selecione até {maxSelections} opções
            </p>
          )}

          <button
            className="ds-widget-confirm"
            onClick={handleConfirm}
            disabled={submitted || selected.size === 0}
          >
            {submitted
              ? `${selected.size} selecionado${selected.size > 1 ? "s" : ""}`
              : `Confirmar (${selected.size})`}
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
