import { test, expect } from '@playwright/test'

const email = `user${Date.now()}@example.com`
const password = 'secret123'

async function login(page){
  await page.goto('/login')
  await page.getByPlaceholder('you@example.com').fill(email)
  await page.getByPlaceholder('••••••••').fill(password)
  await page.getByRole('button', { name: 'Masuk' }).click()
}

test('register → login → analyze → open MTF tabs → verify error modal', async ({ page, baseURL, request }) => {
  // Try register via API to avoid UI dependency if disabled
  const reg = await request.post('http://127.0.0.1:18080/api/auth/register', { data: { email, password } })
  // Login via API to get token and set it in localStorage before opening the app
  const loginResp = await request.post('http://127.0.0.1:18080/api/auth/login', { data: { email, password } })
  const body = await loginResp.json()
  const token = body.access_token || body.token
  expect(token).toBeTruthy()
  await page.addInitScript((t) => {
    window.localStorage.setItem('access_token', t as string)
    window.localStorage.setItem('token', t as string)
    window.localStorage.setItem('role', 'user')
  }, token)

  await page.goto('/')
  // Wait until watchlist input appears (hydration + effect)
  await page.getByPlaceholder('OPUSDT').waitFor({ timeout: 15000 })
  // Add symbol in watchlist
  await page.getByPlaceholder('OPUSDT').fill('OPUSDT')
  await page.getByRole('button', { name: 'Tambah' }).click()
  // Trigger analyze via backend API, then reload UI to fetch latest cards
  await request.post('http://127.0.0.1:18080/api/analyze', {
    data: { symbol: 'OPUSDT' },
    headers: { 'Authorization': `Bearer ${token}` }
  })
  await page.reload()

  // Wait a bit for card to appear
  await expect(page.locator('text=Tren Utama')).toBeVisible({ timeout: 15000 })

  // Switch MTF tabs
  for (const tf of ['5m','15m','1h','4h']){
    await page.getByRole('tab', { name: tf }).click()
    await expect(page.locator('section:has-text("Tren & Momentum")')).toBeVisible()
  }
  // Back to Tren Utama
  await page.getByRole('tab', { name: 'Tren Utama' }).click()
  await expect(page.locator('text=Rencana Jual–Beli')).toBeVisible()

  // Click Tanya GPT; karena LLM tidak dikonfigurasi, seharusnya muncul modal error
  const btnVerify = page.getByRole('button', { name: 'Tanya GPT' })
  await btnVerify.click()
  // Modal error should appear
  await expect(page.locator('text=Verifikasi Gagal')).toBeVisible({ timeout: 15000 })
  // Tutup modal
  await page.getByRole('button', { name: 'Tutup' }).click()
});
