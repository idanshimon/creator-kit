// Browser proof for the generated first-party Archify example; no network required.
import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const root = fileURLToPath(new URL('..', import.meta.url));
const artifact = path.join(root, 'productions/archify-demo/creator-kit.html');
const evidence = path.join(root, 'local/verification/archify');
await mkdir(evidence, {recursive:true});
const browser = await chromium.launch({
  executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless:true,
});
const report = {artifact, checks:[], errors:[]};
try {
  const page = await browser.newPage({viewport:{width:1440,height:900}});
  page.on('pageerror', e => report.errors.push(e.message));
  await page.route(/^https?:/, r => r.abort());
  await page.goto(pathToFileURL(artifact).href);
  // Archify draws each node in two layers; count unique IDs.
  assert.equal(await page.evaluate(() => new Set([...document.querySelectorAll('[data-node-id]')].map(e => e.dataset.nodeId)).size), 4);
  await page.locator('#node-creator').click();
  assert.equal(await page.locator('#node-creator').getAttribute('aria-pressed'), 'true');
  report.checks.push('component selection');
  await page.locator('#btn-reach-downstream').click();
  assert.equal(await page.locator('#btn-reach-downstream').getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator('#focus-reach-downstream-count').textContent(), '2');
  report.checks.push('two downstream nodes from Creator CLI');
  await page.getByRole('button', {name:'Open chapter 2 of 3:', exact:false}).click();
  assert.equal(await page.evaluate(() => location.hash), '#view=validate');
  assert.match(await page.locator('[aria-current="step"]').textContent(), /2\. Validate/);
  report.checks.push('guided chapter selection');
  await page.locator('#guided-view-all').click();
  const before = await page.locator('html').getAttribute('data-theme');
  await page.locator('#btn-theme').click();
  assert.notEqual(await page.locator('html').getAttribute('data-theme'), before);
  report.checks.push('theme toggle');
  await page.screenshot({path:path.join(evidence, 'desktop.png'), fullPage:true});
  await page.setViewportSize({width:390,height:844});
  report.mobile = await page.evaluate(() => ({width:innerWidth,scroll:document.documentElement.scrollWidth}));
  assert.equal(report.mobile.scroll, report.mobile.width);
  await page.screenshot({path:path.join(evidence, 'mobile.png'), fullPage:true});
  report.checks.push('mobile horizontal containment');
  assert.deepEqual(report.errors, []);
  report.ok = true;
} finally {
  await browser.close();
  await writeFile(path.join(evidence, 'report.json'), JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify(report,null,2));
