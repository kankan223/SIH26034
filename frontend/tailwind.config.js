/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'var(--color-ink)',
        paper: 'var(--color-paper)',
        'paper-deep': 'var(--color-paper-deep)',
        verify: 'var(--color-verify)',
        redline: 'var(--color-redline)',
        amber: 'var(--color-amber)',
        'amber-text': 'var(--color-amber-text)',
        seal: 'var(--color-seal)',
      },
      fontFamily: {
        serif: ['Source Serif 4', 'Georgia', 'serif'],
        sans: ['IBM Plex Sans', '-apple-system', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        micro: 'var(--text-micro)',
        small: 'var(--text-small)',
        body: 'var(--text-body)',
        'body-serif': 'var(--text-body-serif)',
        label: 'var(--text-label)',
        section: 'var(--text-section)',
        title: 'var(--text-title)',
        display: 'var(--text-display)',
        'display-xl': 'var(--text-display-xl)',
      },
      spacing: {
        1: 'var(--space-1)',
        2: 'var(--space-2)',
        3: 'var(--space-3)',
        4: 'var(--space-4)',
        6: 'var(--space-6)',
        8: 'var(--space-8)',
        12: 'var(--space-12)',
        16: 'var(--space-16)',
      },
      borderRadius: {
        control: 'var(--radius-control)',
        surface: 'var(--radius-surface)',
      },
    },
  },
  plugins: [],
}
