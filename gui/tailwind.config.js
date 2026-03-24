/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "rgb(var(--c-bg) / <alpha-value>)",
          elevated: "rgb(var(--c-bg-elevated) / <alpha-value>)",
        },
        panel: {
          DEFAULT: "rgb(var(--c-panel) / <alpha-value>)",
          soft: "rgb(var(--c-panel-soft) / <alpha-value>)",
          muted: "rgb(var(--c-panel-muted) / <alpha-value>)",
        },
        border: {
          DEFAULT: "rgb(var(--c-border) / <alpha-value>)",
          strong: "rgb(var(--c-border-strong) / <alpha-value>)",
        },
        txt: {
          DEFAULT: "rgb(var(--c-txt) / <alpha-value>)",
          soft: "rgb(var(--c-txt-soft) / <alpha-value>)",
          faint: "rgb(var(--c-txt-faint) / <alpha-value>)",
          inverse: "rgb(var(--c-txt-inverse) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--c-accent) / <alpha-value>)",
          hover: "rgb(var(--c-accent-hover) / <alpha-value>)",
          soft: "rgb(var(--c-accent-soft) / <alpha-value>)",
        },
        success: {
          DEFAULT: "rgb(var(--c-success) / <alpha-value>)",
          soft: "rgb(var(--c-success-soft) / <alpha-value>)",
        },
        warning: {
          DEFAULT: "rgb(var(--c-warning) / <alpha-value>)",
          soft: "rgb(var(--c-warning-soft) / <alpha-value>)",
        },
        danger: {
          DEFAULT: "rgb(var(--c-danger) / <alpha-value>)",
          soft: "rgb(var(--c-danger-soft) / <alpha-value>)",
        },
        info: {
          DEFAULT: "rgb(var(--c-info) / <alpha-value>)",
          soft: "rgb(var(--c-info-soft) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ['"Noto Sans SC"', '"Source Han Sans SC"', '"PingFang SC"', '"Microsoft YaHei"', "sans-serif"],
        ui: ['"IBM Plex Sans"', '"Noto Sans SC"', "sans-serif"],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', "Consolas", "monospace"],
      },
      fontSize: {
        xs: "12px", sm: "13px", md: "14px", lg: "16px",
        xl: "18px", "2xl": "22px", "3xl": "28px",
      },
      borderRadius: {
        xs: "8px", sm: "10px", md: "16px", lg: "22px", pill: "999px",
      },
      boxShadow: {
        sm: "0 2px 8px rgba(16,24,40,0.04)",
        md: "0 12px 28px rgba(16,24,40,0.08)",
        lg: "0 22px 40px rgba(16,24,40,0.12)",
      },
      spacing: {
        1: "4px", 2: "8px", 3: "12px", 4: "16px", 5: "20px",
        6: "24px", 8: "32px", 10: "40px", 12: "48px",
      },
    },
  },
  plugins: [],
};
