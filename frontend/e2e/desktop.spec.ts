/**
 * The flow desktop (app/page.tsx, FloatWindow, FlowBackground):
 *  - the requirement as recorded is the headline;
 *  - each output is a window, opened from the dock and hidden from its own bar;
 *    a dock button never closes a window;
 *  - a window is dragged by its title bar and stays where it is dropped;
 *  - the water is drawn in WebGL 2, or the static dots stand in for it.
 *
 * Fixture: the same 1 kHz RC low-pass the validation tests use.
 */
import { expect, test, type Page, type Route } from '@playwright/test'
import generate from './fixtures/generate.json'

const API = 'http://backend.test'
type Json = Record<string, unknown>

async function mockBackend(page: Page, design: Json = generate as Json) {
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

  // Nothing leaves the machine: kicanvas' CDN script falls back to raw text.
  await page.route(url => !url.href.startsWith(API) && !url.href.includes('localhost'), r => r.abort())
  await page.route(`${API}/**`, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/health') return json(route, { status: 'ok', pcb_engine_enabled: false })
    if (path === '/auth/login') return json(route, { access_token: 'test-token', token_type: 'bearer' })
    // The library reads these as soon as someone is signed in (2026-11-16).
    if (path === '/auth/me') return json(route, { id: 'u1', email: 'engineer@example.com', tier: 'free', is_active: true })
    if (path === '/design/list') return json(route, [])
    if (path === '/projects') return json(route, [])
    if (path === '/design/generate') return json(route, design)
    if (path.includes('/simulation/')) return json(route, { status: 'queued' })
    return json(route, { detail: 'not mocked' }, 404)
  })
}

async function generateDesign(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: /open app/i }).first().click()
  await page.getByPlaceholder('Email address').fill('engineer@example.com')
  await page.getByPlaceholder('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Sign in' }).click()
  const prompt = page.getByPlaceholder('Describe your circuit…')
  await prompt.fill('RC low-pass filter, 1 kHz cutoff')
  await prompt.press('Enter')
  await expect(page.getByPlaceholder('Request a change…')).toBeVisible()
}

test('the recorded requirement is the headline', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText((generate as Json).intent as string)
})

test('outputs are windows: the dock opens them, their own bar hides them', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)

  // What is on the desktop when a design arrives.
  await expect(page.getByTestId('window-schematic')).toBeVisible()
  await expect(page.getByTestId('window-validation')).toBeVisible()
  await expect(page.getByTestId('window-firmware')).toHaveCount(0)

  const dock = page.getByRole('navigation', { name: 'Outputs' })
  const firmware = dock.getByRole('button', { name: 'Firmware', exact: true })
  await expect(firmware).toHaveAttribute('aria-pressed', 'false')
  await firmware.click()
  await expect(page.getByTestId('window-firmware')).toBeVisible()
  await expect(firmware).toHaveAttribute('aria-pressed', 'true')

  // Pressing the dock button again keeps the window: it never closes one.
  await firmware.click()
  await expect(page.getByTestId('window-firmware')).toBeVisible()

  await page.getByRole('button', { name: 'Hide Firmware' }).click()
  await expect(page.getByTestId('window-firmware')).toHaveCount(0)
  await expect(firmware).toHaveAttribute('aria-pressed', 'false')
  // The others are untouched.
  await expect(page.getByTestId('window-validation')).toBeVisible()
})

test('a window is dragged by its title bar and stays where it is dropped', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)

  const win = page.getByTestId('window-validation')
  await win.scrollIntoViewIfNeeded()
  const before = (await win.boundingBox())!
  const grip = { x: before.x + 80, y: before.y + 14 }

  await page.mouse.move(grip.x, grip.y)
  await page.mouse.down()
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(grip.x - i * 14, grip.y + i * 6)
    await page.waitForTimeout(16)
  }
  await page.mouse.up()
  // Let the throw run out.
  await page.waitForTimeout(2500)

  const after = (await win.boundingBox())!
  expect(before.x - after.x).toBeGreaterThan(100)
  expect(after.y - before.y).toBeGreaterThan(40)
  // Still there a moment later: it does not drift home.
  await page.waitForTimeout(600)
  const later = (await win.boundingBox())!
  expect(Math.abs(later.x - after.x)).toBeLessThan(12)
})

