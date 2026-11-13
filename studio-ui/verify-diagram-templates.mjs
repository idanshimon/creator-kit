// Browser proof for Archify presentation templates (full / presenter / embed / minimal).
// Usage: node verify-diagram-templates.mjs <dir with morrow-<template>.html> <details.json>
import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const dir = path.resolve(process.argv[2] || path.join(root, 'productions/morrow-beginner/templates'));
const details = JSON.parse(await readFile(process.argv[3] || path.join(root, 'productions/morrow-beginner/morrow-beginner.details.json'), 'utf8'));
const evidence = path.join(root, 'local/verification/archify-templates');
await mkdir(evidence, {recursive: true});
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
});
const report = {dir, templates: {}, errors: []};
const visible = (page, sel) => page.evaluate(s => {
  const el = document.querySelector(s);
  if (!el) return false;
  const st = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return st.display !== 'none' && st.visibility !== 'hidden' && !el.hidden && r.width > 0 && r.height > 0;
}, sel);
const camera = page => page.evaluate(() => document.querySelector('.diagram-container svg')?.style.transform
  || document.querySelector('.diagram-container svg g')?.getAttribute('transform') || '');

async function open(name, viewport) {
  const page = await browser.newPage({viewport});
  page.on('pageerror', e => report.errors.push(`${name}: ${e.message}`));
  await page.route(/^https?:/, r => r.abort());
  await page.goto(pathToFileURL(path.join(dir, `morrow-${name}.html`)).href);
  await page.waitForTimeout(600);
  return page;
}

try {
  // full: untouched original — passport opens, no wrapper.
  {
    const page = await open('full', {width: 1440, height: 900});
    const c = [];
    assert.equal(await page.locator('#cc-template').count(), 0); c.push('no wrapper injected');
    for (const s of ['.toolbar', '#guided-views', '.cards', '.diagram-nav']) assert.ok(await visible(page, s), s);
    c.push('toolbar, chapters, cards, nav visible');
    await page.locator('g[data-node-id="bouncer"]').first().click();
    assert.ok(await visible(page, '#focus-chip')); c.push('semantic passport opens on click');
    await page.screenshot({path: path.join(evidence, 'full.png')});
    report.templates.full = c; await page.close();
  }
  // presenter: chapters kept; tooling hidden; detail panel replaces passport; camera still.
  {
    const page = await open('presenter', {width: 1440, height: 900});
    const c = [];
    assert.equal(await page.getAttribute('html', 'data-cc-ready'), 'true');
    for (const s of ['.toolbar', '#btn-route-probe', '#btn-overview-map', '#btn-semantic-lens']) assert.ok(!(await visible(page, s)), `hidden ${s}`);
    for (const s of ['#guided-views', '.cards', '.header']) assert.ok(await visible(page, s), `visible ${s}`);
    c.push('toolbar + PATH/MAP/LENS hidden; header, chapters, cards visible');
    const ids = await page.evaluate(() => [...new Set([...document.querySelectorAll('svg g[data-node-id]')].map(g => g.dataset.nodeId))]);
    assert.equal(ids.length, Object.keys(details).length);
    const before = await camera(page);
    for (const id of ids) {
      await page.locator(`g[data-node-id="${id}"]`).first().click();
      assert.ok(await visible(page, '#cc-detail'), `panel for ${id}`);
      assert.ok(!(await visible(page, '#focus-chip')), `passport hidden for ${id}`);
      const text = await page.locator('#cc-detail').innerText();
      for (const f of ['what', 'why', 'example']) assert.ok(text.includes(details[id][f]), `${id}.${f}`);
      assert.equal(await page.locator('#cc-detail details').getAttribute('open'), null);
    }
    assert.equal(await camera(page), before);
    c.push(`all ${ids.length} components open the detail panel with authored text; camera unchanged; tech details closed`);
    await page.locator('#cc-detail [data-cc-node]').first().click();
    assert.ok(await visible(page, '#cc-detail')); c.push('related-component link navigates panel');
    await page.screenshot({path: path.join(evidence, 'presenter.png')});
    await page.keyboard.press('Escape');
    assert.equal(await page.getAttribute('#cc-detail', 'data-open'), 'false'); c.push('Escape closes panel');
    report.templates.presenter = c; await page.close();
  }
  // embed: graph only inside an iframe-sized viewport; detail sheet still works; no overflow.
  for (const vp of [{width: 900, height: 520}, {width: 390, height: 600}]) {
    const page = await open('embed', vp);
    const c = [];
    for (const s of ['.toolbar', '.header', '#guided-views', '.cards', '#btn-route-probe']) assert.ok(!(await visible(page, s)), `hidden ${s}`);
    const over = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1 || document.documentElement.scrollHeight > innerHeight + 1);
    assert.equal(over, false, 'no page scroll');
    const boxes = await page.evaluate(() => [...document.querySelectorAll('svg g[data-node-id] rect')].map(r => r.getBoundingClientRect()).filter(b => b.width)
      .every(b => b.left >= -1 && b.right <= innerWidth + 1));
    assert.ok(boxes, 'every node inside the frame');
    await page.locator('g[data-node-id="spotlight"]').first().click();
    assert.ok(await visible(page, '#cc-detail'));
    assert.ok((await page.locator('#cc-detail').innerText()).includes(details.spotlight.what));
    c.push('graph only, fits frame, no scroll, all nodes in frame, detail sheet opens');
    await page.screenshot({path: path.join(evidence, `embed-${vp.width}.png`)});
    report.templates[`embed-${vp.width}`] = c; await page.close();
  }
  // minimal: static, nothing opens.
  {
    const page = await open('minimal', {width: 1200, height: 640});
    for (const s of ['.toolbar', '.header', '#guided-views', '.cards', '.diagram-nav']) assert.ok(!(await visible(page, s)), `hidden ${s}`);
    await page.locator('g[data-node-id="bouncer"]').first().click();
    assert.equal(await page.locator('#cc-detail').count(), 0);
    assert.ok(!(await visible(page, '#focus-chip')));
    await page.screenshot({path: path.join(evidence, 'minimal.png')});
    report.templates.minimal = ['graph only, no controls, click opens nothing'];
    await page.close();
  }
  // iframe embedding inside a host page.
  {
    const page = await browser.newPage({viewport: {width: 1100, height: 800}});
    await page.route(/^https?:/, r => r.abort());
    const host = path.join(dir, '_embed-host.html');
    await writeFile(host, `<!doctype html><body style="margin:40px;font-family:sans-serif"><h1>Host article</h1>
<iframe src="morrow-embed.html" title="Morrow diagram" style="width:100%;height:480px;border:0;border-radius:16px"></iframe><p>After</p></body>`);
    await page.goto(pathToFileURL(host).href);
    const f = page.frameLocator('iframe');
    await f.locator('g[data-node-id="examples"]').first().click();
    assert.ok((await f.locator('#cc-detail').innerText()).includes(details.examples.what));
    await page.screenshot({path: path.join(evidence, 'embed-in-host.png')});
    report.templates.iframe = ['embedded in host page; click opens detail inside frame'];
    await page.close();
  }
  assert.deepEqual(report.errors, []);
  report.ok = true;
} catch (e) {
  report.ok = false; report.failure = String(e.stack || e);
} finally {
  await browser.close();
  await writeFile(path.join(evidence, 'report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  process.exit(report.ok ? 0 : 1);
}
