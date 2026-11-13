import type {Plan, PresetName} from './timeline';
import {PRESETS} from './timeline';
type AssetRef = {id: string; path: string};
export interface WirePlan {
  version: number; width: number; height: number; fit?: 'contain'|'cover';
  mute?: boolean; volume?: number; fade_in?: number; fade_out?: number;
  clips: Array<{path: string; start: number; end: number; speed?: number; volume?: number; mute?: boolean}>;
}
export function fromWirePlan(raw: WirePlan, assets: AssetRef[]): Plan {
  const preset = (Object.keys(PRESETS) as PresetName[]).find(k=>PRESETS[k].width===raw.width && PRESETS[k].height===raw.height);
  return {preset, width:raw.width, height:raw.height, fit:raw.fit??'contain', mute:raw.mute??false,
    volume:raw.volume??1, fade_in:raw.fade_in??0, fade_out:raw.fade_out??0,
    clips:raw.clips.map((c,i)=>{
      const asset=assets.find(a=>a.path===c.path);
      if(!asset) throw new Error('Project source is missing from the media library. Import or restore it first.');
      return {id:`${asset.id}-${i}`,asset_id:asset.id,in:c.start,out:c.end,speed:c.speed??1,volume:c.volume??1,mute:c.mute??false};
    })};
}
export function toWirePlan(plan: Plan, assets: AssetRef[]): WirePlan {
  const dims=plan.preset ? PRESETS[plan.preset] : {width:plan.width??1280,height:plan.height??720};
  return {version:1,...dims,fit:plan.fit??'contain',mute:plan.mute??false,volume:plan.volume??1,
    fade_in:plan.fade_in??0,fade_out:plan.fade_out??0,clips:plan.clips.map(c=>{
      const asset=assets.find(a=>a.id===c.asset_id);
      if(!asset)throw new Error('Unknown media asset; import the source before saving.');
      return {path:asset.path,start:c.in,end:c.out,speed:c.speed,volume:c.volume,mute:c.mute};
    })};
}
