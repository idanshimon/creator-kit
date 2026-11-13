// Browser quality gate for generated HTML (Hallmark-inspired tiers, our own code).
// Floor  = never ships: text contrast, horizontal overflow, page errors,
//          network requests from an offline artifact, invisible keyboard focus.
// Reflex = AI-look tells; reported, overrulable with a recorded reason.
// Finish = craft details; never blocks.
// Usage: node design-check.mjs <file.html> [shotsDir]  -> JSON on stdout
import {chromium} from 'playwright-core';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const isUrl = /^http:\/\/(127\.0\.0\.1|localhost):\d+\//.test(process.argv[2]);
const file = isUrl ? process.argv[2] : path.resolve(process.argv[2]);
const shots = process.argv[3] ? path.resolve(process.argv[3]) : null;
if (shots) await mkdir(shots, {recursive: true});

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
});

function inPage() {
  const parse = s => {
    let m = s.match(/rgba?\(([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:[ ,/]+([\d.]+%?))?\)/);
    if (m) {
      let a = m[4] === undefined ? 1 : (m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]));
      return [+m[1], +m[2], +m[3], a];
    }
    m = s.match(/color\(srgb ([\d.e-]+) ([\d.e-]+) ([\d.e-]+)(?: \/ ([\d.e-]+))?\)/);
    if (m) return [m[1] * 255, m[2] * 255, m[3] * 255, m[4] === undefined ? 1 : +m[4]];
    return null;
  };
  const over = (top, bot) => {
    const a = top[3] + bot[3] * (1 - top[3]);
    if (a === 0) return [0, 0, 0, 0];
    return [0, 1, 2].map(i => (top[i] * top[3] + bot[i] * bot[3] * (1 - top[3])) / a).concat(a);
  };
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const visible = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    for (let e = el; e; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) < 0.15) return false;
    }
    return true;
  };
  const bgOf = el => {
    const layers = [];
    for (let e = el; e; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.backgroundImage && s.backgroundImage !== 'none') return {unknown: 'background-image'};
      const c = parse(s.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 0.999) break; }
    }
    let acc = [255, 255, 255, 1];
    for (let i = layers.length - 1; i >= 0; i--) acc = over(layers[i], acc);
    return {color: acc};
  };
  const label = el => (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '') || el.tagName.toLowerCase();

  const contrast = [], unknown = [];
  let checked = 0;
  for (const el of document.body.querySelectorAll('*')) {
    if (['SCRIPT', 'STYLE', 'CANVAS', 'SVG', 'svg', 'OPTION'].includes(el.tagName)) continue;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
    if (!own || !visible(el) || el.closest('[disabled],[aria-hidden="true"]')) continue;
    const s = getComputedStyle(el);
    const fg = parse(s.color);
    const bg = bgOf(el);
    if (!fg || bg.unknown) { unknown.push(label(el)); continue; }
    const fgOnBg = over(fg, bg.color);
    const size = parseFloat(s.fontSize), weight = parseInt(s.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const need = large ? 3 : 4.5;
    const r = ratio(fgOnBg, bg.color);
    checked++;
    if (r + 1e-6 < need) contrast.push({el: label(el), text: el.textContent.trim().slice(0, 40), ratio: +r.toFixed(2), need, size});
  }

  const overflowX = document.documentElement.scrollWidth - window.innerWidth;
  const clipped = [];
  for (const el of document.body.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    if ((s.overflowX === 'hidden' || s.overflow === 'hidden') && s.textOverflow !== 'ellipsis' &&
        el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && el.textContent.trim() && !el.querySelector('canvas') && visible(el))
      clipped.push(label(el));
  }
  // Reflex tells
  let tracked = 0, gradientText = 0, emojiIcons = 0, eyebrows = 0;
  for (const el of document.body.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own || !visible(el)) continue;
    const ls = parseFloat(s.letterSpacing) || 0;
    if (s.textTransform === 'uppercase' && ls >= 0.06 * parseFloat(s.fontSize)) tracked++;
    if ((s.webkitBackgroundClip === 'text' || s.backgroundClip === 'text')) gradientText++;
    if (/^(BUTTON|A)$/.test(el.tagName) && /\p{Extended_Pictographic}/u.test(el.textContent)) emojiIcons++;
  }
  for (const h of document.querySelectorAll('h1,h2')) {
    const p = h.previousElementSibling;
    if (p && getComputedStyle(p).textTransform === 'uppercase' && p.textContent.trim().split(/\s+/).length <= 4) eyebrows++;
  }
  return {checked, contrast, unknownBackground: unknown.length, overflowX, clipped: [...new Set(clipped)].slice(0, 12),
          reflex: {trackedUppercaseLabels: tracked, gradientText, emojiIconButtons: emojiIcons, eyebrowAboveHeading: eyebrows}};
}

