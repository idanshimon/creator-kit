import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {buildSync} from 'esbuild';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const wirePath = new URL('../src/lib/wire.ts', import.meta.url);
test('canonical renderer plans round-trip without leaking UI-only fields', async () => {
  assert.ok(existsSync(wirePath),'Renderer/UI adapter missing');
  buildSync({entryPoints:[wirePath.pathname],bundle:true,platform:'node',format:'esm',outfile:'.test-build/wire.mjs'});
  const {fromWirePlan,toWirePlan}=await import('../.test-build/wire.mjs');
  const assets=[{id:'asset1',path:'/studio/media/source.mp4'}];
  const raw={version:1,width:720,height:1280,fit:'contain',volume:0.8,mute:false,fade_in:0.2,fade_out:0.3,clips:[{path:assets[0].path,start:1,end:3,speed:2,volume:0.5,mute:true}]};
  const ui=fromWirePlan(raw,assets);
  assert.equal(ui.clips[0].asset_id,'asset1');assert.equal(ui.clips[0].in,1);
  assert.equal(ui.preset,'portrait');
  assert.deepEqual(toWirePlan(ui,assets),raw);
  assert.throws(()=>toWirePlan({...ui,clips:[{...ui.clips[0],asset_id:'missing'}]},assets));
});

test('completed job reveals a playable render and download, not a loader', async()=>{
  buildSync({entryPoints:['src/components/ExportPanel.tsx'],bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',outfile:'.test-build/ExportPanel.mjs'});
  const {ExportPanel}=await import('../.test-build/ExportPanel.mjs');
  const p={id:'p',revision:3,plan:{clips:[{id:'c'}]}};
  const job={id:'j',project_id:'p',revision:2,kind:'draft',status:'succeeded',result_url:'/media/result',created_at:'2026-01-01',error:null};
  const html=renderToStaticMarkup(React.createElement(ExportPanel,{project:p,jobs:[job],dirty:false,busy:false,onRender:()=>{}}));
  assert.match(html,/<video/);assert.match(html,/Download/);assert.match(html,/project is now/);
});
