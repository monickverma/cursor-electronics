/**
 * Where each part of a design is drawn, worked out from the design itself.
 *
 * Input is the CircuitIR the backend returned: components, nodes, connections.
 * Nothing here chooses or changes a part, a pin or a net — it only places them.
 * Every connection in the IR becomes exactly one pin in the layout (`pins`),
 * which is what the UI test counts.
 *
 * The drawing keeps the project's net-label convention: nets join by name, not
 * by routed wires. The one exception is a net that only joins two two-pin parts
 * sitting next to each other (R3 → LED1): that is drawn as the short straight
 * wire it is, with the net's name on it.
 */

export interface IrComponent {
  id: string
  type: string
  value?: string | null
  part_number?: string | null
  manufacturer?: string | null
  package?: string | null
  justification?: string | null
}
export interface IrNode { id: string; type?: string | null; voltage_nominal?: number | null }
export interface IrConnection { component_id: string; pin: string; node_id: string; direction?: string | null }
export interface Ir { components: IrComponent[]; nodes: IrNode[]; connections: IrConnection[] }

/** Read an IR that arrived as untyped JSON. Null if it is not one. */
export function readIr(raw: unknown): Ir | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Record<string, unknown>
  if (!Array.isArray(r.components) || !Array.isArray(r.nodes) || !Array.isArray(r.connections)) return null
  const ok = (x: unknown, keys: string[]) =>
    !!x && typeof x === 'object' && keys.every(k => typeof (x as Record<string, unknown>)[k] === 'string')
  if (!r.components.every(c => ok(c, ['id', 'type']))) return null
  if (!r.nodes.every(n => ok(n, ['id']))) return null
  if (!r.connections.every(c => ok(c, ['component_id', 'pin', 'node_id']))) return null
  return { components: r.components, nodes: r.nodes, connections: r.connections } as Ir
}

export interface PinPoint { comp: string; pin: string; net: string; x: number; y: number }
export interface Flag { net: string; x: number; y: number; w: number; pin: PinPoint }
export interface Joint { net: string; x1: number; x2: number; y: number }
export interface TwoPin { comp: IrComponent; x: number; y: number; w: number; a: PinPoint; b: PinPoint }
export interface BoxPin extends PinPoint { side: 'left' | 'right'; innerX: number }
export interface Box { comp: IrComponent; x: number; y: number; w: number; h: number; pins: BoxPin[] }
export interface Layout {
  width: number
  height: number
  boxes: Box[]
  twoPins: TwoPin[]
  flags: Flag[]
  joints: Joint[]
  pins: PinPoint[]
}

/** A net label is as wide as its name needs. */
export const flagWidth = (net: string) => Math.max(46, Math.round(net.length * 7 + 18))
export const FLAG_H = 22
export const LEAD = 16
export const BODY_W = 64
const STEP = LEAD + BODY_W + LEAD
const jointWidth = (net: string) => Math.max(56, Math.round(net.length * 6.8 + 22))
const BOX_W = 122
const PIN_DY = 28
const TITLE_H = 26
const ROW_H = 40
const ROW_GAP = 26
const COL_GAP = 56
const MARGIN = 28

type Rank = 0 | 1 | 2
/** `left` is how far the item reaches left of its body, so a column can line the bodies up. */
interface Item { w: number; h: number; left: number; place: (x: number, y: number) => void }

