/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f4ff',
          100: '#e1e8ff',
          200: '#c8d5ff',
          300: '#a3b8ff',
          400: '#7a92ff',
          500: '#5368fe',
          600: '#3c47f5',
          700: '#3034e0',
          800: '#2729b5',
          900: '#242790',
          950: '#151755',
        }
      }
    },
  },
  plugins: [],
}
