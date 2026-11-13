// Real-Chrome proof for the Mission Control Ask pane + themed scrollbars.
// usage: node verify-mission-ask.mjs <served-url> <outdir> [--file page.html] [--q "question"]... [--selected ENTITY_ID]
// Asks each question through the page's own form (real POST /ask), records answers to <outdir>/ask-results.json,
// screenshots the pane in dark, light and phone width, the scrolled worklist in both themes, and (with --file)
// the static file's disabled pane.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
const argv = process.argv.slice(2);
const url = argv[0], out = argv[1];
const qs = [], opt = {};
for (let i = 2; i < argv.length; i++) { if (argv[i] === '--q') qs.push(argv[++i]); else opt[argv[i].slice(2)] = argv[++i]; }
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, ignoreDefaultArgs: ['--hide-scrollbars'] });
const results = { url, answers: [], errors: [] };
const lastMsg = (p) => p.evaluate(() => { const l = [...document.querySelectorAll('#mc-ask-log .mc-msg')]; const m = l[l.length - 1]; return { text: m.innerText, links: [...m.querySelectorAll('a')].map(a => a.getAttribute('href')) }; });
async function waitAnswer(p, n0) {
  await p.waitForFunction((n) => document.querySelectorAll('#mc-ask-log .mc-msg.a:not(.mc-thinking), #mc-ask-log .mc-msg.err').length > n, n0, { timeout: 330000, polling: 1000 });
  return lastMsg(p);
}
const count = (p) => p.evaluate(() => document.querySelectorAll('#mc-ask-log .mc-msg.a:not(.mc-thinking), #mc-ask-log .mc-msg.err').length);
async function theme(p, want) {
  const cur = await p.evaluate(() => document.documentElement.dataset.theme);
  if (cur !== want) await p.click('#btn-theme');
  await p.waitForTimeout(300);
}

const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on('pageerror', e => results.errors.push(e.message));
await page.goto(url); await page.waitForTimeout(1500);
results.pane_open_on_load = await page.evaluate(() => document.getElementById('mc-ask').classList.contains('open'));
results.state = await page.textContent('#mc-ask-state');
if (!results.pane_open_on_load) await page.click('#btn-ask');
for (const q of qs) {
  const n0 = await count(page); const t0 = Date.now();
  await page.fill('#mc-ask-q', q); await page.click('#mc-ask-send');
  await page.waitForSelector('.mc-thinking', { timeout: 5000 }).then(() => results.thinking_seen = true).catch(() => {});
  const a = await waitAnswer(page, n0);
  results.answers.push({ q, seconds: Math.round((Date.now() - t0) / 1000), ...a });
  console.log('Q:', q, '\nA:', a.text, '\n');
}
if (opt.selected) {
  await page.evaluate((id) => { /* select through the page's own list row */ const r = [...document.querySelectorAll('.entity-item')].find(x => x.textContent.includes(id)); if (r) r.click(); }, opt.selected);
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  const n0 = await count(page);
  await page.click('#mc-ask-sel');
  const a = await waitAnswer(page, n0);
  results.answers.push({ q: '[Ask about selected item] ' + (await page.evaluate(() => JSON.stringify(window.__mcSelected()))), ...a });
  console.log('SELECTED:', a.text);
}
for (const t of ['dark', 'light']) {
  await theme(page, t);
  await page.screenshot({ path: `${out}/ask-desktop-${t}.png` });
  // Scrolled worklist + left rail to show the themed scrollbars.
  await page.evaluate(() => { const l = document.querySelector('.entity-list'); l.scrollTop = 120; const r = document.querySelector('.rail'); r.scrollTop = 60; document.getElementById('mc-ask-log').scrollTop = 80; });
  const box = await page.locator('.entity-list').boundingBox();
  await page.screenshot({ path: `${out}/scrollbar-list-${t}.png`, clip: { x: Math.max(0, box.x - 10), y: Math.max(0, box.y - 10), width: box.width + 20, height: Math.min(260, box.height + 20) } });
  results['scrollbar_' + t] = await page.evaluate(() => { const cs = getComputedStyle(document.querySelector('.entity-list')); return { colorScheme: getComputedStyle(document.documentElement).colorScheme, scrollbarColor: cs.scrollbarColor, scrollbarWidth: cs.scrollbarWidth, scrollable: document.querySelector('.entity-list').scrollHeight > document.querySelector('.entity-list').clientHeight }; });
}
const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
phone.on('pageerror', e => results.errors.push('phone: ' + e.message));
await phone.goto(url); await phone.waitForTimeout(1200);
await phone.click('#btn-ask'); await phone.waitForTimeout(400);
for (const t of ['dark', 'light']) { await theme(phone, t); await phone.screenshot({ path: `${out}/ask-phone-${t}.png` }); }
results.phone_pane = await phone.evaluate(() => { const r = document.getElementById('mc-ask').getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, sw: document.documentElement.scrollWidth }; });
if (opt.file) {
  const f = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  f.on('pageerror', e => results.errors.push('file: ' + e.message));
  await f.goto('file://' + opt.file); await f.waitForTimeout(800);
  await f.click('#btn-ask'); await f.waitForTimeout(300);
  results.static = await f.evaluate(() => ({ disabled: document.getElementById('mc-ask-q').disabled, note: document.querySelector('.mc-ask-off')?.innerText }));
  await f.screenshot({ path: `${out}/ask-static-file.png` });
}
fs.writeFileSync(`${out}/ask-results.json`, JSON.stringify(results, null, 2));
console.log(JSON.stringify({ ...results, answers: results.answers.length }, null, 2));
await browser.close();