export function layoutSchematic(ir: Ir): Layout {
  const out: Layout = { width: 0, height: 0, boxes: [], twoPins: [], flags: [], joints: [], pins: [] }
  const nodeType = new Map(ir.nodes.map(n => [n.id, n.type ?? '']))
  const rank = (net: string): Rank => {
    const t = nodeType.get(net)
    return t === 'power' ? 0 : t === 'ground' ? 2 : 1
  }

  const byComp = new Map<string, IrConnection[]>()
  const netUse = new Map<string, IrConnection[]>()
  for (const c of ir.connections) {
    byComp.set(c.component_id, [...(byComp.get(c.component_id) ?? []), c])
    netUse.set(c.node_id, [...(netUse.get(c.node_id) ?? []), c])
  }
  const index = new Map(ir.components.map((c, i) => [c.id, i]))
  const compOf = new Map(ir.components.map(c => [c.id, c]))
  const isTwoPin = (id: string) =>
    (byComp.get(id)?.length ?? 0) === 2 && compOf.get(id)?.type !== 'microcontroller'

  // ── Chains of two-pin parts joined by a net nothing else is on ──────────
  // partner(id, net): the other two-pin part on `net`, when the net is theirs alone.
  const partner = (id: string, net: string): string | null => {
    const use = netUse.get(net) ?? []
    if (use.length !== 2) return null
    const other = use.find(u => u.component_id !== id)
    return other && isTwoPin(other.component_id) ? other.component_id : null
  }
  const chained = new Set<string>()
  const chains: { comp: string; a: IrConnection; b: IrConnection }[][] = []
  const twoPinIds = ir.components.filter(c => isTwoPin(c.id)).map(c => c.id)
  const neighbours = (id: string) =>
    (byComp.get(id) ?? []).map(c => partner(id, c.node_id)).filter((x): x is string => !!x)

  const walk = (start: string) => {
    const chain: { comp: string; a: IrConnection; b: IrConnection }[] = []
    let current: string | null = start
    let cameBy: string | null = null
    while (current && !chained.has(current)) {
      chained.add(current)
      const [p, q] = byComp.get(current)!
      let a = p
      let b = q
      if (cameBy !== null) {
        if (q.node_id === cameBy) { a = q; b = p }
      } else if (partner(current, p.node_id) && !partner(current, q.node_id)) {
        a = q; b = p                               // the joined end faces the next part
      } else if (!partner(current, p.node_id) && !partner(current, q.node_id) && rank(p.node_id) > rank(q.node_id)) {
        a = q; b = p                               // alone: supply side on the left
      }
      chain.push({ comp: current, a, b })
      const next: string | null = partner(current, b.node_id)
      cameBy = b.node_id
      current = next && !chained.has(next) ? next : null
    }
    // Supply on the left, ground on the right.
    if (chain.length > 1 && rank(chain[0].a.node_id) > rank(chain[chain.length - 1].b.node_id)) {
      chain.reverse()
      for (const link of chain) { const t = link.a; link.a = link.b; link.b = t }
    }
    chains.push(chain)
  }
  for (const id of twoPinIds) if (!chained.has(id) && neighbours(id).length < 2) walk(id)
  for (const id of twoPinIds) if (!chained.has(id)) walk(id)       // a closed loop, if one ever appears

  // ── Items to place ────────────────────────────────────────────────────
  const pin = (c: IrConnection, x: number, y: number): PinPoint => {
    const p = { comp: c.component_id, pin: c.pin, net: c.node_id, x, y }
    out.pins.push(p)
    return p
  }

  const chainItem = (chain: typeof chains[number]): Item => {
    const leftW = flagWidth(chain[0].a.node_id)
    const rightW = flagWidth(chain[chain.length - 1].b.node_id)
    const joints = chain.slice(0, -1).map(link => jointWidth(link.b.node_id))
    return {
      w: leftW + chain.length * STEP + joints.reduce((n, j) => n + j, 0) + rightW,
      h: TITLE_H + ROW_H,
      left: leftW,
      place: (x, y) => {
        const cy = y + TITLE_H + ROW_H / 2
        let px = x + leftW
        chain.forEach((link, i) => {
          const a = pin(link.a, px, cy)
          const b = pin(link.b, px + STEP, cy)
          out.twoPins.push({ comp: compOf.get(link.comp)!, x: px, y: cy, w: STEP, a, b })
          if (i === 0) out.flags.push({ net: a.net, x: px - leftW, y: cy, w: leftW, pin: a })
          if (i === chain.length - 1) {
            out.flags.push({ net: b.net, x: px + STEP, y: cy, w: rightW, pin: b })
          } else {
            out.joints.push({ net: b.net, x1: px + STEP, x2: px + STEP + joints[i], y: cy })
            px += STEP + joints[i]
          }
        })
      },
    }
  }

  const boxItem = (comp: IrComponent, allRight: boolean): Item => {
    const conns = byComp.get(comp.id) ?? []
    let left = allRight ? [] : conns.filter(c => c.direction === 'input')
    let right = allRight ? conns : conns.filter(c => c.direction !== 'input')
    if (!allRight && left.length === 0 && right.length > 1) {
      left = right.slice(0, Math.ceil(right.length / 2))
      right = right.slice(left.length)
    }
    const rows = Math.max(left.length, right.length, 1)
    const widest = (list: IrConnection[]) => Math.max(...list.map(c => flagWidth(c.node_id)))
    const leftExtent = left.length ? widest(left) + LEAD : 0
    const rightExtent = right.length ? LEAD + widest(right) : 0
    const h = rows * PIN_DY + 12
    return {
      w: leftExtent + BOX_W + rightExtent,
      h: TITLE_H + h,
      left: leftExtent,
      place: (x, y) => {
        const bx = x + leftExtent
        const by = y + TITLE_H
        const pins: BoxPin[] = []
        left.forEach((c, i) => {
          const py = by + 6 + PIN_DY / 2 + i * PIN_DY
          const p = pin(c, bx - LEAD, py)
          pins.push({ ...p, side: 'left', innerX: bx })
          const fw = flagWidth(c.node_id)
          out.flags.push({ net: c.node_id, x: bx - LEAD - fw, y: py, w: fw, pin: p })
        })
        right.forEach((c, i) => {
          const py = by + 6 + PIN_DY / 2 + i * PIN_DY
          const p = pin(c, bx + BOX_W + LEAD, py)
          pins.push({ ...p, side: 'right', innerX: bx + BOX_W })
          out.flags.push({ net: c.node_id, x: bx + BOX_W + LEAD, y: py, w: flagWidth(c.node_id), pin: p })
        })
        out.boxes.push({ comp, x: bx, y: by, w: BOX_W, h, pins })
      },
    }
  }

  // The microcontroller stands on the left; everything else fills columns beside it,
  // in the order the design lists its parts (generators emit a block at a time).
  const mcu = ir.components.find(c => c.type === 'microcontroller' && (byComp.get(c.id)?.length ?? 0) > 0)
  const rest: { order: number; item: Item }[] = []
  for (const chain of chains) {
    rest.push({ order: Math.min(...chain.map(l => index.get(l.comp) ?? 0)), item: chainItem(chain) })
  }
  for (const comp of ir.components) {
    if (comp === mcu || chained.has(comp.id)) continue
    if ((byComp.get(comp.id)?.length ?? 0) === 0) continue      // a part with no connection has nothing to draw
    rest.push({ order: index.get(comp.id) ?? 0, item: boxItem(comp, false) })
  }
  rest.sort((p, q) => p.order - q.order)

  let x = MARGIN
  let height = 0
  if (mcu) {
    const item = boxItem(mcu, true)
    item.place(x, MARGIN)
    x += item.w + COL_GAP
    height = item.h
  }

  const total = rest.reduce((n, r) => n + r.item.h + ROW_GAP, 0)
  const columns = total > Math.max(height, 420) && rest.length > 3 ? 2 : 1
  const cols: Item[][] = Array.from({ length: columns }, () => [])
  const used = cols.map(() => 0)
  for (const r of rest) {
    const k = used.indexOf(Math.min(...used))
    cols[k].push(r.item)
    used[k] += r.item.h + ROW_GAP
  }
  let width = x
  cols.forEach((items, k) => {
    if (!items.length) return
    let y = MARGIN
    // Bodies line up down the column: each item is pushed right by what its labels do not need.
    const reach = Math.max(...items.map(i => i.left))
    const w = Math.max(...items.map(i => reach - i.left + i.w))
    for (const item of items) {
      item.place(x + reach - item.left, y)
      y += item.h + ROW_GAP
    }
    height = Math.max(height, used[k] - ROW_GAP)
    x += w + (k < cols.length - 1 ? COL_GAP : 0)
    width = x
  })

  out.width = Math.max(width, x) + MARGIN
  out.height = height + MARGIN * 2
  return out
}

/** "3400" on a resistor is 3.4 kΩ. Other parts are named by what they are. */
export function partLabel(c: IrComponent): string {
  const n = c.value != null && c.value !== '' ? Number(c.value) : NaN
  if (c.type === 'resistor' && Number.isFinite(n)) {
    const show = (v: number) => String(Number(v.toPrecision(4)))
    return n >= 1e6 ? `${show(n / 1e6)} MΩ` : n >= 1000 ? `${show(n / 1000)} kΩ` : `${show(n)} Ω`
  }
  if ((c.type === 'capacitor' || c.type === 'inductor') && c.value) return c.value
  return c.part_number ?? ''
}
