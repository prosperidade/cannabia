import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        /* ── Material Design 3 – Stitch tokens ── */
        primary: "#bee654",
        "on-primary": "#273500",
        "primary-container": "#a3c93a",
        "on-primary-container": "#3e5200",
        "primary-fixed": "#c9f15e",
        "primary-fixed-dim": "#aed445",

        secondary: "#a4d2a4",
        "on-secondary": "#0e3817",
        "secondary-container": "#29522e",
        "on-secondary-container": "#96c496",
        "secondary-fixed": "#bfefbe",
        "secondary-fixed-dim": "#a4d2a4",

        tertiary: "#ffc4fe",
        "on-tertiary": "#580064",
        "tertiary-container": "#f998ff",
        "on-tertiary-container": "#792484",
        "tertiary-fixed": "#ffd6fc",
        "tertiary-fixed-dim": "#fcaaff",

        error: "#ffb4ab",
        "on-error": "#690005",
        "error-container": "#93000a",
        "on-error-container": "#ffdad6",

        surface: "#0e1606",
        "surface-dim": "#0e1606",
        "surface-bright": "#333c29",
        "surface-container-lowest": "#091003",
        "surface-container-low": "#161e0d",
        "surface-container": "#1a2211",
        "surface-container-high": "#242d1a",
        "surface-container-highest": "#2f3824",
        "surface-variant": "#2f3824",
        "surface-tint": "#aed445",

        "on-surface": "#dce6cb",
        "on-surface-variant": "#c5c9b1",
        "on-background": "#dce6cb",
        background: "#0e1606",

        outline: "#8f937d",
        "outline-variant": "#444937",

        "inverse-surface": "#dce6cb",
        "inverse-on-surface": "#2a3320",
        "inverse-primary": "#4f6700",

        "on-primary-fixed": "#151f00",
        "on-primary-fixed-variant": "#3a4d00",
        "on-secondary-fixed": "#002107",
        "on-secondary-fixed-variant": "#274f2c",
        "on-tertiary-fixed": "#36003e",
        "on-tertiary-fixed-variant": "#741e80",
      },
      borderRadius: {
        DEFAULT: "1rem",
        lg: "2rem",
        xl: "3rem",
        full: "9999px",
      },
      fontFamily: {
        headline: ["Manrope", "sans-serif"],
        body: ["Inter", "sans-serif"],
        label: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
