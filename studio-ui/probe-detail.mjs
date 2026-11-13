// Probe: tapping an item opens the detail sheet; chips open watcher detail; Esc closes. usage: node probe-detail.mjs file.html [outdir]
import { chromium } from 'playwright-core';
const [file, out = '/tmp'] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
for (const [name, vp, touch] of [['desktop', { width: 1440, height: 900 }, false], ['phone', { width: 390, height: 844 }, true]]) {
  const page = await browser.newPage({ viewport: vp, hasTouch: touch, isMobile: touch });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.goto('file://' + file); await page.waitForTimeout(1200);
  const box = await page.locator('#map-canvas').boundingBox();
  const d = await page.evaluate(() => window.__mcDebug());
  const crit = d.nodes[0];
  await page.locator('#map-canvas').scrollIntoViewIfNeeded();
  const box2 = await page.locator('#map-canvas').boundingBox();
  if (touch) await page.touchscreen.tap(box2.x + crit.sx, box2.y + crit.sy); else await page.mouse.click(box2.x + crit.sx, box2.y + crit.sy);
  await page.waitForTimeout(400);
  const open = await page.evaluate(() => document.getElementById('mc-sheet').classList.contains('open'));
  const title = await page.textContent('#mc-sheet-title');
  const hasWhy = await page.locator('.mc-why').count(), opts = await page.locator('.mc-opt').count();
  await page.screenshot({ path: `${out}/detail-${name}.png` });
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  const closed = await page.evaluate(() => !document.getElementById('mc-sheet').classList.contains('open'));
  await page.click('#btn-help'); await page.waitForTimeout(300);
  const help = await page.textContent('#mc-sheet-title'); await page.keyboard.press('Escape');
  console.log(JSON.stringify({ name, open, title, hasWhy, opts, closed, help, errs }));
  await page.close();
}
await browser.close();
