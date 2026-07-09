import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0d1117",
        "bg-2": "#161b22",
        "bg-3": "#1a2332",
        border: "#21262d",
        "text-primary": "#c9d1d9",
        "text-muted": "#8b949e",
        accent: "#ecad0a",
        blue: "#209dd7",
        purple: "#753991",
        profit: "#3fb950",
        loss: "#f85149",
        "profit-bg": "#1f3a1f",
        "loss-bg": "#3a1f1f",
      },
    },
  },
  plugins: [],
};

export default config;
