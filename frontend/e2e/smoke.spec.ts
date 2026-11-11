import { expect, test } from '@playwright/test'

test('landing page explains the product and links to sign up', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('course materials')
  await page.getByRole('link', { name: 'Start studying free' }).click()
  await expect(page).toHaveURL(/\/register$/)
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
})

test('protected pages redirect to login when signed out', async ({ page }) => {
  await page.goto('/app/workspaces')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
})

test('privacy page discloses third-party AI processing', async ({ page }) => {
  await page.goto('/privacy')
  await expect(page.getByText(/sent to Google’s Gemini API/)).toBeVisible()
})

test('unknown routes show a 404 page (SPA rewrite works)', async ({ page }) => {
  await page.goto('/does-not-exist')
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
})
