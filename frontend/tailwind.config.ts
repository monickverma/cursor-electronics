import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        /* Light side */
        lumen:       '#ffffeb',
        'lumen-dim': '#e4e4d0',
        /* Dark side */
        vast:        '#1a1a1a',
        surface:     '#242424',
        'surface-2': '#2e2e2e',
        /* Accents */
        dawn:        '#f0d7ff',
        'dawn-dim':  '#d8b8f5',
        fathom:      '#034f46',
        glow:        '#ffa946',
        /* Legacy aliases kept so nothing breaks */
        cream:       '#ffffeb',
        'cream-dim': '#e4e4d0',
        dark:        '#1a1a1a',
        lavender:    '#f0d7ff',
        'lavender-dim': '#d8b8f5',
        border:      '#383838',
        muted:       '#888888',
      },
      fontFamily: {
        serif: ['EB Garamond', 'Georgia', 'serif'],
        sans: ['Figtree', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: { from: { opacity: '0', transform: 'translateY(12px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
export default config
