"use client";

import { useState, useRef, useCallback, type PointerEvent } from "react";
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

interface SliderPickerProps {
  /** Label shown above the slider */
  label: string;
  /** Unit appended to value display (e.g. "/10", "%") */
  unit?: string;
  /** Min value (default 0) */
  min?: number;
  /** Max value (default 10) */
  max?: number;
  /** Step increment (default 1) */
  step?: number;
  /** Initial value */
  defaultValue?: number;
  /** Labels for min/max extremes */
  hints?: [string, string];
  /** Icon displayed in widget header */
  icon?: string;
  /** Called when user confirms selection */
  onConfirm?: (value: number) => void;
  /** Show/hide the widget */
  visible?: boolean;
}

export function SliderPicker({
  label,
  unit = "/10",
  min = 0,
  max = 10,
  step = 1,
  defaultValue = 5,
  hints,
  icon = "\u{1F3AF}",
  onConfirm,
  visible = true,
}: SliderPickerProps) {
  const [value, setValue] = useState(defaultValue);
  const [submitted, setSubmitted] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const pct = ((value - min) / (max - min)) * 100;

  const updateFromPointer = useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track) return;
      const rect = track.getBoundingClientRect();
      const raw = (clientX - rect.left) / rect.width;
      const clamped = Math.max(0, Math.min(1, raw));
      const stepped = Math.round((clamped * (max - min)) / step) * step + min;
      setValue(stepped);
    },
    [min, max, step],
  );

  const onPointerDown = (e: PointerEvent) => {
    if (submitted) return;
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    updateFromPointer(e.clientX);
  };

  const onPointerMove = (e: PointerEvent) => {
    if (!dragging.current) return;
    updateFromPointer(e.clientX);
  };

  const onPointerUp = () => {
    dragging.current = false;
  };

  const handleConfirm = () => {
    setSubmitted(true);
    onConfirm?.(value);
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
            {label}
          </h4>

          <div className="ds-slider">
            <div className="ds-slider__label-row">
              <span className="ds-slider__label">Intensidade</span>
              <span className="ds-slider__value">
                {value}
                <span style={{ fontSize: 12, fontWeight: 400, opacity: 0.6 }}>{unit}</span>
              </span>
            </div>

            <div
              className="ds-slider__track-wrap"
              ref={trackRef}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              role="slider"
              aria-valuenow={value}
              aria-valuemin={min}
              aria-valuemax={max}
              aria-label={label}
              tabIndex={0}
            >
              <div className="ds-slider__track">
                <div className="ds-slider__fill" style={{ width: `${pct}%` }} />
              </div>
              <motion.div
                className="ds-slider__thumb"
                style={{ left: `${pct}%` }}
                whileTap={{ scale: 1.2 }}
                transition={{ type: "spring" as const, stiffness: 400, damping: 20 }}
              />
            </div>

            {hints && (
              <div className="ds-slider__hints">
                <span>{hints[0]}</span>
                <span>{hints[1]}</span>
              </div>
            )}
          </div>

          <button className="ds-widget-confirm" onClick={handleConfirm} disabled={submitted}>
            {submitted ? "Enviado" : "Confirmar"}
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
