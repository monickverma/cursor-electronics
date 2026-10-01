/**
 * Stage 5 — firmware is shown only once it has compiled (FirmwareViewer).
 *  - While the build runs, the tab says so and polls; no source is shown.
 *  - When the poll says compiled, the source and platformio.ini appear.
 *  - A failed build shows its log and never its source, and is not polled.
 *
 * Fixtures: scripts/export_ui_fixtures.py — an ESP32 LED design and the
 * compile gate's own answers for it (api/routes/firmware.py::firmware_view).
 */
import { expect, test, type Page, type Route } from '@playwright/test'
import firmware from './fixtures/firmware.json'

const API = 'http://backend.test'
type Json = Record<string, unknown>
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))

/** Mock the backend; `answer()` is what a firmware poll returns right now. */
async function mockBackend(page: Page, design: Json, answer: () => Json) {
  const polls: string[] = []
  const times: number[] = []
  const unexpected: string[] = []
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

  await page.route(url => !url.href.startsWith(API) && !url.href.includes('localhost'), r => r.abort())
  await page.route(`${API}/**`, async route => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    if (path === '/health') return json(route, { status: 'ok', pcb_engine_enabled: false })
    if (path === '/auth/login') return json(route, { access_token: 'test-token', token_type: 'bearer' })
    if (path === '/design/generate') return json(route, design)
    if (path === `/design/${design.circuit_id}/firmware`) {
      polls.push(path)
      times.push(Date.now())
      return json(route, answer())
    }
    if (path.includes('/simulation/')) return json(route, { status: 'queued' })
    unexpected.push(`${req.method()} ${path}`)
    return json(route, { detail: 'not mocked' }, 404)
  })
  return { polls, times, unexpected }
}

async function openFirmware(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: /get started/i }).first().click()
  await page.getByPlaceholder('Email address').fill('engineer@example.com')
  await page.getByPlaceholder('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Sign in' }).click()
  const prompt = page.getByPlaceholder('Describe your circuit…')
  await prompt.fill('LED on an ESP32, 5 mA')
  await prompt.press('Enter')
  await expect(page.getByPlaceholder('Request a change…')).toBeVisible()
  await page.getByRole('button', { name: 'Firmware', exact: true }).click()
}

const design = firmware.generate as Json
const compiled = firmware.compiled as Json & { firmware: string; platformio_ini: string; board: string }

test('source appears only when the poll says it compiled', async ({ page }) => {
  // The build finishes when the test says so, not on a poll count.
  let built = false
  const backend = await mockBackend(page, design, () => (built ? compiled : (firmware.compiling as Json)))
  await openFirmware(page)

  await expect(page.getByText(/compiling for the ESP32-DevKitC/)).toBeVisible()
  await expect.poll(() => backend.polls.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(2)
  await page.waitForTimeout(6_500)
  await expect(page.getByText('#define', { exact: false })).toHaveCount(0)
  // Every 3 s, not a flood: the gaps after the first poll (React's dev-mode
  // double mount may fire two at once) are the interval.
  const gaps = backend.times.slice(1).map((t, i) => t - backend.times[i]).filter(g => g > 500)
  expect(gaps.length).toBeGreaterThanOrEqual(2)
  for (const gap of gaps) expect(gap).toBeGreaterThan(2_500)
  expect(backend.times.length).toBeLessThanOrEqual(gaps.length + 2)

  built = true
  await expect(page.getByText(`compiled for the ${compiled.board}`, { exact: false })).toBeVisible({ timeout: 15_000 })
  const firstLine = compiled.firmware.split('\n').find(l => l.trim().length > 0)!
  await expect(page.locator('pre')).toContainText(firstLine.trim())
  await expect(page.getByRole('button', { name: 'Download platformio.ini' })).toBeVisible()
  expect(backend.polls.length).toBeGreaterThanOrEqual(3)

  // Settled: no more polls.
  const settled = backend.polls.length
  await page.waitForTimeout(4_000)
  expect(backend.polls.length).toBe(settled)
  expect(backend.unexpected).toEqual([])
})

test('a failed build shows its log, never its source, and is not polled', async ({ page }) => {
  const failed = firmware.failed as Json & { log: string; message: string }
  const withFailure = clone(design)
  withFailure.firmware_build = Object.fromEntries(
    Object.entries(failed).filter(([k]) => k !== 'firmware' && k !== 'platformio_ini'))
  const backend = await mockBackend(page, withFailure, () => failed)
  await openFirmware(page)

  await expect(page.getByText(failed.message)).toBeVisible()
  await expect(page.locator('pre')).toContainText("'LED_PIN' was not declared")
  await expect(page.getByRole('button', { name: 'Download .ino' })).toHaveCount(0)
  await page.waitForTimeout(4_000)
  expect(backend.polls).toEqual([])
  expect(backend.unexpected).toEqual([])
})

test('a design with no microcontroller says so and polls nothing', async ({ page }) => {
  const passive = clone(design)
  passive.firmware_build = { status: 'none', message: 'this design has no microcontroller, so no firmware' }
  const backend = await mockBackend(page, passive, () => ({}))
  await openFirmware(page)
  await expect(page.getByText(/No firmware for this circuit type/)).toBeVisible()
  expect(backend.polls).toEqual([])
})
