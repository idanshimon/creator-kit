import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';

const browser = await chromium.launch({executablePath: process.env.CHROME_PATH || (process.platform === 'darwin' ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : '/usr/bin/chromium')});
const demo = new URL('../templates/overlays/sdlc-loop/demo.html', import.meta.url).href;
const labels = ['Issue','Triage','Plan','Implement','Checks','Review','Merge','Resolved'];
try {
 for (const mobile of [false, true]) {
  const context = await browser.newContext({offline:true, isMobile:mobile, hasTouch:mobile, viewport:mobile ? {width:360,height:740} : {width:1280,height:800}, colorScheme:mobile?'dark':'light', reducedMotion:mobile?'reduce':'no-preference'});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', req => errors.push(req.url()));
  page.on('request', req => { if (!req.url().startsWith('file:')) errors.push(req.url()); });
  await page.goto(demo);
  const loop = page.locator('sdlc-loop');
  assert.deepEqual(await loop.evaluate(el => el.stages?.map(s=>s.label)), labels);
  const current = loop.locator('.dial [aria-current="step"]');
  assert.equal(await current.count(), 0);
  const next = page.getByRole('button',{name:'Next',exact:true});
  await next.click(); await next.focus(); await page.keyboard.press('Enter');
  assert.equal(await current.getAttribute('aria-label'),'3. Plan');
  const last = loop.getByRole('button',{name:'8. Resolved',exact:true});
  if (mobile) await last.tap(); else await last.click();
  assert.match(await loop.locator('.inspection').innerText(),/Inspecting: Resolved/);
  assert.equal(await current.getAttribute('aria-label'),'3. Plan');
  const picker = loop.getByRole('combobox');
  await picker.focus(); await page.keyboard.press('Home');
  assert.match(await loop.locator('.inspection').innerText(),/Inspecting: Issue/);
  assert.equal(await current.getAttribute('aria-label'),'3. Plan');
  assert.equal(await picker.locator('option').count(),8);
  await page.keyboard.press('Escape');
  assert.equal(await picker.isVisible(),false);
  await next.click(); assert.equal(await current.getAttribute('aria-label'),'6. Review');
  await page.getByRole('button',{name:'Previous'}).click();
  assert.equal(await current.getAttribute('aria-label'),'3. Plan');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),true);
  const box = await loop.boundingBox(); assert.ok(box.width < 220 && box.x >= 0 && box.x + box.width <= page.viewportSize().width);
  const palette = () => loop.locator('.panel').evaluate(el=>getComputedStyle(el).backgroundColor);
  const before = await palette(); await loop.evaluate((el,m)=>el.setAttribute('theme',m?'light':'dark'),mobile); assert.notEqual(await palette(),before);
  if(mobile) assert.equal(await last.evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
  await loop.evaluate(el => {el.setStage(null);}); assert.equal(await current.count(),0);
  await loop.evaluate(el => {el.stages = [{id:'draft',label:'Draft',detail:'Example only.'}]; el.setStage('draft');});
  assert.equal(await current.getAttribute('aria-label'),'1. Draft');
  await assert.rejects(loop.evaluate(el=>el.setStage('absent')), /Unknown stage/);
  await assert.rejects(loop.evaluate(el=>el.stages=[...el.stages,...el.stages]), /unique/);
  assert.equal(await current.getAttribute('aria-label'),'1. Draft');
  assert.deepEqual(errors,[]);
  console.log(`PASS offline ${mobile?'mobile 360x740 touch/dark/reduced motion':'desktop 1280x800 light'}: chapters, inspection, keyboard, layout, theme and API`);
  await context.close();
 }
} finally { await browser.close(); }
