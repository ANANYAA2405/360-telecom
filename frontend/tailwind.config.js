/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        signal: "#0e7490",
        field: "#f5f7f8",
        alert: "#b42318"
      }
    }
  },
  plugins: []
};

