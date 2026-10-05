/**
 * The board in 3D (Board3DView), drawn from the scene POST /pcb/compile returns.
 * decisions.md [2026-10-06].
 *  - The PCB tab opens on the 3D view and draws it into a WebGL canvas.
 *  - The view and layer buttons respond, and the 2D SVG is one click away.
 *  - What the board is *not* is on screen: unrouted connections and DRC errors
 *    are counted from the scene, and the bodies are labelled package-shaped.
 *
 * Fixture: scripts/export_ui_fixtures.py --only pcb — the composed room monitor
 * and the compile route's real answer for it (Board IR + 3D scene).
 */
import { expect, test, type Page, type Route } from '@playwright/test'
import pcb from './fixtures/pcb.json'

const API = 'http://backend.test'
type Json = Record<string, unknown>

const design = pcb.generate as Json
const compiled = pcb.compile as Json & {
  scene: { stats: { unrouted: number; drc_errors: number; components: number } }
}

async function mockBackend(page: Page) {
  const compiles: unknown[] = []
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

  await page.route(url => !url.href.startsWith(API) && !url.href.includes('localhost'), r => r.abort())
  await page.route(`${API}/**`, async route => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    if (path === '/health') return json(route, { status: 'ok', pcb_engine_enabled: true })
    if (path === '/auth/login') return json(route, { access_token: 'test-token', token_type: 'bearer' })
    if (path === '/design/generate') return json(route, design)
    if (path === '/pcb/compile') { compiles.push(req.postDataJSON()); return json(route, compiled) }
    if (path.endsWith('/explanation')) return json(route, { status: 'unavailable', explanation: null })
    if (path.includes('/simulation/')) return json(route, { status: 'queued' })
    if (path.endsWith('/firmware')) return json(route, { status: 'unavailable' })
    return json(route, { detail: 'not mocked' }, 404)
  })
  return { compiles }
}

async function openPcb(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: /get started/i }).first().click()
  await page.getByPlaceholder('Email address').fill('engineer@example.com')
  await page.getByPlaceholder('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Sign in' }).click()
  const prompt = page.getByPlaceholder('Describe your circuit…')
  await prompt.fill('Room monitor: an Uno reads a DHT22, sounds a buzzer above 30 °C, and lights a status LED')
  await prompt.press('Enter')
  await expect(page.getByPlaceholder('Request a change…')).toBeVisible()
  await page.getByRole('button', { name: 'PCB (experimental)' }).click()
}

test('the PCB tab opens on the board in 3D, drawn into WebGL', async ({ page }) => {
  const { compiles } = await mockBackend(page)
  await openPcb(page)

  const view = page.getByTestId('board-3d')
  await expect(view).toBeVisible()
  await expect(view.locator('canvas')).toBeVisible()
  // React StrictMode (dev) mounts effects twice; the first request is cancelled
  expect(compiles.length).toBeGreaterThanOrEqual(1)
  expect((compiles[0] as Json).components).toBeTruthy()

  // the camera eases in; give it time, then keep a picture for review
  await page.waitForTimeout(1500)
  await page.screenshot({ path: 'test-results/board3d-iso.png' })
})

test('views and layers respond, and the 2D board is one click away', async ({ page }) => {
  await mockBackend(page)
  await openPcb(page)
  await expect(page.getByTestId('board-3d')).toBeVisible()

  const top = page.getByRole('button', { name: 'Top', exact: true })
  await top.click()
  await expect(top).toHaveAttribute('aria-pressed', 'true')
  await page.waitForTimeout(1200)
  await page.screenshot({ path: 'test-results/board3d-top.png' })

  // click the microcontroller (board centre of U1, seen from the top) → its pins and nets
  const canvas = page.getByTestId('board-3d').locator('canvas')
  const box = (await canvas.boundingBox())!
  const u1 = (pcb.compile.scene.components as { ref: string; x: number; y: number }[])
    .find(c => c.ref === 'U1')!
  const { w, h, thickness } = pcb.compile.scene.board
  // Board3DView's top view: camera straight down from 1.55 x 1.15 x the longer side,
  // fov 35°, looking at the board centre. Project U1's body top (3.8 mm above the mask).
  const distance = Math.max(w, h) * 1.55 * 1.15 - (thickness + 3.8)
  const pxPerMm = box.height / (2 * distance * Math.tan((35 / 2) * Math.PI / 180))
  await page.mouse.click(box.x + box.width / 2 + (u1.x - w / 2) * pxPerMm,
                         box.y + box.height / 2 - (u1.y - h / 2) * pxPerMm)
  const panel = page.getByTestId('part-panel')
  await expect(panel, 'clicking U1 opens its panel').toBeVisible()
  await expect(panel.getByText('U1', { exact: true })).toBeVisible()
  await expect(panel.getByText('DIP-28')).toBeVisible()
  await expect(panel.getByText('VCC_5V').first()).toBeVisible()
  await page.screenshot({ path: 'test-results/board3d-selected.png' })
  await panel.getByRole('button', { name: 'Close' }).click()
  await expect(panel).toHaveCount(0)

  // lifting the parts animates them off the board and back; the picture changes
  await page.getByTestId('board-3d').getByRole('button', { name: '3D', exact: true }).click()
  await page.waitForTimeout(1200)
  const seated = await canvas.screenshot()
  await page.getByRole('button', { name: 'Lift parts' }).click()
  await page.waitForTimeout(1200)
  const lifted = await canvas.screenshot({ path: 'test-results/board3d-lifted.png' })
  expect(Buffer.compare(seated, lifted)).not.toBe(0)
  await page.getByRole('button', { name: 'Seat parts' }).click()

  const parts = page.getByRole('button', { name: 'Components', exact: true })
  await expect(parts).toHaveAttribute('aria-pressed', 'true')
  await parts.click()
  await expect(parts).toHaveAttribute('aria-pressed', 'false')

  await page.getByRole('button', { name: '2D', exact: true }).click()
  await expect(page.getByTestId('board-3d')).toHaveCount(0)
  await expect(page.locator('#pcb-panel svg')).toBeVisible()
})

test('what the board is not is on screen, counted from the scene', async ({ page }) => {
  await mockBackend(page)
  await openPcb(page)
  const { unrouted, drc_errors } = compiled.scene.stats
  const view = page.getByTestId('board-3d')
  await expect(view).toBeVisible()
  if (unrouted) await expect(view.getByText(`${unrouted} unrouted (dashed)`)).toBeVisible()
  else await expect(view.getByText('all connections routed')).toBeVisible()
  await expect(view.getByText(`${drc_errors} DRC error`, { exact: false })).toBeVisible()
  await expect(view.getByText(/package-shaped bodies, not manufacturer models/)).toBeVisible()
})
