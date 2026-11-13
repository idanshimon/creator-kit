// Probe: does selecting each entity keep the page responsive? usage: node probe-select.mjs file.html
import { chromium } from 'playwright-core';
const file = process.argv[2];
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on('pageerror', e => console.log('pageerror', e.message));
await page.goto('file://' + file);
await page.waitForTimeout(1500);
const ids = await page.evaluate(() => window.__mcDebug().nodes.map(n => n.id));
for (const id of ids) {
  const ok = await Promise.race([
    page.evaluate((a) => { const id = a.id;
      const cv = document.querySelector('canvas'); const r = cv.getBoundingClientRect();
      const t = window.__mcDebug().nodes.find(n => n.id === id);
      const o = { bubbles: true, clientX: r.left + t.sx + a.off, clientY: r.top + t.sy, pointerId: 1, isPrimary: true, button: 0, pointerType: a.pt };
      cv.dispatchEvent(new PointerEvent('pointerdown', o)); cv.dispatchEvent(new PointerEvent('pointerup', o));
      return new Promise(res => requestAnimationFrame(() => requestAnimationFrame(() => res(window.__mcDebug().selected))));
    }, {id, pt: process.env.PT || 'mouse', off: Number(process.env.OFF || 0)}),
    new Promise(res => setTimeout(() => res('HANG'), 4000)),
  ]);
  console.log(id, '->', ok);
  if (ok === 'HANG') break;
}
await browser.close();
process.exit(0);
