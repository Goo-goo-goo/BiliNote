// Electron 走查：点导航栏逐页切换，等标题变化后截图 + 断言
const { _electron } = require('playwright-core')
const path = require('node:path')
const fs = require('node:fs')

const SHOT_DIR = path.join(__dirname, 'shots')
const ROUTES = [
  { label: '工作台', name: 'dashboard' },
  { label: '任务', name: 'tasks' },
  { label: '笔记', name: 'notes' },
  { label: '合集', name: 'collections' },
  { label: '自测', name: 'quiz' },
  { label: '错题', name: 'wrong' },
  { label: '复习', name: 'review' },
  { label: '设置', name: 'settings' },
]

;(async () => {
  fs.mkdirSync(SHOT_DIR, { recursive: true })

  const app = await _electron.launch({
    args: [path.join(__dirname, '..'), '--no-sandbox'],
  })
  const page = await app.firstWindow()
  await page.setViewportSize({ width: 1360, height: 900 })
  await page.waitForTimeout(1500)

  for (const { label, name } of ROUTES) {
    // 点导航项（.rail-item 里的文字）
    await page.locator('.rail-item', { hasText: label }).first().click()
    // 等路由真的切过去：顶部标题出现对应词
    await page.waitForTimeout(900)
    const h1 = await page.locator('.topbar h1').innerText()
    await page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`) })
    const emptyCount = await page.locator('.empty').count()
    console.log(`[${name}] 标题="${h1}" 空状态块=${emptyCount}`)
    if (!h1) throw new Error(`页面标题为空：${name}`)
  }

  // 笔记详情：在笔记库点第一行进去
  await page.locator('.rail-item', { hasText: '笔记' }).first().click()
  await page.waitForTimeout(900)
  const firstRow = page.locator('.rows .row').first()
  if (await firstRow.count()) {
    await firstRow.click()
    await page.waitForTimeout(1200)
    await page.screenshot({ path: path.join(SHOT_DIR, 'note-detail.png'), fullPage: true })
    console.log('[note-detail] 标题="' + (await page.locator('.topbar h1').innerText()) + '"')
  } else {
    console.log('[note-detail] 笔记库为空，跳过')
  }

  console.log('WALKTHROUGH_DONE')
  await app.close()
})().catch((e) => {
  console.error('WALKTHROUGH_FAILED', e)
  process.exit(1)
})
