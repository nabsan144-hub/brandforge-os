/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{svelte,js,ts}'],
  theme: {
    extend: {
      colors: {
        bg:     'rgb(var(--bg-rgb) / <alpha-value>)',
        card:   'rgb(var(--card-rgb) / <alpha-value>)',
        inset:  'rgb(var(--inset-rgb) / <alpha-value>)',
        line:   'rgb(var(--line-rgb) / <alpha-value>)',
        ink:    'rgb(var(--ink-rgb) / <alpha-value>)',
        mut:    'rgb(var(--mut-rgb) / <alpha-value>)',
        faint:  'rgb(var(--faint-rgb) / <alpha-value>)',
        gold:   'rgb(var(--gold-rgb) / <alpha-value>)'
      }
    }
  },
  plugins: []
}
