/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0d1117",
        panel: "#161b22",
        border: "#21262d",
        "text-primary": "#e6edf3",
        "text-muted": "#7d8590",
        accent: "#2f81f7",
        success: "#3fb950",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
