// Zoomed real-Chrome crops of scrolled regions (left rail, worklist, Ask log) in both themes.
// usage: node shot-scrollbars.mjs <url-or-file> <outdir>
import { chromium } from 'playwright-core';
const [src, out] = process.argv.slice(2);
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, ignoreDefaultArgs: ['--hide-scrollbars'] });  // headless hides scrollbars by default
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await p.goto(/^https?:/.test(src) ? src : 'file://' + src); await p.waitForTimeout(1200);
await p.evaluate(() => { document.querySelector('.workspace').scrollIntoView(); });
for (const t of ['dark', 'light']) {
  if (await p.evaluate(() => document.documentElement.dataset.theme) !== t) await p.click('#btn-theme');
  await p.waitForTimeout(300);
  const info = await p.evaluate(() => { const r = document.querySelector('.rail'); r.scrollTop = 200; const l = document.querySelector('.entity-list'); l.scrollTop = 150;
    const g = document.getElementById('mc-ask-log'); if (g) g.scrollTop = 100;
    return [r, l].map(e => ({ sh: e.scrollHeight, ch: e.clientHeight, st: e.scrollTop })); });
  console.log(t, JSON.stringify(info));
  await p.locator('.entity-list').scrollIntoViewIfNeeded();
  const box = await p.locator('.entity-list').boundingBox();
  // macOS uses overlay scrollbars that only show while scrolling: scroll with the wheel, then shoot at once.
  await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await p.mouse.wheel(0, 60); await p.waitForTimeout(120);
  await p.screenshot({ path: `${out}/scrollbar-list-${t}.png`, clip: { x: box.x - 14, y: box.y - 30, width: box.width + 28, height: box.height + 44 } });
  if (await p.locator('#mc-ask.open').count()) { const a = await p.locator('#mc-ask').boundingBox(); await p.screenshot({ path: `${out}/scrollbar-asklog-${t}.png`, clip: { x: a.x, y: a.y, width: a.width, height: Math.min(a.height, 600) } }); }
}
await b.close();
