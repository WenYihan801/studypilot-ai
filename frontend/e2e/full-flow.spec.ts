import { expect, test } from '@playwright/test'
import path from 'node:path'

// Full user journey against a REAL stack (Supabase + backend + Gemini or mock).
// Requires a confirmed test account: E2E_EMAIL / E2E_PASSWORD. Skipped otherwise.
const email = process.env.E2E_EMAIL
const password = process.env.E2E_PASSWORD
test.skip(!email || !password, 'E2E_EMAIL / E2E_PASSWORD not set')
test.describe.configure({ mode: 'serial' })

test('upload → grounded chat → quiz → flashcards → cleanup', async ({ page }) => {
  test.setTimeout(300_000)
  await page.goto('/login')
  await page.getByLabel('Email').fill(email!)
  await page.getByLabel('Password').fill(password!)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({ timeout: 90_000 })

  // Workspace
  const name = `E2E ${Date.now()}`
  await page.goto('/app/workspaces')
  await page.getByRole('button', { name: /new workspace/i }).first().click()
  await page.getByLabel('Course name').fill(name)
  await page.getByRole('button', { name: 'Create workspace' }).click()
  await page.getByRole('link', { name }).click()

  // Upload + wait for READY
  const file = path.resolve(__dirname, '../../sample_data/computer-networks-transport.md')
  await page.getByLabel('Upload documents').setInputFiles(file)
  await expect(page.getByText('Ready')).toBeVisible({ timeout: 120_000 })

  // Grounded chat with a source card
  await page.getByRole('link', { name: 'AI Chat' }).click()
  await page.getByLabel('Your question').fill('What is the difference between TCP and UDP?')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('computer-networks-transport.md').first()).toBeVisible({ timeout: 90_000 })

  // Quiz
  await page.getByRole('link', { name: 'Quiz Studio' }).click()
  await page.getByLabel('Questions').fill('3')
  await page.getByRole('button', { name: 'Generate quiz' }).click()
  await expect(page.getByRole('button', { name: 'Submit answers' })).toBeEnabled({ timeout: 120_000 })
  for (const group of await page.getByRole('radiogroup').all()) await group.getByRole('radio').first().check()
  await page.getByRole('button', { name: 'Submit answers' }).click()
  await expect(page.getByText(/of \d+ correct/)).toBeVisible({ timeout: 60_000 })

  // Flashcards
  await page.getByRole('link', { name: 'Quiz Studio' }).click()
  await page.getByRole('link', { name: 'Flashcards' }).click()
  await page.getByLabel('Number of cards').fill('3')
  await page.getByRole('button', { name: 'Generate flashcards' }).click()
  await page.getByRole('button', { name: 'Show answer' }).click({ timeout: 120_000 })
  await page.getByRole('button', { name: 'Mastered' }).click()

  // Cleanup: delete the workspace (removes files + vectors)
  await page.goto('/app/workspaces')
  await page.getByRole('button', { name: `Delete ${name}` }).click()
  await page.getByRole('button', { name: 'Delete permanently' }).click()
  await expect(page.getByText(name)).toHaveCount(0)
})
