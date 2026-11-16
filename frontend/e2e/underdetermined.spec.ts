/**
 * A request the producer will not guess at (422 underdetermined) is answered in the chat:
 *  - the reply names every missing field, not a generic line;
 *  - the next message is added to the original words, because "5 V, 10 mA" alone describes no circuit.
 */
import { expect, test, type Route } from '@playwright/test'
import firmware from './fixtures/firmware.json'

const API = 'http://backend.test'
const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

test('the answer is added to the original request, and the missing fields are named', async ({ page }) => {
  const prompts: string[] = []
  await page.route(url => !url.href.startsWith(API) && !url.href.includes('localhost'), r => r.abort())
  await page.route(`${API}/**`, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/health') return json(route, { status: 'ok', pcb_engine_enabled: false })
    if (path === '/auth/login') return json(route, { access_token: 'test-token', token_type: 'bearer' })
    // The library reads these as soon as someone is signed in (2026-11-16).
    if (path === '/auth/me') return json(route, { id: 'u1', email: 'engineer@example.com', tier: 'free', is_active: true })
    if (path === '/design/list') return json(route, [])
    if (path === '/projects') return json(route, [])
    if (path === '/design/generate') {
      const sent = (route.request().postDataJSON() as { prompt: string }).prompt
      prompts.push(sent)
      if (!/5 V/.test(sent)) {
        return json(route, {
          detail: {
            error: 'underdetermined',
            questions: ['targets.led_current_ma', 'constraints.supply_v'],
            message: 'The request does not pin these down. Supply them and resubmit.',
          },
        }, 422)
      }
      return json(route, firmware.generate)
    }
    if (path.includes('/simulation/')) return json(route, { status: 'queued' })
    return json(route, { detail: 'not mocked' }, 404)
  })

  await page.goto('/')
  await page.getByRole('button', { name: /open app/i }).first().click()
  await page.getByPlaceholder('Email address').fill('engineer@example.com')
  await page.getByPlaceholder('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Sign in' }).click()

  const box = page.getByPlaceholder('Describe your circuit…')
  await box.fill('LED blink with current-limiting resistor')
  await box.press('Enter')
  await expect(page.getByText('targets.led_current_ma')).toBeVisible()
  await expect(page.getByText('constraints.supply_v')).toBeVisible()
  await expect(page.getByText(/add them to your request/)).toBeVisible()
  // Each missing value is asked for as a question a person can answer; the path stays beside it.
  const log = page.getByRole('log', { name: 'Conversation' })
  await expect(log).toContainText('How much current should the LED get, in mA?  [targets.led_current_ma]')
  await expect(log).toContainText('What supply voltage does it run from, in volts?  [constraints.supply_v]')
  await expect(log).toContainText('I need 2 more values before I can build this:')

  await box.fill('5 V supply, 10 mA')
  await box.press('Enter')
  await expect(page.getByPlaceholder('Request a change…')).toBeVisible()
  expect(prompts).toEqual([
    'LED blink with current-limiting resistor',
    'LED blink with current-limiting resistor. 5 V supply, 10 mA',
  ])
})
