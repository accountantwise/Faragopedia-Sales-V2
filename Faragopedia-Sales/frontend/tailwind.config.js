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
        primary: 'var(--color-primary)',
        'primary-hover': 'var(--color-primary-hover)',
        'bg-base': 'var(--color-bg-base)',
        'bg-sidebar': 'var(--color-bg-sidebar)',
        'bg-elevated': 'var(--color-bg-elevated)',
        'text-base': 'var(--color-text-base)',
        'text-muted': 'var(--color-text-muted)',
        'border-color': 'var(--color-border)',
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
