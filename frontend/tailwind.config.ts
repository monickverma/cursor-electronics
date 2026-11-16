import type { Config } from 'tailwindcss'

/**
 * Every colour a panel uses is a CSS variable (an RGB triplet in globals.css),
 * so one component renders in either tone:
 *   - the default values are the dark "screen" tone;
 *   - inside `.paper` (a FloatWindow body) they flip to ink on white.
 * A panel never needs to know which window it sits in.
 */
const v = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        /* The desktop itself: fixed, never themed */
        ground:      '#16213f',
        ink:         '#141414',
        paper:       '#fefefe',
        /* Light side */
        lumen:       v('lumen'),
        'lumen-dim': v('lumen-dim'),
        /* Dark side */
        vast:        v('vast'),
        surface:     v('surface'),
        'surface-2': v('surface-2'),
        /* Accents */
        dawn:        v('dawn'),
        'dawn-dim':  v('dawn-dim'),
        fathom:      '#034f46',
        glow:        v('glow'),
        /* Legacy aliases kept so nothing breaks */
        cream:       v('cream'),
        'cream-dim': v('cream-dim'),
        dark:        v('dark'),
        lavender:    v('lavender'),
        'lavender-dim': v('lavender-dim'),
        border:      v('border'),
        muted:       v('muted'),
        /* Status: what a verdict or a grade is drawn in */
        ok:          v('ok'),
        bad:         v('bad'),
        warn:        v('warn'),
        info:        v('info'),
      },
      fontFamily: {
        serif: ['EB Garamond', 'Georgia', 'serif'],
        sans: ['Schibsted Grotesk', 'Figtree', 'system-ui', 'sans-serif'],
        mono: ['Space Mono', 'JetBrains Mono', 'ui-monospace', 'monospace'],
        pixel: ['VT323', 'Space Mono', 'ui-monospace', 'monospace'],
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
