/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#f4f7fb", elevated: "#edf2f7" },
        panel: { DEFAULT: "#ffffff", soft: "#f8fafc", muted: "#f1f5f9" },
        border: { DEFAULT: "#d8e1ea", strong: "#c3ced9" },
        txt: { DEFAULT: "#16202a", soft: "#5f6b7a", faint: "#8a95a3", inverse: "#ffffff" },
        accent: { DEFAULT: "#1967d2", hover: "#1557b0", soft: "#e8f0fe" },
        success: { DEFAULT: "#1f8f5f", soft: "#eaf7f0" },
        warning: { DEFAULT: "#b7791f", soft: "#fff6e5" },
        danger: { DEFAULT: "#c53b3b", soft: "#fdecec" },
        info: { DEFAULT: "#3366cc", soft: "#eef4ff" },
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
