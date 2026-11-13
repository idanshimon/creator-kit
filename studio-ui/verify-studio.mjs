// Real, isolated browser smoke test. Never uses the user's existing workspace.
import {chromium} from 'playwright-core';
import {spawn,execFileSync} from 'node:child_process';
import {mkdtemp,mkdir,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('..',import.meta.url));
const scratch=await mkdtemp(path.join(tmpdir(),'creator-e2e-'));
const evidence=path.join(scratch,'evidence');await mkdir(evidence);
const source=path.join(scratch,'test-pattern.mp4');
execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',source]);
const python=process.env.CREATOR_PYTHON||'python3.13';
let server;
async function start(){
 server=spawn(python,[path.join(root,'creator.py'),'studio','--port','0','--workspace',path.join(scratch,'workspace')],{cwd:root});
 return await new Promise((resolve,reject)=>{
  let out='',err='';const timer=setTimeout(()=>reject(new Error('Server startup timed out: '+err)),15000);
  server.stderr.on('data',d=>{err+=d});server.stdout.on('data',d=>{out+=d;const m=out.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0]);}});
  server.on('error',e=>{clearTimeout(timer);reject(e)});server.on('exit',code=>{clearTimeout(timer);reject(new Error('Server exited '+code+': '+err))});
 });
}
async function stop(){if(server&&server.exitCode===null){const done=new Promise(r=>server.once('exit',r));server.kill('SIGTERM');await done;}}
let browser;
const report={scope:'isolated synthetic fixture, no cloud calls',scratch};
try{
 let url=await start();
 const chrome=process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
 browser=await chromium.launch({executablePath:chrome,headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('dialog',async d=>{await d.accept(d.type()==='prompt'?(d.message().includes('Revision')?'Smoke revision':'Smoke project'):undefined)});
 await page.goto(url);
 await page.getByTitle('New project',{exact:true}).click();
 await page.getByLabel('Project name').waitFor();
 await page.locator('input[type=file]').setInputFiles(source);
 await page.getByTitle('Add to timeline',{exact:true}).click();
 await page.locator('.timeline .clip').waitFor();
 await page.getByTitle('Split at source midpoint',{exact:true}).click();
 assert.equal(await page.locator('.timeline .clip').count(),2);
 await page.getByTitle('Save revision (Ctrl+S)',{exact:true}).click();
 await page.getByText('r2 saved',{exact:true}).waitFor();
 await page.getByTitle('Undo (Ctrl+Z)',{exact:true}).click();
 await page.getByText('r3 saved',{exact:true}).waitFor();
 assert.equal(await page.locator('.timeline .clip').count(),0);
 await page.getByTitle('Redo (Ctrl+Shift+Z)',{exact:true}).click();
 await page.getByText('r4 saved',{exact:true}).waitFor();
 assert.equal(await page.locator('.timeline .clip').count(),2);
 await page.getByTitle('Fast draft render',{exact:true}).click();
 await page.getByTitle('Download rendered video',{exact:true}).waitFor({timeout:60000});
 const state=await (await fetch(url+'/api/state')).json();
 const job=state.jobs.find(j=>j.status==='succeeded');assert.ok(job);assert.equal(job.revision,4);
 const ranged=await fetch(url+job.result_url,{headers:{Range:'bytes=0-31'}});
 assert.equal(ranged.status,206);assert.equal((await ranged.arrayBuffer()).byteLength,32);
 const downloadPromise=page.waitForEvent('download');
 await page.getByTitle('Download rendered video',{exact:true}).click();
 const download=await downloadPromise;const output=path.join(evidence,'draft.mp4');await download.saveAs(output);
 const meta=JSON.parse(execFileSync('ffprobe',['-v','error','-show_streams','-show_format','-of','json',output],{encoding:'utf8'}));
 const video=meta.streams.find(s=>s.codec_type==='video');assert.ok(video);assert.equal(video.width,640);assert.equal(video.height,360);assert.ok(Math.abs(Number(meta.format.duration)-2)<.15);
 await page.screenshot({path:path.join(evidence,'desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:path.join(evidence,'mobile.png'),fullPage:true});
 const geometry=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right})).slice(0,12)}));
 console.log('MOBILE',JSON.stringify(geometry),'EVIDENCE',evidence);
 assert.equal(geometry.scroll<=geometry.width,true);
 await page.getByTitle('Download rendered video',{exact:true}).scrollIntoViewIfNeeded();
 assert.equal(await page.getByTitle('Download rendered video',{exact:true}).isVisible(),true);
 await page.screenshot({path:path.join(evidence,'mobile-export.png')});
 const projectId=state.projects[0].id;await stop();url=await start();
 await page.goto(url);await page.getByLabel('Select project').selectOption(projectId);
 await page.getByText('r4 saved',{exact:true}).waitFor();
 assert.equal(await page.locator('.timeline .clip').count(),2);
 assert.deepEqual(errors,[]);
 Object.assign(report,{passed:true,actions:['create','upload','add','split','save','undo','redo','draft render','range stream','download','restart/reopen'],revision:4,output:{width:video.width,height:video.height,duration:Number(meta.format.duration)},mobileOverflow:false,pageErrors:errors});
 await writeFile(path.join(evidence,'report.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report,null,2));
}finally{if(browser)await browser.close();await stop();}
