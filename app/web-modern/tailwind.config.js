/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{svelte,js,ts}'],
  theme: {
    extend: {
      spacing: {1:"var(--bf-space-1)",2:"var(--bf-space-2)",3:"var(--bf-space-3)",4:"var(--bf-space-4)",6:"var(--bf-space-6)"},
      borderRadius: {card:"var(--bf-radius-card)",control:"var(--bf-radius-control)",full:"var(--bf-radius-pill)"},
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
