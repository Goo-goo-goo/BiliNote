// 单页特写：设置页滚动到「下载 Cookie」面板截图
const { _electron } = require('playwright-core')
const path = require('node:path')

;(async () => {
  const app = await _electron.launch({ args: [path.join(__dirname, '..'), '--no-sandbox'] })
  const page = await app.firstWindow()
  await page.setViewportSize({ width: 1360, height: 900 })
  await page.waitForTimeout(1200)

  await page.locator('.rail-item', { hasText: '设置' }).first().click()
  await page.waitForTimeout(900)

  // 滚动到「下载 Cookie」面板
  await page.locator('.panel', { hasText: '下载 Cookie' }).first().scrollIntoViewIfNeeded()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(__dirname, 'shots', 'cookie-panel.png') })
  console.log('COOKIE_SHOT_DONE')
  await app.close()
})().catch((e) => {
  console.error('SHOT_FAILED', e)
  process.exit(1)
})
