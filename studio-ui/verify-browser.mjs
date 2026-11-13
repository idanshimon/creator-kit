import {chromium} from 'playwright-core';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const root=new URL('../local/ui-verification/',import.meta.url).pathname;
await mkdir(root,{recursive:true});
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
page.on('dialog',async d=>{await d.accept(d.type()==='prompt'?(d.message().includes('Revision')?'Browser verification':'Creator verification edit'):undefined);});
try {
 await page.goto('http://127.0.0.1:4318/');
 await page.getByTitle('New project',{exact:true}).click();
 await page.getByLabel('Project name').waitFor();
 await page.locator('input[type=file]').setInputFiles(new URL('../local/verification/source-a.mp4',import.meta.url).pathname);
 await page.getByText('source-a.mp4',{exact:true}).waitFor();
 console.log('Imported source through browser');
 console.log(await page.locator('button').evaluateAll(es=>es.map(e=>({title:e.title,text:e.innerText}))));
 await page.screenshot({path:root+'initial-desktop.png',fullPage:true});
 await writeFile(root+'browser-state.txt',await page.locator('body').innerText());
 assert.deepEqual(errors,[]);
} finally {await browser.close();}
