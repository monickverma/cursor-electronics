import type { Config } from 'tailwindcss'

/*
 * Mirrors the tokens in app/globals.css (spec §3). Hex literals rather than
 * var() so opacity modifiers (`bg-fail/10`) work — change both files together.
 *
 * Colour only ever means a verdict: `pass`, `warn`, `fail`, `none`. Chrome is
 * `bench-*`, `line*` and `fg*`. Radius is 0 everywhere.
 *
 * Note: `none` collides with existing utilities (`border-none` is border-style,
 * `bg-none` is background-image). Use `text-none`, or the `.chip-none` /
 * `.c-none` classes from globals.css, for the "not assessed" grey.
 */
const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  // The component classes in globals.css (@layer components) are built from props at runtime
  // (`chip-${tone}`, `btn-${variant}`, `callout-${tone}` …), which the content scan cannot see.
  safelist: [
    { pattern: /^(btn|chip|callout|c)-(primary|secondary|ghost|danger|sm|md|lg|square|pass|warn|fail|none|info|neutral|mono|label|solid)$/ },
  ],
  theme: {
    // Zero radius everywhere.
    borderRadius: {
      none: '0',
      DEFAULT: '0',
      sm: '0',
      md: '0',
      lg: '0',
      xl: '0',
      '2xl': '0',
      '3xl': '0',
      full: '9999px',
    },
    extend: {
      colors: {
        'bench-0': '#000000',
        'bench-1': '#0a0a0a',
        'bench-2': '#111111',
        'bench-3': '#191919',
        'bench-4': '#222222',
        line: '#262626',
        'line-2': '#3d3d3d',
        fg: '#f2f2f2',
        'fg-2': '#a6a6a6',
        'fg-3': '#7c7c7c',
        paper: '#ffffff',
        'paper-2': '#f3f3f3',
        ink: '#000000',
        'ink-2': '#505050',
        'ink-3': '#737373',
        'paper-line': '#c8c8c8',
        pass: { DEFAULT: '#55b068', bg: 'rgba(85,176,104,0.10)' },
        warn: { DEFAULT: '#d9a441', bg: 'rgba(217,164,65,0.10)' },
        fail: { DEFAULT: '#e5484d', bg: 'rgba(229,72,77,0.10)' },
        none: '#7c7c7c',
      },
      borderColor: {
        DEFAULT: '#262626',
      },
      fontFamily: {
        sans: ['var(--font-sans)'],
        mono: ['var(--font-mono)'],
      },
      fontSize: {
        label: ['10.5px', { lineHeight: '1' }],
        small: ['12px', { lineHeight: '1.4' }],
        ui: ['13px', { lineHeight: '1.45' }],
        title: ['18px', { lineHeight: '1.2' }],
        display: ['32px', { lineHeight: '1' }],
      },
      height: {
        top: '40px',
        tabs: '36px',
        'sheet-head': '32px',
        status: '26px',
        row: '28px',
      },
      transitionDuration: {
        ui: '120ms',
      },
      animation: {
        'fade-in': 'fadeIn 120ms ease-out',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
      },
    },
  },
  plugins: [],
}
export default config
