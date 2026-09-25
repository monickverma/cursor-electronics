/**
 * Stage 6 — the BOM tab (BOMTable). `brain/decisions.md` [2026-09-25] Stage 6.
 *  - Every price carries the date it was recorded; a part the catalogue does
 *    not hold as itself is "unknown", never priced as another part.
 *  - Substitutes arrive already checked; the refused ones say why.
 *  - "Use this part" sends exactly the substitute's patch, stays on the tab,
 *    and shows the re-derived design's BOM.
 *
 * Fixtures: scripts/export_ui_fixtures.py — an RS-485 node on the Uno, and
 * api/routes/bom.py::bom_view's own answers before and after the patch.
 */
import { expect, test, type Page, type Route } from '@playwright/test'
import bom from './fixtures/bom.json'

const API = 'http://backend.test'
type Json = Record<string, unknown>

async function mockBackend(page: Page) {
  const design = bom.generate as Json
  const patches: unknown[] = []
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
    if (path === `/design/${design.circuit_id}/bom`) return json(route, patches.length ? bom.bom_after : bom.bom)
    if (path === `/design/${design.circuit_id}/patch` && req.method() === 'POST') {
      patches.push(req.postDataJSON())
      return json(route, bom.patch)
    }
    if (path === `/design/${design.circuit_id}/firmware`) return json(route, { status: 'unavailable', message: 'n/a' })
    if (path.includes('/simulation/')) return json(route, { status: 'queued' })
    unexpected.push(`${req.method()} ${path}`)
    return json(route, { detail: 'not mocked' }, 404)
  })
  return { patches, unexpected }
}

async function openBom(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: /get started/i }).first().click()
  await page.getByPlaceholder('Email address').fill('engineer@example.com')
  await page.getByPlaceholder('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Sign in' }).click()
  const prompt = page.getByPlaceholder('Describe your circuit…')
  await prompt.fill('Modbus master on RS-485')
  await prompt.press('Enter')
  await expect(page.getByPlaceholder('Request a change…')).toBeVisible()
  await page.getByRole('button', { name: 'BOM', exact: true }).click()
}

test('prices are dated, and the terminator is never priced as an 0402', async ({ page }) => {
  const { unexpected } = await mockBackend(page)
  await openBom(page)
  const table = page.getByTestId('bom-table')
  const terminator = table.getByRole('row').filter({ hasText: 'RC1206FR-07120RL' })
  await expect(terminator).toContainText('unknown')
  await expect(terminator).not.toContainText('C25071')          // the 0402's LCSC number
  const priced = table.getByRole('row').filter({ hasText: 'CL05B104KO5NNNC' })
  await expect(priced).toContainText('2026-07-25')
  await expect(page.getByText('Live distributor pricing is not enabled.')).toBeVisible()
  expect(unexpected).toEqual([])
})

test('substitutes arrive checked, and the refused ones say why', async ({ page }) => {
  await mockBackend(page)
  await openBom(page)
  const panel = page.getByTestId('bom-substitutes')
  const first = bom.used as { part_number: string; checks: number }
  await expect(panel.getByText(first.part_number).first()).toBeVisible()   // R2 and R3 share it
  await expect(panel.getByText(`${first.checks} checks passed`).first()).toBeVisible()
  await panel.getByText(/checked and not offered/).click()
  await expect(panel.getByText(/RC0402FR-07120RL/)).toBeVisible()
  await expect(panel.getByText(/62\.5 mW rating/).first()).toBeVisible()
})

test('using a substitute sends its patch, stays on the tab and shows the new part', async ({ page }) => {
  const { patches } = await mockBackend(page)
  await openBom(page)
  const used = bom.used as { part_number: string; ops: unknown[] }
  const panel = page.getByTestId('bom-substitutes')
  await panel.getByRole('listitem').filter({ hasText: used.part_number }).first()
    .getByRole('button', { name: 'Use this part' }).click()
  await expect.poll(() => patches.length).toBe(1)
  expect(patches[0]).toEqual({ ops: used.ops })
  await expect(page.getByTestId('bom-table').getByRole('row').filter({ hasText: used.part_number })).toBeVisible()
})