test('a docked window is all the desktop shows, beside the library, and Esc puts it back', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)
  const vp = page.viewportSize()!
  const schematic = page.getByTestId('window-schematic')
  const change = page.getByPlaceholder('Request a change…')

  await page.getByRole('button', { name: 'Dock Schematic on the right' }).click()
  await expect(schematic).toHaveAttribute('data-size', 'half')
  // From the library's edge to the right of the screen, full height, from the first frame.
  const box = (await schematic.boundingBox())!
  const library = (await page.getByRole('button', { name: 'Close the library' }).evaluate(
    b => b.closest('.fixed')!.getBoundingClientRect().right))
  expect(Math.abs(box.x - library)).toBeLessThan(2)
  expect(box.x + box.width).toBeGreaterThan(vp.width - 2)
  expect(box.y).toBe(0)
  expect(box.height).toBe(vp.height)
  // Nothing between them: the headline, the conversation and the other windows are hidden.
  await expect(change).toBeHidden()
  await expect(page.getByTestId('window-validation')).toBeHidden()

  // Esc typed in a text field is the field's (the library's search, beside the dock).
  const search = page.getByPlaceholder('Search your designs')
  await search.focus()
  await search.press('Escape')
  await expect(schematic).toHaveAttribute('data-size', 'half')
  await search.blur()
  await page.keyboard.press('Escape')
  await expect(schematic).toHaveAttribute('data-size', 'normal')
  // Back exactly as it was.
  await expect(change).toBeVisible()
  await expect(page.getByTestId('window-validation')).toBeVisible()
})

test('docking opens the library on the left, and the library stays usable', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)
  await page.getByRole('button', { name: 'Close the library' }).click()
  await expect(page.getByRole('button', { name: 'Open the library' })).toBeVisible()

  await page.getByRole('button', { name: 'Dock Claims and checks on the right' }).click()
  await expect(page.getByTestId('window-validation')).toHaveAttribute('data-size', 'half')
  await expect(page.getByRole('button', { name: 'Close the library' })).toBeVisible()
  // A point on the library reaches the library, not a hidden page or the dock.
  const inLibrary = await page.evaluate(() => {
    const el = document.elementFromPoint(100, window.innerHeight / 2)
    return !!el?.closest('.fixed') && !el.closest('[data-testid^="window-"]')
  })
  expect(inLibrary).toBe(true)
})

test('an output window goes full screen and comes back where it was', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)
  const vp = page.viewportSize()!
  const win = page.getByTestId('window-schematic')
  const before = (await win.boundingBox())!

  await page.getByRole('button', { name: 'Show Schematic full screen' }).click()
  await expect(win).toHaveAttribute('data-size', 'full')
  const full = (await win.boundingBox())!
  expect(full.x).toBeLessThanOrEqual(0)
  expect(full.y).toBeLessThanOrEqual(0)
  expect(full.width).toBeGreaterThanOrEqual(vp.width - 20)
  expect(full.height).toBeGreaterThanOrEqual(vp.height)

  await page.getByRole('button', { name: 'Leave full screen' }).click()
  await expect(win).toHaveAttribute('data-size', 'normal')
  await expect.poll(async () => (await win.boundingBox())!.height).toBeCloseTo(before.height, -1)
  expect(await page.evaluate(() => document.fullscreenElement)).toBeNull()

  // Double-clicking the title bar is the same switch.
  await win.locator('.win-bar').dblclick({ position: { x: 40, y: 12 } })
  await expect(win).toHaveAttribute('data-size', 'full')
})

test('only output windows can be docked or made full screen', async ({ page }) => {
  await mockBackend(page)
  await page.goto('/')
  await page.getByRole('button', { name: /open app/i }).first().click()
  const auth = page.getByTestId('window-auth')
  await expect(auth).toBeVisible()
  await expect(auth.getByRole('button', { name: /on the right|full screen/ })).toHaveCount(0)
})

test('the water is drawn in WebGL 2, or the static dots stand in', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)

  const water = page.getByTestId('flow-water')
  // Either the simulation sized its canvas to the viewport, or it hid itself.
  await expect
    .poll(() => water.evaluate((c: HTMLCanvasElement) => c.style.display === 'none' || c.width > 300))
    .toBe(true)
  const hidden = await water.evaluate((c: HTMLCanvasElement) => c.style.display === 'none')
  if (hidden) await expect(page.locator('.flow-fallback')).toBeAttached()
  // It never takes a click meant for the page.
  expect(await water.evaluate(c => getComputedStyle(c).pointerEvents)).toBe('none')
})

interface Ir {
  components: Array<{ id: string; part_number: string }>
  nodes: Array<{ id: string }>
  connections: Array<{ component_id: string; pin: string; node_id: string }>
}
const ir = (generate as Json).ir as Ir

test('the schematic draws every connection in the design, on the net the design names', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)

  const drawing = page.getByTestId('schematic-drawing')
  await expect(drawing).toBeVisible()
  // One dot per IR connection: none dropped, none invented.
  await expect(drawing.locator('[data-pin]')).toHaveCount(ir.connections.length)
  for (const c of ir.connections) {
    await expect(drawing.locator(`[data-pin="${c.component_id}.${c.pin}"]`)).toHaveAttribute('data-net', c.node_id)
  }
  for (const part of ir.components) await expect(drawing.locator(`[data-part="${part.id}"]`)).toHaveCount(1)
  for (const node of ir.nodes) await expect(drawing.locator(`[data-net-chip="${node.id}"]`)).toHaveCount(1)
})

