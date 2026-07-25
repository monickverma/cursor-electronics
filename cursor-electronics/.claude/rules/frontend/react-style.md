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
| `ChatPanel.tsx` | Auth form + chat input + message history | Handles both first-generate and follow-up-patch |
| `SchematicViewer.tsx` | Renders `.kicad_sch` via kicanvas | Must be `dynamic import`, `ssr: false` |
| `SimulationResults.tsx` | Polls simulation status every 3s | Clears interval on component unmount |
| `BOMTable.tsx` | Displays component list, CSV export | No live pricing in Phase 1 |
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

No global auth context, no localStorage persistence — Phase 1 simplicity. Phase 2 adds persistent sessions.

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
