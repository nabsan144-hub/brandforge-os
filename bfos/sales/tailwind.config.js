/** Sales site Tailwind config — palette wired to CSS vars (theme.css) so
    dark/light switching works without touching class names. */
export default {
  // ALL pages + inline JS class strings. Missing a page here = its classes
  // silently drop from assets/tailwind.css (incident 2026-08-30: tools/demo
  // absent → px-3.5/py-1.5 etc. vanished; nav button text clipped).
  content: ['./*.html', './assets/*.js'],
  theme: {
    extend: {
      colors: {
        bg:     'rgb(var(--sb-bg-rgb) / <alpha-value>)',
        card:   'rgb(var(--sb-card-rgb) / <alpha-value>)',
        line:   'rgb(var(--sb-line-rgb) / <alpha-value>)',
        gold:   'rgb(var(--sb-gold-rgb) / <alpha-value>)',
        muted:  'rgb(var(--sb-muted-rgb) / <alpha-value>)',
        ink:    'rgb(var(--sb-ink) / <alpha-value>)',
        faint:  'var(--sb-faint)',
        inset:  'rgb(var(--sb-inset-rgb) / <alpha-value>)'
      }
    }
  },
  plugins: []
}