test('a net is traced when kept, and a part says what it is', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)
  const drawing = page.getByTestId('schematic-drawing')
  const detail = page.getByTestId('schematic-detail')

  const net = ir.nodes[1].id
  const onNet = ir.connections.filter(c => c.node_id === net)
  const chip = drawing.locator(`[data-net-chip="${net}"]`)
  await chip.click()
  await expect(chip).toHaveAttribute('aria-pressed', 'true')
  for (const c of onNet) await expect(detail).toContainText(`${c.component_id}.${c.pin}`)
  // Kept, not hovered: it stays lit with the pointer elsewhere.
  await page.mouse.move(5, 5)
  // (A trace along one row has no height, which Playwright calls hidden: count it instead.)
  await expect(drawing.getByTestId('net-trace')).toHaveCount(1)

  const part = ir.components[0]
  await drawing.locator(`[data-part="${part.id}"]`).click()
  await expect(detail).toContainText(part.part_number)

  // The KiCad file is the same window, one click away, and comes back.
  await page.getByRole('button', { name: 'KiCad file' }).click()
  await expect(drawing).toHaveCount(0)
  await page.getByRole('button', { name: 'Drawing' }).click()
  await expect(page.getByTestId('schematic-drawing')).toBeVisible()
})

test('with a design open, the windows start within the first screen', async ({ page }) => {
  await mockBackend(page)
  await generateDesign(page)
  // Desktop Chrome in these tests is 1280 × 720. Before 2026-11-16 the first window began
  // below the fold on a 1000 px screen: the headline and the conversation took the top.
  const top = await page.getByTestId('window-schematic').evaluate(el => el.getBoundingClientRect().top + window.scrollY)
  expect(top).toBeLessThan(560)
})

test('the parts sheet lists every part beside its nets, and a catalogue find is only a request', async ({ page }) => {
  await mockBackend(page)
  // The catalogue search, answered with one part.
  const searches: string[] = []
  await page.route(`${API}/parts?**`, route => {
    searches.push(new URL(route.request().url()).searchParams.get('q') ?? '')
    return route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        query: 'dht', catalogue_size: 101, categories: ['sensor'],
        results: [{
          part_number: 'DHT22', manufacturer: 'Aosong', category: 'sensor', package: '4-pin SIP', value: null,
          description: 'Temperature and humidity sensor', supply_voltage_min: 3.3, supply_voltage_max: 5.5,
          current_draw_ma: 2.5, unit_price_usd: 3.5, price_asof: '2026-07-25', price_source: 'static',
          lcsc_pn: 'C19528', digikey_pn: null,
        }],
      }),
    })
  })
  await generateDesign(page)

  await page.getByRole('navigation', { name: 'Outputs' }).getByRole('button', { name: 'Parts', exact: true }).click()
  const sheet = page.getByTestId('parts-sheet')
  await expect(sheet.locator('[data-part-row]')).toHaveCount(ir.components.length)
  for (const part of ir.components) {
    const row = sheet.locator(`[data-part-row="${part.id}"]`)
    await expect(row).toContainText(part.part_number)
    for (const c of ir.connections.filter(x => x.component_id === part.id)) await expect(row).toContainText(c.node_id)
    await expect(row.getByRole('link', { name: 'Datasheet search' })).toHaveAttribute('href', /datasheet/)
  }

  // Typing searches; choosing a result writes a request and changes nothing by itself.
  await sheet.getByLabel('FIND A PART').fill('dht')
  await expect(sheet.getByTestId('parts-results')).toContainText('Temperature and humidity sensor')
  expect(searches.at(-1)).toBe('dht')
  await sheet.getByRole('button', { name: 'Ask for this part' }).click()
  await expect(page.getByPlaceholder('Request a change…')).toHaveValue(/^Use DHT22/)
})

test('the explanation is drawn as formatted text, never as raw mark-up', async ({ page }) => {
  // The fixture was exported without an explanation; give it one shaped like the real ones.
  const explained = {
    ...(generate as Json),
    explanation: [
      '## What you asked for', '', 'RC low-pass filter', '', '- **cutoff_hz**: 1000', '- supply_v: 5', '',
      '## Why each component', '', '**R1** (RC0402FR-073K4L)', '', 'Nearest E96 value to the ideal.',
    ].join('\n'),
  }
  await mockBackend(page, explained)
  await generateDesign(page)

  const explanation = page.getByTestId('explanation')
  await expect(explanation).toBeVisible()
  const text = await explanation.innerText()
  expect(text).not.toMatch(/^#{1,6}\s/m)
  expect(text).not.toContain('**')
  await expect(explanation.getByRole('heading', { name: 'Why each component' })).toBeVisible()
  await expect(explanation.getByRole('listitem')).toHaveCount(2)
  await expect(explanation.locator('strong', { hasText: 'cutoff_hz' })).toBeVisible()
  // The conversation shows its opening the same way.
  const log = page.getByRole('log', { name: 'Conversation' })
  expect(await log.innerText()).not.toMatch(/^#{1,6}\s/m)
})
