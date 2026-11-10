import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          void: "#040406",
          black: "#08090c",
          dark: "#0e1017",
          surface: "#141721",
          surfaceHover: "#1b1f2d",
          border: "#2e2513",
          borderHover: "#59400f",
          amber: {
            DEFAULT: "#d97706", // Dark Amber
            light: "#f59e0b",   // Cyber Gold
            bright: "#fbbf24",  // Neon Amber
            deep: "#92400e",    // Deep Gold
            darkest: "#451a03",
          },
          yellow: {
            DEFAULT: "#ca8a04",
            bright: "#facc15",
            pale: "#fef08a",
          },
          cyan: "#06b6d4",
          emerald: "#10b981",
          red: "#ef4444",
        },
      },
      boxShadow: {
        "amber-glow-sm": "0 0 10px -2px rgba(217, 119, 6, 0.35)",
        "amber-glow": "0 0 20px -3px rgba(217, 119, 6, 0.45), 0 0 8px -2px rgba(245, 158, 11, 0.3)",
        "amber-glow-lg": "0 0 35px -5px rgba(217, 119, 6, 0.6), 0 0 15px -3px rgba(245, 158, 11, 0.4)",
        "cyber-card": "0 8px 32px 0 rgba(0, 0, 0, 0.8), inset 0 1px 0 0 rgba(245, 158, 11, 0.15)",
      },
      fontFamily: {
        mono: ["Consolas", "Monaco", "Courier New", "monospace"],
      },
      backgroundImage: {
        "grid-pattern": "linear-gradient(to right, rgba(217, 119, 6, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(217, 119, 6, 0.05) 1px, transparent 1px)",
        "circuit-radial": "radial-gradient(circle at 50% 0%, rgba(217, 119, 6, 0.15) 0%, rgba(8, 9, 12, 0) 70%)",
      },
    },
  },
  plugins: [],
};

export default config;

