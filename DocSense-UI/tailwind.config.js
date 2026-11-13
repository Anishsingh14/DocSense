/** Tailwind config: every colour resolves to the design tokens in src/styles/tokens.css. */
export default {
      theme: {
        /* Replacing the palette outright so no default Tailwind color can be used */
        colors: {
          transparent: 'transparent',
          current: 'currentColor',
          inherit: 'inherit',
          page: 'rgb(var(--ds-page) / <alpha-value>)',
          section: 'rgb(var(--ds-section) / <alpha-value>)',
          card: 'rgb(var(--ds-card) / <alpha-value>)',
          raised: 'rgb(var(--ds-raised) / <alpha-value>)',
          shade: 'rgb(var(--ds-shade) / <alpha-value>)',
          khaki: 'rgb(var(--ds-khaki) / <alpha-value>)',
          ink: 'rgb(var(--ds-ink) / <alpha-value>)',
          burgundy: 'rgb(var(--ds-burgundy) / <alpha-value>)',
          espresso: 'rgb(var(--ds-espresso) / <alpha-value>)',
          muted: 'rgb(var(--ds-muted) / <alpha-value>)',
          placeholder: 'rgb(var(--ds-placeholder) / <alpha-value>)',
          gold: 'rgb(var(--ds-gold) / <alpha-value>)',
          cream: 'rgb(var(--ds-cream) / <alpha-value>)',
          sand: 'rgb(var(--ds-sand) / <alpha-value>)',
          clay: 'rgb(var(--ds-clay) / <alpha-value>)',
          overlay: 'rgb(var(--ds-overlay) / <alpha-value>)',
          danger: 'rgb(var(--ds-danger) / <alpha-value>)',
          success: {
            DEFAULT: 'rgb(var(--ds-success) / <alpha-value>)',
            deep: 'rgb(var(--ds-success-deep) / <alpha-value>)',
            soft: 'rgb(var(--ds-success-soft) / <alpha-value>)',
            line: 'rgb(var(--ds-success-line) / <alpha-value>)'
          },
          highlight: {
            DEFAULT: 'rgb(var(--ds-highlight) / <alpha-value>)',
            mark: 'rgb(var(--ds-highlight-mark) / <alpha-value>)',
            line: 'rgb(var(--ds-highlight-line) / <alpha-value>)'
          },
          doc: {
            pdf: 'rgb(var(--ds-doc-pdf) / <alpha-value>)',
            docx: 'rgb(var(--ds-doc-docx) / <alpha-value>)',
            txt: 'rgb(var(--ds-doc-txt) / <alpha-value>)'
          },
          dot: {
            close: 'rgb(var(--ds-dot-close) / <alpha-value>)',
            min: 'rgb(var(--ds-dot-minimize) / <alpha-value>)',
            max: 'rgb(var(--ds-dot-maximize) / <alpha-value>)'
          },
          live: 'rgb(var(--ds-live) / <alpha-value>)'
        },
        fontFamily: {
          sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        },
        boxShadow: {
          'soft': '0 8px 30px rgb(var(--ds-ink) / 0.07)',
          'card': '0 12px 36px -4px rgb(var(--ds-ink) / 0.12)',
          'glow': '0 0 45px rgb(var(--ds-burgundy) / 0.30)',
          'float': '0 20px 40px -10px rgb(var(--ds-ink) / 0.18)'
        }
      },
  content: ['./index.html', './src/**/*.{js,jsx}'],
  corePlugins: { preflight: false },
}
