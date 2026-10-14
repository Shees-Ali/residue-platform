import tailwindcssAnimate from "tailwindcss-animate";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#F8F7F2",
        foreground: "#1B241E",
        primary: { DEFAULT: "#245C43", foreground: "#FFFFFF" },
        secondary: { DEFAULT: "#D6A64D", foreground: "#27210F" },
        gold: "#D6A64D",
        card: { DEFAULT: "#FFFFFF", foreground: "#1B241E" },
        muted: { DEFAULT: "#EFF0EA", foreground: "#677069" },
        accent: { DEFAULT: "#DFF1E3", foreground: "#245C43" },
        border: "#E2E3DC",
        input: "#E2E3DC",
        ring: "#245C43",
        destructive: { DEFAULT: "#BD4238", foreground: "#FFFFFF" },
        overlay: "#050E0880",
        "gold-soft": "#FEF2D2",
        "blue-soft": "#DEEFFC",
        "blue-ink": "#31658D",
      },
      fontFamily: {
        sans: ["DM Sans", "sans-serif"],
        display: ["Manrope", "sans-serif"],
      },
      borderRadius: { sm: "4px", md: "6px", lg: "8px", xl: "8px" },
    },
  },
  plugins: [tailwindcssAnimate],
};
