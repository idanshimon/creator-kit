// Real browser proof; run from studio-ui with the generated HTML path.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));
const html=path.resolve(process.argv[2]||path.join(root,'local/verification/gsap/demo/index.html'));
const evidence=path.join(root,'local/verification/gsap');
await mkdir(evidence,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const context=await browser.newContext({viewport:{width:1280,height:800},offline:true});
const page=await context.newPage();
const errors=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
const pose=async t=>{
 await page.evaluate(t=>window.__motion.seek(t),t);
 return page.evaluate(()=>Array.from(document.querySelectorAll('.headline,.subtitle,.underline,.card,.trace,.node,.spark,.progress-fill')).map(e=>{const s=getComputedStyle(e);return {class:e.getAttribute('class'),transform:s.transform,opacity:s.opacity,stroke:s.stroke,dash:s.strokeDashoffset,cx:e.getAttribute('cx')};}));
};
const report={checks:[],screenshots:[],errors,networkRequests:requests};
try{
 await page.goto(pathToFileURL(html).href);
 await page.waitForFunction(()=>window.__ready===true);
 assert.equal(await page.evaluate(()=>gsap.version),'3.15.0');
 assert.equal(await page.evaluate(()=>Object.keys(window.__timelines)[0]),'gsap-motion');
 assert.equal(await page.evaluate(()=>window.__timelines['gsap-motion'].paused()),true);
 assert.equal(await page.evaluate(()=>window.__timelines['gsap-motion'].duration()),8);
 const first=await pose(0),mid=await pose(2.5);
 await pose(8);await pose(1.3);assert.deepEqual(await pose(2.5),mid);
 assert.deepEqual(await pose(0),first);
 report.checks.push('real pinned runtime, paused registry, exact 8s timeline, backward/out-of-order seek');
 await page.getByRole('button',{name:'Play',exact:true}).click();
 await page.waitForFunction(()=>window.__motion.getTime()>.08);
 await page.getByRole('button',{name:'Pause',exact:true}).click();
 const paused=await page.evaluate(()=>window.__motion.getTime());
 await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>window.__motion.getTime()),paused);
 await page.getByRole('button',{name:'Reset',exact:true}).click();assert.equal(await page.evaluate(()=>window.__motion.getTime()),0);
 await page.locator('#seek').focus();await page.keyboard.press('End');assert.equal(await page.evaluate(()=>window.__motion.getTime()),8);
 await page.keyboard.press('Home');assert.equal(await page.evaluate(()=>window.__motion.getTime()),0);
 report.checks.push('actual Play/Pause/Reset clicks and keyboard scrubber');
 await page.evaluate(()=>window.__motion.reset());await page.evaluate(()=>window.__advance(2500));assert.equal(await page.evaluate(()=>window.__motion.getTime()),2.5);
 await page.evaluate(()=>window.__advance(5500));assert.equal(await page.evaluate(()=>window.__done()),true);
 report.checks.push('showcase delta clock and terminal done state');
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 const clipped=await page.locator('.controls button,.controls input,.controls output').evaluateAll(es=>es.filter(e=>{const r=e.getBoundingClientRect();return r.left<0||r.right>innerWidth+1||r.bottom>innerHeight+1;}).length);
 assert.equal(clipped,0);await page.screenshot({path:path.join(evidence,'preview-mobile.png')});
 report.checks.push('390px preview controls fit without horizontal overflow');
 await page.setViewportSize({width:1280,height:720});
 await page.goto(pathToFileURL(html).href+'?render=1');await page.waitForFunction(()=>window.__ready===true);
 assert.equal(await page.locator('.controls').isVisible(),false);
 for(const [label,t] of [['first',0],['middle',2.5],['final',8]]){
  await pose(t);
  const file=path.join(evidence,`gsap-${label}.png`),image=await page.screenshot({path:file});
  report.screenshots.push({label,time:t,file,sha256:createHash('sha256').update(image).digest('hex')});
 }
 assert.equal(new Set(report.screenshots.map(s=>s.sha256)).size,3);
 assert.equal(await page.locator('.card').count(),3);
 const cards=await page.locator('.card').evaluateAll(es=>es.map(e=>({opacity:Number(getComputedStyle(e).opacity),r:e.getBoundingClientRect().toJSON()})));
 assert.ok(cards.every(c=>c.opacity===1&&c.r.left>=0&&c.r.right<=1280&&c.r.bottom<=720));
 if(process.argv[3]){
  await page.goto(pathToFileURL(path.resolve(process.argv[3])).href+'?render=1');await page.waitForFunction(()=>window.__ready===true);await pose(8);
  const geo=await page.evaluate(()=>({textBottom:document.querySelector('.subtitle').getBoundingClientRect().bottom,cardsTop:document.querySelector('.cards').getBoundingClientRect().top,headlineBottom:document.querySelector('.headline').getBoundingClientRect().bottom}));
  assert.ok(geo.textBottom<geo.cardsTop-10,JSON.stringify(geo));
  await page.screenshot({path:path.join(evidence,'long-copy.png')});report.longCopyGeometry=geo;
 }
 assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
 report.checks.push('offline render mode, distinct proof-frame pixels, final cards visible, no browser exceptions');
 console.log(JSON.stringify(report,null,2));
}finally{
 await writeFile(path.join(evidence,'browser-report.json'),JSON.stringify(report,null,2)+'\n');
 await browser.close();
}
