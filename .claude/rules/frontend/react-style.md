# Frontend / React Style — Circuit OS

## Rule: kicanvas Requires `dynamic import` with `ssr: false`

kicanvas uses browser-only APIs (`document`, `customElements`, `URL.createObjectURL`). It cannot run during Next.js server-side rendering.

```tsx
// CORRECT — page.tsx
import dynamic from 'next/dynamic'

const SchematicViewer = dynamic(
  () => import('@/components/SchematicViewer'),
  { ssr: false }
)

// WRONG — crashes the server render with "document is not defined"
import SchematicViewer from '@/components/SchematicViewer'
```

The `SchematicViewer` component itself also must not reference `document` at module level — only inside `useEffect`:

```tsx
// CORRECT — inside useEffect, runs only in browser
useEffect(() => {
  const blob = new Blob([schematic], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  // inject kicanvas-embed element
}, [schematic])

// WRONG — runs during SSR
const blob = new Blob([schematic])  // module-level — crashes
```

---

## Next.js API Proxy Pattern

The frontend never calls the FastAPI backend directly at `http://localhost:8000` from user-facing components. It goes through a Next.js route handler that forwards requests:

```
Browser → POST /api/design → Next.js route.ts → http://localhost:8000/design/generate
```

This avoids CORS issues in production where backend and frontend are on different domains.

```ts
// frontend/app/api/design/route.ts
export async function POST(req: NextRequest) {
  const token = req.headers.get('authorization') || ''
  const upstream = await fetch(`${BACKEND}/design/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: token } : {}) },
    body: await req.text(),
  })
  return NextResponse.json(await upstream.json(), { status: upstream.status })
}
```

For direct API calls in `lib/api.ts`, use the `NEXT_PUBLIC_API_URL` env var — defaults to `http://localhost:8000`.

---

## Component Responsibilities

| Component | What it does | Key constraint |
|---|---|---|
| `ChatPanel.tsx` | Sign-in + the requirement console (tagged transcript, composer) | Handles both first-generate and follow-up-patch |
| `SchematicViewer.tsx` | Renders `.kicad_sch` via kicanvas | Must be `dynamic import`, `ssr: false` |
| `SimulationResults.tsx` | Polls simulation status every 3s | Clears interval on component unmount |
| `BOMTable.tsx` | Displays component list, CSV export | Each price shows its source, currency and date; one total per currency, never converted (2026-09-25) |
| `ValidationReport.tsx` | Rules, claims, proved properties | The explanation lives on the Overview sheet (`workbench/OverviewSheet.tsx`) since 2026-11-13 |
| `workbench/*` | Top bar, sheet tabs, status bar (title block), Overview sheet | Shows only values present in the response; a cell with no data is omitted |
| `ui/*` | Primitives: `Button`, `VerdictBadge`, `SheetFrame`, `Section`, `Callout`, `Prose`… | Panels use these; no panel defines its own colours or buttons |
| `FirmwareViewer.tsx` | Code display + `.ino` download | Returns null message for passive circuits |

---

## Simulation Polling Pattern

`SimulationResults.tsx` polls every 3 seconds until `status === "complete"` or `status === "failed"`:

```tsx
useEffect(() => {
  if (!circuitId || !jobId) return
  const id = setInterval(async () => {
    const s = await pollSimulation(circuitId, jobId, token)
    setStatus(s)
    if (s.status === 'complete' || s.status === 'failed') {
      clearInterval(id)
    }
  }, 3000)
  return () => clearInterval(id)   // cleanup on unmount — prevent memory leaks
}, [circuitId, jobId, token])
```

The interval is cleared in the cleanup function. If the component unmounts while polling is active, no further network requests are made.

---

## Design System — "Drawing Set"

> **Replaced 2026-11-13** (`brain/decisions.md` [2026-11-13]). The cream / lavender "Flow" system and its
> serif headings are gone. The landing page and the app now share one system.

The app is a drawing set: numbered sheets (`00 Overview` … `06 Validation`), a title block that is always
visible (the status bar), hairlines, zero radius, no shadows. **Monochrome — colour only ever means a
verdict.**

Tokens are owned by `frontend/app/globals.css` (`:root`) and mirrored in `tailwind.config.ts`. Read them
there; do not restate the values in another file.

| Group | Tokens | Use |
|---|---|---|
| Bench (dark) | `--bench-0…4`, `--line`, `--line-2`, `--fg`, `--fg-2`, `--fg-3` | The app, the landing hero and footer. `--fg-3` is the darkest grey allowed for text |
| Paper (light) | `--paper`, `--paper-2`, `--ink`, `--ink-2`, `--ink-3`, `--paper-line` | Landing body sections only |
| Verdicts | `--pass`, `--warn`, `--fail`, `--none` (+ `-bg`) | Holds / holds, defeasible / fails / not assessed. Nothing else is coloured |
| Type | `--font-sans` (Archivo, width axis), `--font-mono` (JetBrains Mono) | Loaded with `next/font` in `app/layout.tsx` |

Type classes: `.t-label` (condensed uppercase lettering), `.t-ui` (13px), `.t-small`, `.t-data` (mono,
tabular), `.t-title`, `.t-display`. Tables: `.dt`. The root font size is 16px, so Tailwind spacing lands
on the 4px grid; body text is 13px.

```tsx
// CORRECT — a verdict is the only thing that carries colour, and never colour alone
<VerdictBadge verdict={claim.verdict} />          // glyph + word + token
<Button variant="primary">Send</Button>           // white on black

// WRONG — decoration, or an unknown value dressed as a warning
<span className="text-warn">unknown</span>        // an unknown price is grey, not a verdict
<button style={{ backgroundColor: '#ffa946' }}>   // no hex colours, no amber buttons
```

Rules that follow:

- A sheet-level panel renders its own `SheetFrame`; the workbench supplies the sheet number and title.
- The shell and the Overview show only what the API response carries. No zeros or dashes for missing data.
- Sheet tabs are buttons whose accessible names are exactly `Overview`, `Schematic`, `PCB (experimental)`,
  `Firmware`, `Simulation`, `BOM`, `Validation` — the e2e suite opens them by name.
- The landing page keeps a button named `Get started` first in the DOM: every e2e test starts there.
- Motion in the app is 120ms colour fades and a blinking cursor for work in progress; the landing keeps
  its Lenis + GSAP scroll. Both respect `prefers-reduced-motion`.

---

## Token / Auth State Pattern

Auth state lives in `page.tsx` as a `useState` string. It is passed down to `ChatPanel` and used in every API call:

```tsx
// page.tsx
const [token, setToken] = useState<string>('')

<ChatPanel
  token={token}
  onTokenChange={setToken}  // ChatPanel calls this after login/register
  ...
/>
```

No global auth context, no localStorage persistence — Phase 1 simplicity. Phase 2 adds persistent sessions.

---

## Tailwind: Using Design Tokens

Use the component classes and primitives first, then Tailwind classes mapped to the tokens
(`bg-bench-2`, `text-fg-2`, `border-line`, `text-pass`). Never arbitrary colour values:

```tsx
// CORRECT — design tokens
<div className="bg-bench-2 border border-line text-fg-2">

// WRONG — arbitrary values bypass the design system
<div style={{ backgroundColor: '#242424' }}>
```

The only exception is inline styles for dynamic values (a measured width, an animation delay), and the
3D board's scene materials in `Board3DView.tsx`, which are the board's own colours, not the UI's.
