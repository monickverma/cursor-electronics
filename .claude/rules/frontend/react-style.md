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

## The Shell: the Flow Desktop

> **Amended 2026-11-15 (owner's choice of look; `brain/decisions.md` [2026-11-15]).** The two-panel
> layout is gone. `app/page.tsx` is a desktop: the requirement as recorded is the headline, the prompt
> bar and conversation sit under it, and each output is a `FloatWindow` on live water.

- **Outputs are windows, not tabs.** The dock (`nav[aria-label="Outputs"]`) opens a window and brings it
  forward; it never closes one. A window is hidden from its own title bar. Schematic and Validation are
  open when a design arrives; the rest open on request, so nothing polls or fetches unasked.
- **An output window can leave the layout** (amended 2026-11-27, owner's request): its title bar docks it
  to the right half or makes it full screen (Fullscreen API; double-click the bar too); Esc or the same
  button puts it back. A half dock on a wide screen is a split screen — the rest of the desktop moves into
  the left half and the library stays clickable. One window out at a time. Only windows given
  `maximizable` (the outputs in `page.tsx`) show these buttons.
- **`FloatWindow` moves by transform only** and stays in the page's layout, so the desktop reflows at any
  width. Its bob freezes in place while the pointer or focus is inside it — it does not even settle — so a click
  aimed at a point inside a window (a part on the 3D board) lands on that point.
- **`FlowBackground` is decoration.** Nothing reads it. It hides itself, leaving static dots, without
  WebGL 2, on a software renderer, or when frames stay slow. `prefers-reduced-motion` stills the windows.
- **A panel never knows its window's tone.** Colours are CSS variables (`globals.css`), read through
  Tailwind tokens. Inside `.paper` they are ink on white; the default is the dark "screen" tone (the 3D
  board). Use `text-ok / text-bad / text-warn / text-info`, never `text-green-300` and the like.

## Component Responsibilities

| Component | What it does | Key constraint |
|---|---|---|
| `ChatPanel.tsx` | Auth form + chat input + message history | Handles both first-generate and follow-up-patch |
| `SchematicViewer.tsx` | Renders `.kicad_sch` via kicanvas | Must be `dynamic import`, `ssr: false` |
| `SimulationResults.tsx` | Polls simulation status every 3s | Clears interval on component unmount |
| `BOMTable.tsx` | Displays component list, CSV export | Each price shows its source, currency and date; one total per currency, never converted (2026-09-25) |
| `ValidationReport.tsx` | Error/warning list + explanation text | Shows explanation from `ExplanationEngine` |
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

## Design System (Flow-Inspired)

> **Amended 2026-11-15.** The variables below still exist and still style the landing page. The app
> itself now uses: ground `#16213f`, ink `#141414`, paper `#fefefe`; `Schibsted Grotesk` (headline, body),
> `Space Mono` (data), `VT323` (window title bars). Tailwind: `bg-ground`, `text-ink`, `bg-paper`,
> `font-sans`, `font-mono`, `font-pixel`.

CSS variables defined in `app/globals.css`:

```css
--cream: #ffffeb;       /* primary text on dark backgrounds */
--dark: #1a1a1a;        /* page background */
--surface: #242424;     /* panel backgrounds */
--surface-2: #2e2e2e;   /* hover states */
--border: #383838;      /* borders, dividers */
--lavender: #f0d7ff;    /* accent — buttons, links, highlights */
--lavender-dim: #d8b8f5; /* hover state for lavender */
--muted: #888888;       /* secondary text */
```

Typography:
- Headings: `EB Garamond` (serif, weights 400/500/600)
- Body: `Figtree` (sans, weights 300/400/500)
- Code/values: `JetBrains Mono` (monospace)

Tailwind classes map directly to these vars (configured in `tailwind.config.ts`):
```tsx
<h1 className="text-lavender">        // --lavender accent
<p className="text-muted">            // --muted secondary text
<div className="bg-surface border border-border">  // panel
```

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

No global auth context.

> **Amended 2026-11-16 (the library; `brain/decisions.md` [2026-11-16] item 4).** The token is also kept in
> `localStorage` (`circuitos.token`) so a reload keeps the session and the library. `page.tsx` checks it
> against `/auth/me` before trusting it and drops it if refused; "Sign out" removes it. Because any script on
> the page could read it, **never build HTML from user or model text** (`dangerouslySetInnerHTML`,
> `innerHTML`): render it as React elements, as `Markdown.tsx` does.

---

## Tailwind: Using Design Tokens

Always use Tailwind classes mapped to the design system rather than arbitrary values:

```tsx
// CORRECT — uses design tokens
<button className="bg-lavender text-dark hover:bg-lavender-dim">

// WRONG — arbitrary values bypass the design system
<button style={{ backgroundColor: '#f0d7ff' }}>
```

The only exception is inline styles for dynamic values (e.g., animation delays):
```tsx
style={{ animationDelay: `${i * 200}ms` }}
```
