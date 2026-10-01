/**
 * The Stage 3 + 4 UI, which until now was checked only by eye:
 *  - ClaimsTable: every claim is a row, most urgent first; "not assessed" and
 *    "out of scope" are printed rows, never omitted; the headline numbers.
 *  - PropertiesPanel: the sentence shown is the one signed; sign-off quotes the
 *    hash on screen; a 409 signs nothing and says why.
 *  - WaveformChart: the AC sweep ngspice produced is drawn.
 *
 * Fixtures: scripts/export_ui_fixtures.py (a 1 kHz RC low-pass, real pipeline).
 */
import { expect, test, type Page, type Route } from '@playwright/test'
import generate from './fixtures/generate.json'
import signOff from './fixtures/sign_off.json'
import simulation from './fixtures/simulation.json'

const API = 'http://backend.test'
const RANK: Record<string, number> = {
  fails: 0, not_assessed: 1, holds_defeasible: 2, holds: 3, not_applicable: 4, out_of_scope: 5,
}

type Json = Record<string, unknown>
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))

interface Backend {
  unexpected: string[]
  signOffBodies: Json[]
}

/** Mock every backend call; record anything a test did not expect. */
async function mockBackend(page: Page, opts: { design?: Json; signOff?: (route: Route) => Promise<void> } = {}) {
  const backend: Backend = { unexpected: [], signOffBodies: [] }
  const design = opts.design ?? (generate as Json)
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

  // Nothing leaves the machine: kicanvas' CDN script falls back to raw text.
  await page.route(url => !url.href.startsWith(API) && !url.href.includes('localhost'), r => r.abort())
  await page.route(`${API}/**`, async route => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    if (path === '/health') return json(route, { status: 'ok', pcb_engine_enabled: false })
    if (path === '/auth/login') return json(route, { access_token: 'test-token', token_type: 'bearer' })
    if (path === '/design/generate') return json(route, design)
    if (path.endsWith('/sign-off')) {
      backend.signOffBodies.push(req.postDataJSON())
      return opts.signOff ? opts.signOff(route) : json(route, signOff)
    }
    if (path.includes('/simulation/')) return json(route, simulation)
    backend.unexpected.push(`${req.method()} ${path}`)
    return json(route, { detail: 'not mocked' }, 404)
  })
  return backend
}

async function generateDesign(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: /get started/i }).first().click()
  await page.getByPlaceholder('Email address').fill('engineer@example.com')
  await page.getByPlaceholder('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Sign in' }).click()
  const prompt = page.getByPlaceholder('Describe your circuit…')
  await prompt.fill('RC low-pass filter, 1 kHz cutoff')
  await prompt.press('Enter')
  await expect(page.getByPlaceholder('Request a change…')).toBeVisible()
}

async function openTab(page: Page, name: string) {
  await page.getByRole('button', { name, exact: true }).click()
}

const coverage = (generate as Json).validation_coverage as {
  claims: Array<{ id: string; verdict: string; claim: string }>
  grade_floor: string
  open_defeaters: string[]
  properties: Array<{ id: string; english: string; grade: string }>
  properties_hash: string
}

test('every claim is a row, most urgent first, out-of-scope rows included', async ({ page }) => {
  const backend = await mockBackend(page)
  await generateDesign(page)
  await openTab(page, 'Validation')

  const headline = page.getByTestId('claims-headline')
  await expect(headline).toContainText(`Grade floor${coverage.grade_floor}`)
  await expect(headline).toContainText(coverage.open_defeaters.join(', '))

  const rows = page.getByTestId('claims-table').locator('tbody tr')
  await expect(rows).toHaveCount(coverage.claims.length)
  const verdicts = await rows.evaluateAll(trs => trs.map(tr => tr.getAttribute('data-verdict') ?? ''))
  const ranks = verdicts.map(v => RANK[v])
  expect(ranks).toEqual([...ranks].sort((a, b) => a - b))
  const outOfScope = coverage.claims.filter(c => c.verdict === 'out_of_scope').length
  expect(outOfScope).toBeGreaterThan(0)
  await expect(page.locator('tr[data-verdict="out_of_scope"]')).toHaveCount(outOfScope)
  for (const c of coverage.claims) await expect(page.getByTestId('claims-table')).toContainText(c.id)
  expect(backend.unexpected).toEqual([])
})

