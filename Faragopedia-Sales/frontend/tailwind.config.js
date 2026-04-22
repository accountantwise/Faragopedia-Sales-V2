/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: 'rgb(var(--color-primary) / <alpha-value>)',
        'primary-hover': 'rgb(var(--color-primary-hover) / <alpha-value>)',
        'bg-base': 'rgb(var(--color-bg-base) / <alpha-value>)',
        'bg-sidebar': 'rgb(var(--color-bg-sidebar) / <alpha-value>)',
        'bg-elevated': 'rgb(var(--color-bg-elevated) / <alpha-value>)',
        'text-base': 'rgb(var(--color-text-base) / <alpha-value>)',
        'text-muted': 'rgb(var(--color-text-muted) / <alpha-value>)',
        'border-color': 'rgb(var(--color-border) / <alpha-value>)',
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
