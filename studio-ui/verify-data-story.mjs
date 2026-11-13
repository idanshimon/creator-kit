// Local-only browser proof. Uses installed playwright-core and local Chrome, no server or downloads.
import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.resolve(process.argv[2] || path.join(root, 'local/verification/data-story', new Date().toISOString().replaceAll(':', '-')));
await mkdir(path.dirname(out), { recursive: true });
await mkdir(out, { recursive: false });
const python = process.env.PYTHON || 'python3';
const chrome = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const source = path.join(root, 'examples/data-story/synthetic-workshop.json');
const html = path.join(out, 'synthetic-workshop.html');
function cli(...args) {
  return JSON.parse(execFileSync(python, [path.join(root, 'creator.py'), 'data-story', ...args], { cwd: root, encoding: 'utf8' }));
}
const report = cli('render', '--input', source, '--output', html);
const browser = await chromium.launch({ executablePath: chrome, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, offline: true, reducedMotion: 'reduce' });
const errors = [], requests = [], screenshots = [];
context.on('page', page => {
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('request', request => { if (/^https?:/i.test(request.url())) requests.push(request.url()); });
});
async function shot(page, name) {
  const target = path.join(out, name + '.png');
  await page.screenshot({ path: target, fullPage: true });
  screenshots.push({ path: target, sha256: createHash('sha256').update(await readFile(target)).digest('hex') });
}
async function noOverflow(page) {
  const size = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
  assert.ok(size.scroll <= size.width, JSON.stringify(size));
  const labelHeights = await page.locator('svg text').evaluateAll(elements => elements.map(element => element.getBoundingClientRect().height));
  assert.ok(labelHeights.every(height => height >= 10), 'Chart labels must remain at least 10 CSS pixels high: ' + JSON.stringify(labelHeights));
}
try {
  const page = await context.newPage();
  await page.goto(pathToFileURL(html).href);
  assert.equal(await page.locator('h1').textContent(), 'SYNTHETIC: a workshop\'s changing rhythm');
  assert.equal(await page.locator('svg[role="img"]').count(), 3);
  assert.equal(await page.locator('details[open]').count(), 0);
  assert.ok((await page.locator('h1').boundingBox()).y < 300);
  await shot(page, 'desktop-light');
  for (const [index, fact] of report.figures.entries()) {
    const section = page.locator('section').nth(index);
    assert.equal(await section.locator('.metric strong').first().textContent(), `${fact.latest} ${index === 1 ? 'observed / predicted' : index === 0 ? 'items' : 'items waiting'}`);
    await section.locator('summary').click();
    assert.equal(await section.locator('details').getAttribute('open'), '');
    const text = await section.locator('.evidence').innerText();
    for (const expected of [fact.digest, 'Not verified', 'SYNTHETIC-workshop-v1', '2026-10-01T12:00:00Z', 'Calculation inputs', 'Local-file extract']) assert.ok(text.includes(expected), expected);
    assert.equal(await section.locator('.point').count(), fact.values.length);
  }
  await page.locator('nav a').nth(1).click();
  await page.waitForFunction(() => location.hash === '#story-pooled-load');
  assert.equal(await page.locator('nav a').nth(1).getAttribute('aria-current'), 'true');
  const bounds = await page.locator('#story-pooled-load').boundingBox();
  assert.ok(bounds.y >= 0 && bounds.y < 100, JSON.stringify(bounds));
  await page.locator('#theme').click();
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  assert.equal(await page.locator('#theme').getAttribute('aria-pressed'), 'true');
  await shot(page, 'desktop-dark-explain');
  await page.locator('#theme').focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
  const firstSummary = page.locator('summary').first();
  await firstSummary.focus(); await page.keyboard.press('Enter');
  assert.equal(await page.locator('details').first().getAttribute('open'), null);
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('details').first().getAttribute('open'), '');
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await noOverflow(page);
    for (const evidence of await page.locator('.evidence').all()) assert.ok(await evidence.isVisible());
    await page.evaluate(() => scrollTo(0, 0));
    assert.ok((await page.locator('h1').boundingBox()).y >= 0);
    await shot(page, `mobile-${width}-explain`);
  }
  // Exercise an adversarial author payload and a source-supplied verification declaration.
  const fixture = JSON.parse(await readFile(source, 'utf8'));
  const hostile = '</script><script>window.PWNED=1</script>\" & <img src=x onerror=alert(1)>';
  fixture.title = hostile;
  fixture.figures[0].interpretation = hostile;
  fixture.figures[0].source.url += '/' + 'long-source-path-'.repeat(30);
  fixture.figures[0].extract.mode = 'query';
  fixture.figures[0].extract.query = 'SYNTHETIC SECURITY FIXTURE: ' + hostile + 'x'.repeat(500);
  const fixturePath = path.join(out, 'synthetic-security-fixture.json');
  await writeFile(fixturePath, JSON.stringify(fixture), { flag: 'wx' });
  const digest = cli('validate', '--input', fixturePath).figures[0].digest;
  fixture.figures[0].verification = { digest, status: 'passed', expected_latest: 18 };
  await writeFile(fixturePath, JSON.stringify(fixture));
  const safeHtml = path.join(out, 'synthetic-security-fixture.html');
  cli('render', '--input', fixturePath, '--output', safeHtml);
  await page.goto(pathToFileURL(safeHtml).href);
  assert.equal(await page.locator('h1').textContent(), hostile);
  assert.equal(await page.evaluate(() => window.PWNED), undefined);
  assert.equal(await page.locator('script').count(), 1);
  assert.equal(await page.locator('img').count(), 0);
  await page.locator('summary').first().click();
  assert.ok((await page.locator('.evidence').first().innerText()).includes('Supplied checks passed'));
  assert.ok((await page.locator('pre').first().innerText()).includes(hostile));
  await noOverflow(page);
  await shot(page, 'mobile-security-explain');
  assert.deepEqual(errors, []);
  assert.deepEqual(requests, []);
  const evidence = { passed: true, html, offline: true, browser: await browser.version(), viewports: [1440, 390, 320],
    checks: ['native Explain open/close via pointer and keyboard', 'navigation hash, active state and actual scroll', 'light/dark toggle via pointer and keyboard', 'all figures expose periods, inputs, identity, digest and unverified state', 'latest values match CLI facts', 'mobile overflow with all explanations open', 'hostile text inert including closing scripts, long query and URL', 'supplied verification label'],
    errors, networkRequests: requests, screenshots };
  await writeFile(path.join(out, 'browser-evidence.json'), JSON.stringify(evidence, null, 2), { flag: 'wx' });
  console.log(JSON.stringify(evidence, null, 2));
} finally { await browser.close(); }
