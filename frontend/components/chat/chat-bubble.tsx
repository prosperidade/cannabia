"use client";

import { type ReactNode } from "react";
import { motion } from "framer-motion";

/* ─── Animation variants ────────────────────────────────────────────── */

const bubbleVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.96 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 380, damping: 28 },
  },
};

/* ─── Chat Bubble ───────────────────────────────────────────────────── */

interface ChatBubbleProps {
  role: "ai" | "patient";
  children: ReactNode;
  /** Initials shown in avatar (defaults to role-based) */
  initials?: string;
  timestamp?: string;
}

export function ChatBubble({ role, children, initials, timestamp }: ChatBubbleProps) {
  const isAi = role === "ai";
  const fallbackInitials = isAi ? "IA" : "P";

  return (
    <motion.div
      className={`ds-chat-row ds-chat-row--${role}`}
      variants={bubbleVariants}
      initial="hidden"
      animate="visible"
    >
      <div className={`ds-chat-avatar ds-chat-avatar--${role}`}>{initials ?? fallbackInitials}</div>
      <div>
        <div className={`ds-chat-bubble ds-chat-bubble--${role}`}>{children}</div>
        {timestamp && <div className="ds-chat-time">{timestamp}</div>}
      </div>
    </motion.div>
  );
}

/* ─── Typing Indicator ──────────────────────────────────────────────── */

export function TypingIndicator() {
  return (
    <motion.div
      className="ds-chat-row ds-chat-row--ai"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
    >
      <div className="ds-chat-avatar ds-chat-avatar--ai">IA</div>
      <div className="ds-chat-typing" aria-label="Digitando...">
        <span className="ds-chat-typing__dot" />
        <span className="ds-chat-typing__dot" />
        <span className="ds-chat-typing__dot" />
      </div>
    </motion.div>
  );
}