test('a not-assessed check is printed as a row and announced, never dropped', async ({ page }) => {
  const design = clone(generate) as Json
  const cov = design.validation_coverage as typeof coverage & { not_assessed: string[] }
  const target = cov.claims.find(c => c.verdict === 'not_applicable')!
  target.verdict = 'not_assessed'
  cov.not_assessed = [target.id]
  const backend = await mockBackend(page, { design })
  await generateDesign(page)
  await openTab(page, 'Validation')

  await expect(page.getByText('1 check(s) were not assessed on this design')).toBeVisible()
  const first = page.getByTestId('claims-table').locator('tbody tr').first()
  await expect(first).toHaveAttribute('data-verdict', 'not_assessed')
  await expect(first).toContainText(target.id)
  await expect(first).toContainText('not assessed')
  expect(backend.unexpected).toEqual([])
})

test('sign-off quotes the hash on screen, then the proofs count', async ({ page }) => {
  const backend = await mockBackend(page)
  await generateDesign(page)
  await openTab(page, 'Validation')

  const panel = page.getByTestId('properties-panel')
  for (const p of coverage.properties) await expect(panel).toContainText(p.english)
  await expect(panel).toContainText(`set ${coverage.properties_hash.slice(0, 16)}`)
  // Unsigned proofs are shown, and the table says they do not count.
  const proofId = `proof.${coverage.properties[0].id}`
  const proofRow = page.getByTestId('claims-table').locator('tr', { has: page.getByText(proofId, { exact: true }) })
  await expect(proofRow).toContainText('not counted')

  await panel.getByRole('button', { name: `Sign off these ${coverage.properties.length} properties` }).click()
  await expect(panel).toContainText('Signed off by engineer@example.com')
  expect(backend.signOffBodies).toEqual([{ properties_hash: coverage.properties_hash }])
  await expect(panel.getByRole('button', { name: /sign off/i })).toHaveCount(0)
  await expect(proofRow).not.toContainText('not counted')
  expect(backend.unexpected).toEqual([])
})

test('a refused sign-off signs nothing and says why', async ({ page }) => {
  const message = 'The properties you were shown are not this design\'s current ones.'
  const backend = await mockBackend(page, {
    signOff: route => route.fulfill({
      status: 409, contentType: 'application/json',
      body: JSON.stringify({ detail: { error: 'properties_changed', message } }),
    }),
  })
  await generateDesign(page)
  await openTab(page, 'Validation')

  const panel = page.getByTestId('properties-panel')
  const button = panel.getByRole('button', { name: /sign off these/i })
  await button.click()
  await expect(panel).toContainText(message)
  await expect(button).toBeEnabled()
  await expect(panel).not.toContainText('Signed off by')
  expect(backend.signOffBodies).toHaveLength(1)
  expect(backend.unexpected).toEqual([])
})

test('the AC sweep ngspice produced is drawn', async ({ page }) => {
  const backend = await mockBackend(page)
  await generateDesign(page)
  await openTab(page, 'Simulation')

  const figure = page.getByTestId('waveform-AC sweep')
  await expect(figure).toBeVisible({ timeout: 15_000 })   // first poll is 3 s in
  const series = Object.keys(simulation.results.waveforms.ac.series)
  await expect(figure.locator('svg')).toHaveAttribute('aria-label', new RegExp(series.join(', ')))
  const points = await figure.locator('polyline').evaluateAll(
    ls => ls.map(l => (l.getAttribute('points') ?? '').trim().split(/\s+/).length))
  expect(points.length).toBeGreaterThanOrEqual(series.length)
  expect(Math.max(...points)).toBeGreaterThan(10)
  // No transient in this design: the transient chart is not drawn empty.
  await expect(page.getByTestId('waveform-Transient')).toHaveCount(0)
  expect(backend.unexpected).toEqual([])
})
