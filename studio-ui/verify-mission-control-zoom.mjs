// Real-browser proof for Mission Control map gestures: wheel zoom toward the cursor,
// mouse drag pan, click-to-select, and touch pinch / one-finger pan / tap via CDP touch events.
// Usage (from studio-ui): node verify-mission-control-zoom.mjs <mission-control.html>
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const file = path.resolve(process.argv[2]);
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true});
const results = [];
const errors = [];

// ---------- desktop mouse ----------
{
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(pathToFileURL(file).href);
  await page.waitForTimeout(600);
  const box = await page.locator('.map-stage canvas').boundingBox();
  const label = () => page.locator('#zoom-reset').textContent();
  // Pick a node, record its screen position, wheel-zoom on it, it must stay under the cursor.
  const nodeAt = () => page.evaluate(() => window.__mcDebug && window.__mcDebug());
  const before = await nodeAt();
  assert.ok(before, 'debug hook present');
  const n = before.nodes[0];
  await page.mouse.move(box.x + n.sx, box.y + n.sy);
  for (let i = 0; i < 5; i++) { await page.mouse.wheel(0, -200); await page.waitForTimeout(40); }
  await page.waitForTimeout(150);
  const after = await nodeAt();
  const n2 = after.nodes.find(m => m.id === n.id);
  assert.ok(after.k > 1.8, `wheel zoomed in (k=${after.k})`);
  assert.ok(Math.hypot(n2.sx - n.sx, n2.sy - n.sy) < 3, `node stayed under cursor (moved ${Math.hypot(n2.sx - n.sx, n2.sy - n.sy).toFixed(1)}px)`);
  assert.equal(await label(), Math.round(after.k * 100) + '%');
  const scrollY = await page.evaluate(() => window.scrollY);
  assert.equal(scrollY, 0, 'wheel over map does not scroll the page');
  results.push(`wheel zoom toward cursor: k=${after.k.toFixed(2)}, label ${await label()}, page not scrolled`);

  // Drag pan
  await page.mouse.move(box.x + 100, box.y + 100);
  await page.mouse.down();
  await page.mouse.move(box.x + 180, box.y + 140, {steps: 6});
  await page.mouse.up();
  const panned = await nodeAt();
  assert.ok(Math.abs(panned.x - after.x - 80) < 2 && Math.abs(panned.y - after.y - 40) < 2, 'drag pans by pointer delta');
  assert.equal(panned.selected, after.selected, 'drag does not select');
  results.push('mouse drag pans 80,40 without selecting');

  // Click a different node selects it
  const target = panned.nodes.find(m => m.id !== panned.selected && m.sx > 20 && m.sy > 20 && m.sx < box.width - 20 && m.sy < box.height - 20);
  await page.mouse.click(box.x + target.sx, box.y + target.sy);
  await page.waitForTimeout(100);
  assert.equal((await nodeAt()).selected, target.id, 'click selects node at zoom');
  results.push(`click at zoom selects ${target.id}`);

  await page.mouse.dblclick(box.x + 30, box.y + box.height - 30);
  const reset = await nodeAt();
  assert.equal(reset.k, 1); assert.equal(reset.x, 0);
  results.push('double-click resets to 100%');
  await page.close();
}

// ---------- mobile touch via CDP ----------
{
  const ctx = await browser.newContext({viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true, deviceScaleFactor: 2});
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(pathToFileURL(file).href);
  await page.waitForTimeout(600);
  const cdp = await ctx.newCDPSession(page);
  const canvas = page.locator('.map-stage canvas');
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  const st = () => page.evaluate(() => window.__mcDebug());
  const touch = (type, pts) => cdp.send('Input.dispatchTouchEvent', {type, touchPoints: pts.map(([x, y], i) => ({x: box.x + x, y: box.y + y, id: i}))});
  const cx = box.width / 2, cy = box.height / 2;
  // Pinch out
  await touch('touchStart', [[cx - 30, cy], [cx + 30, cy]]);
  for (let i = 1; i <= 8; i++) await touch('touchMove', [[cx - 30 - i * 12, cy], [cx + 30 + i * 12, cy]]);
  const pinched = await st();
  await touch('touchEnd', []);
  assert.ok(pinched.k > 2.2, `pinch zoomed (k=${pinched.k})`);
  results.push(`real CDP touch pinch: k=${pinched.k.toFixed(2)}`);
  // One finger lifts mid-pinch and the other keeps panning. CDP touch events cannot lift
  // a single finger, so this step uses dispatched PointerEvents (same handlers, synthetic input).
  const cont = await page.evaluate(() => {
    const cv = document.querySelector('.map-stage canvas'), r = cv.getBoundingClientRect();
    const ev = (type, id, x, y) => cv.dispatchEvent(new PointerEvent(type, {pointerId: id, pointerType: 'touch', clientX: r.left + x, clientY: r.top + y, bubbles: true, isPrimary: id === 1}));
    cv.setPointerCapture = () => {};
    ev('pointerdown', 1, 100, 200); ev('pointerdown', 2, 200, 200);
    ev('pointermove', 2, 240, 200);            // pinch a little
    const a = window.__mcDebug();
    ev('pointerup', 2, 240, 200);              // second finger lifts
    ev('pointermove', 1, 130, 220);            // remaining finger moves +30,+20
    const b = window.__mcDebug();
    ev('pointerup', 1, 130, 220);
    return {dx: b.x - a.x, dy: b.y - a.y, dk: b.k - a.k};
  });
  assert.ok(Math.abs(cont.dx - 30) < 1 && Math.abs(cont.dy - 20) < 1 && Math.abs(cont.dk) < 1e-9, `continuation ${JSON.stringify(cont)}`);
  results.push('finger lift mid-pinch: remaining finger pans +30,+20 with no zoom jump (synthetic PointerEvents)');
  // Pinch-in clamps at minimum
  await touch('touchStart', [[cx - 150, cy], [cx + 150, cy]]);
  for (let i = 1; i <= 14; i++) await touch('touchMove', [[cx - 150 + i * 10, cy], [cx + 150 - i * 10, cy]]);
  await touch('touchEnd', []);
  assert.ok((await st()).k >= 0.6 - 1e-9, 'zoom clamps at 60%');
  // Tap selects
  const s = await st();
  const target = s.nodes.find(m => m.id !== s.selected && m.sx > 15 && m.sy > 15 && m.sx < box.width - 15 && m.sy < box.height - 15);
  await touch('touchStart', [[target.sx, target.sy]]);
  await touch('touchEnd', []);
  await page.waitForTimeout(120);
  assert.equal((await st()).selected, target.id, 'tap selects');
  results.push(`tap selects ${target.id}; pinch-in clamps at 60%`);
  // Browser page zoom unchanged (canvas consumed the pinch)
  const vv = await page.evaluate(() => window.visualViewport.scale);
  assert.equal(vv, 1, 'browser did not page-zoom');
  results.push('browser page zoom stays 1 (canvas owns the gesture)');
  await ctx.close();
}
await browser.close();
assert.deepEqual(errors, []);
console.log(JSON.stringify({ok: true, results}, null, 1));
