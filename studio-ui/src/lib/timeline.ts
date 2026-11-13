// Pure, framework-free timeline helpers + domain types.
// These are the ONLY editing computations covered by Node tests (test/timeline.test.mjs).
// Keep this file free of React/DOM imports so it compiles for both the browser bundle
// and the node test build.

export interface Clip {
  id: string;
  asset_id: string;
  in: number; // source in-point, seconds
  out: number; // source out-point, seconds
  speed: number; // 0.25..4
  volume: number; // 0..2
  mute: boolean;
}

export interface Plan {
  width?: number;
  height?: number;
  mute?: boolean;
  clips: Clip[];
  // Output/composition settings (parent renderer consumes these):
  preset?: PresetName;
  fit?: 'contain' | 'cover';
  volume?: number; // global 0..2
  fade_in?: number; // seconds
  fade_out?: number; // seconds
}

export type PresetName = 'landscape' | 'portrait' | 'square';

export interface Dimensions {
  width: number;
  height: number;
}

export const PRESETS: Record<PresetName, Dimensions> = {
  landscape: { width: 1280, height: 720 },
  portrait: { width: 720, height: 1280 },
  square: { width: 1080, height: 1080 },
};

export const SPEED_MIN = 0.25;
export const SPEED_MAX = 4;
export const VOLUME_MIN = 0;
export const VOLUME_MAX = 2;
export const MAX_UPLOAD_BYTES = 256 * 1024 * 1024; // 256 MiB

export function clampSpeed(speed: number): number {
  if (!Number.isFinite(speed)) return 1;
  return Math.min(SPEED_MAX, Math.max(SPEED_MIN, speed));
}

export function clampVolume(volume: number): number {
  if (!Number.isFinite(volume)) return 1;
  return Math.min(VOLUME_MAX, Math.max(VOLUME_MIN, volume));
}

/** Timeline duration of a single clip: source span / speed, never negative. */
export function clipDuration(clip: Clip): number {
  const span = clip.out - clip.in;
  if (!(span > 0)) return 0;
  const speed = clampSpeed(clip.speed);
  return span / speed;
}

/** Sum of all clip timeline durations. Empty plan -> 0. */
export function planDuration(plan: Plan): number {
  if (!plan || !Array.isArray(plan.clips)) return 0;
  return plan.clips.reduce((total, c) => total + clipDuration(c), 0);
}

/**
 * Move the clip at `index` by `delta` positions (delta -1 = up, +1 = down).
 * Returns a NEW array; out-of-range moves are a no-op (returns a copy in original order).
 */
export function moveClip(clips: Clip[], index: number, delta: number): Clip[] {
  const next = clips.slice();
  const target = index + delta;
  if (index < 0 || index >= next.length) return next;
  if (target < 0 || target >= next.length) return next;
  const [item] = next.splice(index, 1);
  next.splice(target, 0, item);
  return next;
}

/**
 * Split the clip at `index` at source time `sourceTime` (absolute source seconds).
 * Produces two contiguous clips [in, sourceTime] and [sourceTime, out].
 * No-op (returns a copy) when the split point does not leave positive spans on both sides.
 * `newId` mints ids for the two halves (receives a short suffix).
 */
export function splitClipAt(
  clips: Clip[],
  index: number,
  sourceTime: number,
  newId: (suffix: string) => string,
): Clip[] {
  const next = clips.slice();
  const clip = next[index];
  if (!clip) return next;
  if (!(sourceTime > clip.in) || !(sourceTime < clip.out)) return next;
  const left: Clip = { ...clip, id: newId('a'), in: clip.in, out: sourceTime };
  const right: Clip = { ...clip, id: newId('b'), in: sourceTime, out: clip.out };
  next.splice(index, 1, left, right);
  return next;
}

export function resolvePreset(name: PresetName): Dimensions {
  return PRESETS[name];
}
