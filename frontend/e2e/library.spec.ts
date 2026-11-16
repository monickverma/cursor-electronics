/**
 * The library (components/Library.tsx, app/page.tsx):
 *  - saved designs are listed, filed by project;
 *  - opening one brings back the design and the conversation behind it, rebuilt
 *    from the requirement and its patch history;
 *  - a design is filed under a project without anything else about it changing;
 *  - a reload keeps the session; signing out ends it.
 *
 * Fixture: the 1 kHz RC low-pass, as a design saved earlier and patched once.
 */
import { expect, test, type Page, type Route } from '@playwright/test'
import generate from './fixtures/generate.json'

const API = 'http://backend.test'
type Json = Record<string, unknown>

const saved = generate as Json
const ID = saved.circuit_id as string
const WHEN = '2026-11-10T09:30:00+00:00'

interface Backend {
  projects: Array<{ id: string; name: string; created_at: string }>
  filedUnder: string | null
  filings: Json[]
  opened: number
  unexpected: string[]
}

async function mockBackend(page: Page): Promise<Backend> {
  const backend: Backend = { projects: [], filedUnder: null, filings: [], opened: 0, unexpected: [] }
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

  await page.route(url => !url.href.startsWith(API) && !url.href.includes('localhost'), r => r.abort())
  await page.route(`${API}/**`, async route => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    const method = req.method()
    if (path === '/health') return json(route, { status: 'ok', pcb_engine_enabled: false })
    if (path === '/auth/login') return json(route, { access_token: 'test-token', token_type: 'bearer' })
    if (path === '/auth/me') {
      return req.headers().authorization === 'Bearer test-token'
        ? json(route, { id: 'u1', email: 'engineer@example.com', tier: 'free', is_active: true })
        : json(route, { detail: 'Invalid or expired token' }, 401)
    }
    if (path === '/design/list') {
      return json(route, [{
        circuit_id: ID, intent: saved.intent, application_class: saved.application_class, version: 2,
        simulation_passed: null, created_at: WHEN, updated_at: WHEN, target_mcu: null,
        project_id: backend.filedUnder,
      }])
    }
    if (path === '/projects' && method === 'GET') return json(route, backend.projects)
    if (path === '/projects' && method === 'POST') {
      const made = { id: `p${backend.projects.length + 1}`, name: (req.postDataJSON() as Json).name as string, created_at: WHEN }
      backend.projects.push(made)
      return json(route, made, 201)
    }
    if (path === `/design/${ID}` && method === 'GET') {
      backend.opened += 1
      return json(route, {
        ...saved, version: 2, simulation_job_id: null, project_id: backend.filedUnder,
        created_at: WHEN, updated_at: WHEN, patchable: true,
      })
    }
    if (path === `/design/${ID}/history`) {
      return json(route, {
        circuit_id: ID, current_version: 2, patchable: true,
        entries: [{
          from_version: 1, to_version: 2, kind: 'requirement_patch',
          changes: ['targets.cutoff_hz: 500 → 1000'], predict_delta: [],
          prompted_by: 'make the cutoff 1 kHz', created_at: WHEN,
        }],
      })
    }
    if (path === `/design/${ID}/project` && method === 'PUT') {
      const body = req.postDataJSON() as Json
      backend.filings.push(body)
      backend.filedUnder = (body.project_id as string | null) ?? null
      return json(route, { circuit_id: ID, project_id: backend.filedUnder })
    }
    backend.unexpected.push(`${method} ${path}`)
    return json(route, { detail: 'not mocked' }, 404)
  })
  return backend
}

async function signIn(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: /open app/i }).first().click()
  await page.getByPlaceholder('Email address').fill('engineer@example.com')
  await page.getByPlaceholder('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByTestId('library')).toBeVisible()
}

test('a saved design opens with its outputs and the conversation behind it', async ({ page }) => {
  const backend = await mockBackend(page)
  await signIn(page)

  const library = page.getByTestId('library')
  await expect(library.getByText('engineer@example.com')).toBeVisible()
  await library.locator(`[data-design="${ID}"]`).click()

  // The design is back: its requirement as the headline, its windows on the desktop.
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(saved.intent as string)
  await expect(page.getByTestId('window-schematic')).toBeVisible()
  await expect(page.getByTestId('schematic-drawing').locator('[data-pin]').first()).toBeAttached()

  // So is the conversation, from what was stored: the requirement, then the change and what it did.
  const log = page.getByRole('log', { name: 'Conversation' })
  await expect(log).toContainText(saved.intent as string)
  await expect(log).toContainText('make the cutoff 1 kHz')
  await expect(log).toContainText('targets.cutoff_hz: 500 → 1000')
  await expect(log).toContainText('Design became v2')
  // And it carries on as a patch, not a new design.
  await expect(page.getByPlaceholder('Request a change…')).toBeVisible()

  expect(backend.opened).toBe(1)
  expect(backend.unexpected).toEqual([])
})

test('a design is filed under a project, and only its filing changes', async ({ page }) => {
  const backend = await mockBackend(page)
  await signIn(page)
  const library = page.getByTestId('library')

  await library.getByRole('button', { name: '+ New project' }).click()
  await library.getByPlaceholder('Project name').fill('Filters')
  await library.getByRole('button', { name: 'Add' }).click()
  await expect(library.getByRole('region', { name: 'Filters' })).toBeVisible()

  await library.locator(`[data-design="${ID}"]`).click()
  await library.getByLabel('File under').selectOption({ label: 'Filters' })

  await expect.poll(() => backend.filings).toEqual([{ project_id: 'p1' }])
  await expect(library.getByRole('region', { name: 'Filters' }).locator(`[data-design="${ID}"]`)).toBeVisible()
  // Filing did not reopen or regenerate anything.
  expect(backend.opened).toBe(1)
  expect(backend.unexpected).toEqual([])
})

test('a reload keeps the session; New design starts clean; Sign out ends it', async ({ page }) => {
  await mockBackend(page)
  await signIn(page)
  await page.getByTestId('library').locator(`[data-design="${ID}"]`).click()
  await expect(page.getByPlaceholder('Request a change…')).toBeVisible()

  await page.getByTestId('library').getByRole('button', { name: '+ New design' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Describe Your Circuit')
  await expect(page.getByPlaceholder('Describe your circuit…')).toBeVisible()
  await expect(page.getByTestId('window-schematic')).toHaveCount(0)

  // Straight back into the app: no landing page, no sign-in form.
  await page.reload()
  await expect(page.getByTestId('library')).toBeVisible()
  await expect(page.getByPlaceholder('Email address')).toHaveCount(0)

  await page.getByTestId('library').getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('button', { name: /open app/i }).first()).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: /open app/i }).first()).toBeVisible()
  await expect(page.getByTestId('library')).toHaveCount(0)
})
