/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      screens: {
        wide: "1600px",
      },
      colors: {
        redis: {
          hyper: "#FF4438",
          "deep-hyper": "#EB352A",
        },
        "redis-text": {
          DEFAULT: "#F0F4F5",
          secondary: "#C8D1D5",
          link: "#8AB4C7",
          muted: "#5A6A72",
        },
        "redis-bg": {
          DEFAULT: "#0A1A23",
          secondary: "#122A35",
          tertiary: "#1C3A47",
        },
        "redis-border": {
          DEFAULT: "#2D4754",
          secondary: "#3D5764",
        },
        verdict: {
          approve: "#1FB36B",
          review: "#E2A03F",
          block: "#FF4438",
        },
      },
      fontFamily: {
        "redis-body": ['"Space Grotesk"', "sans-serif"],
        "redis-mono": ['"Space Mono"', "monospace"],
      },
      borderRadius: {
        redis: "5px",
      },
    },
  },
  plugins: [],
};