const viewports = [{name: 'desktop', width: 1440, height: 900}, {name: 'mobile', width: 390, height: 844}];
const runs = [];
const pageErrors = [], requests = [];
let focus = null;
for (const vp of viewports) {
  const ctx = await browser.newContext({viewport: {width: vp.width, height: vp.height}});
  const page = await ctx.newPage();
  page.on('pageerror', e => pageErrors.push(e.message));
  // A served page may call its own origin (e.g. /ask/health); anything else still fails the gate.
  page.on('request', r => { const u = r.url(); if (/^https?:/.test(u) && !(isUrl && new URL(u).origin === new URL(file).origin)) requests.push(u); });
  await page.goto(isUrl ? file : pathToFileURL(file).href, {waitUntil: 'load'});
  await page.waitForTimeout(700);
  const themes = await page.evaluate(() => document.documentElement.hasAttribute('data-theme')
    ? [document.documentElement.getAttribute('data-theme'), document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark']
    : [null]);
  for (const th of themes) {
    if (th) {
      await page.evaluate(t => {
        // Prefer the page's own toggle so canvas palettes repaint; fall back to the attribute.
        const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim().toLowerCase().replace(/[^a-z]/g, '') === t);
        if (btn) btn.click(); else document.documentElement.setAttribute('data-theme', t);
      }, th);
      await page.waitForTimeout(400);
    }
    const actual = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    const res = await page.evaluate(inPage);
    res.themeApplied = actual;
    if (shots) {
      const p = path.join(shots, `${vp.name}-${th || 'default'}.png`);
      await page.screenshot({path: p});
      res.screenshot = p;
    }
    runs.push({viewport: vp.name, theme: th, ...res});
  }
  if (vp.name === 'desktop') {
    focus = {tested: 0, invisible: []};
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press('Tab');
      const f = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const s = getComputedStyle(el);
        const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none');
        return {el: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''), ring};
      });
      if (!f) continue;
      focus.tested++;
      if (!f.ring) focus.invisible.push(f.el);
    }
  }
  await ctx.close();
}
await browser.close();

const floor = [];
for (const r of runs) {
  if (r.contrast.length) floor.push(`${r.viewport}/${r.theme}: ${r.contrast.length} text elements below WCAG contrast`);
  if (r.overflowX > 1) floor.push(`${r.viewport}/${r.theme}: page scrolls sideways by ${r.overflowX}px`);
}
if (pageErrors.length) floor.push(`${pageErrors.length} page errors`);
if (requests.length) floor.push(`${requests.length} network requests from an offline artifact`);
if (focus && focus.invisible.length) floor.push(`keyboard focus not visible on: ${[...new Set(focus.invisible)].join(', ')}`);
const reflex = [];
const rf = runs[0].reflex;
if (rf.trackedUppercaseLabels > 8) reflex.push(`${rf.trackedUppercaseLabels} tracked-uppercase labels (AI-look tell; keep for real section labels only)`);
if (rf.gradientText) reflex.push(`${rf.gradientText} gradient-text elements`);
if (rf.emojiIconButtons) reflex.push(`${rf.emojiIconButtons} buttons using emoji as icons`);
if (rf.eyebrowAboveHeading) reflex.push(`${rf.eyebrowAboveHeading} eyebrow labels above headings`);
const finish = [];
for (const r of runs) if (r.clipped.length) finish.push(`${r.viewport}/${r.theme}: clipped text in ${r.clipped.join(', ')}`);
console.log(JSON.stringify({ok: floor.length === 0, input: file, floor, reflex, finish,
  pageErrors, networkRequests: requests, focus, runs}, null, 1));
