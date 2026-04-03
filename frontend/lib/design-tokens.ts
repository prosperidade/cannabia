/**
 * CannabIA Design Tokens
 *
 * Source of truth para cores, espaçamentos, tipografia e radii.
 * As CSS custom properties em globals.css DEVEM ser mantidas em sincronia
 * com os valores abaixo — os tokens JS são para uso em lógica condicional,
 * animações e componentes que precisam de valores programáticos.
 */

// ─── Palette ────────────────────────────────────────────────────────
export const colors = {
  bg: "#07111f",
  panel: "rgba(11, 23, 42, 0.82)",
  line: "rgba(176, 205, 255, 0.14)",
  text: "#ecf3ff",
  muted: "#9db2d8",

  // Accent
  aqua: "#79f0ff",
  mint: "#77f7c5",
  amber: "#ffd36d",
  rose: "#ff8ea1",

  // Semantic
  success: "#77f7c5",
  warning: "#ffd36d",
  error: "#ff8ea1",
  info: "#79f0ff",

  // Surfaces
  overlay: "rgba(0, 0, 0, 0.34)",
  glassLight: "rgba(255, 255, 255, 0.04)",
  glassMedium: "rgba(255, 255, 255, 0.06)",
} as const;

// ─── Olive Harmony — Chat / Triagem Palette ────────────────────────
export const chat = {
  primary: "#4c5e31",
  primaryLight: "#6c8148",
  primaryMuted: "#8a9e6b",
  canvas: "#faf9f5",
  surface: "#ffffff",
  surfaceHover: "#f4f3ee",
  border: "#e2e0d6",
  borderFocus: "#4c5e31",
  textPrimary: "#1e1e1c",
  textSecondary: "#5c5c56",
  textMuted: "#8a8a82",
  aiBubble: "#f0efe8",
  aiBubbleBorder: "#dddcd4",
  patientBubble: "#4c5e31",
  patientText: "#ffffff",
  widgetBg: "#ffffff",
  widgetBorder: "#e2e0d6",
  widgetAccent: "#6c8148",
  widgetTrack: "#e8e7e0",
  widgetThumb: "#4c5e31",
  inputBg: "#ffffff",
  inputBorder: "#d4d2c8",
  shadowSoft: "0 2px 12px rgba(76, 94, 49, 0.08)",
  shadowMedium: "0 8px 30px rgba(76, 94, 49, 0.12)",
  shadowWidget: "0 4px 20px rgba(0, 0, 0, 0.06)",
} as const;

// ─── Typography ─────────────────────────────────────────────────────
export const fontFamilies = {
  sans: '"Space Grotesk", "Manrope", "Avenir Next", "Segoe UI", sans-serif',
  mono: '"IBM Plex Mono", "SFMono-Regular", Consolas, monospace',
} as const;

export const fontSizes = {
  xs: "12px",
  sm: "13px",
  base: "16px",
  lg: "18px",
  xl: "22px",
  "2xl": "30px",
  "3xl": "clamp(34px, 6vw, 62px)",
} as const;

export const fontWeights = {
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
} as const;

export const lineHeights = {
  tight: 0.96,
  snug: 1.2,
  normal: 1.5,
  relaxed: 1.7,
} as const;

// ─── Spacing ────────────────────────────────────────────────────────
export const spacing = {
  0: "0px",
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "18px",
  6: "22px",
  7: "24px",
  8: "26px",
  9: "28px",
  10: "30px",
  12: "34px",
  14: "40px",
  16: "72px",
} as const;

// ─── Radii ──────────────────────────────────────────────────────────
export const radii = {
  sm: "12px",
  md: "14px",
  lg: "16px",
  xl: "18px",
  "2xl": "20px",
  "3xl": "22px",
  "4xl": "24px",
  "5xl": "28px",
  full: "999px",
} as const;

// ─── Shadows ────────────────────────────────────────────────────────
export const shadows = {
  card: "0 26px 80px rgba(0, 0, 0, 0.34)",
  glow: "0 12px 30px rgba(121, 240, 255, 0.22)",
} as const;

// ─── Transitions ────────────────────────────────────────────────────
export const transitions = {
  fast: "140ms ease",
  normal: "200ms ease",
  slow: "300ms ease",
} as const;

// ─── Breakpoints ────────────────────────────────────────────────────
export const breakpoints = {
  sm: 760,
  md: 1120,
} as const;

// ─── Z-index ────────────────────────────────────────────────────────
export const zIndex = {
  base: 0,
  dropdown: 10,
  sticky: 20,
  overlay: 30,
  modal: 40,
  toast: 50,
  skipNav: 100,
} as const;
