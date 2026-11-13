// Node built-in test runner. Imports the esbuild-compiled pure helpers.
// Run via `npm test` which builds src/lib/timeline.ts -> .test-build/timeline.mjs first.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  PRESETS,
  clipDuration,
  planDuration,
  moveClip,
  splitClipAt,
  clampSpeed,
  clampVolume,
  resolvePreset,
} from '../.test-build/timeline.mjs';

const clip = (over = {}) => ({
  id: 'c1',
  asset_id: 'a1',
  in: 0,
  out: 10,
  speed: 1,
  volume: 1,
  mute: false,
  ...over,
});

test('clipDuration: source span divided by speed', () => {
  assert.equal(clipDuration(clip({ in: 2, out: 12, speed: 1 })), 10);
  assert.equal(clipDuration(clip({ in: 0, out: 10, speed: 2 })), 5);
  assert.equal(clipDuration(clip({ in: 0, out: 10, speed: 0.5 })), 20);
});

test('clipDuration: zero/negative span is zero, never negative', () => {
  assert.equal(clipDuration(clip({ in: 5, out: 5 })), 0);
  assert.equal(clipDuration(clip({ in: 8, out: 4 })), 0);
});

test('clampSpeed: bounded 0.25..4', () => {
  assert.equal(clampSpeed(0), 0.25);
  assert.equal(clampSpeed(10), 4);
  assert.equal(clampSpeed(1.5), 1.5);
});

test('clampVolume: bounded 0..2', () => {
  assert.equal(clampVolume(-1), 0);
  assert.equal(clampVolume(3), 2);
  assert.equal(clampVolume(1.25), 1.25);
});

test('planDuration: sums clip timeline durations honoring speed', () => {
  const plan = {
    clips: [
      clip({ id: 'a', in: 0, out: 10, speed: 1 }), // 10
      clip({ id: 'b', in: 0, out: 10, speed: 2 }), // 5
      clip({ id: 'c', in: 4, out: 10, speed: 1 }), // 6
    ],
  };
  assert.equal(planDuration(plan), 21);
});

test('planDuration: empty clips allowed -> 0', () => {
  assert.equal(planDuration({ clips: [] }), 0);
});

test('moveClip: up swaps with previous, generates new array', () => {
  const clips = [clip({ id: 'a' }), clip({ id: 'b' }), clip({ id: 'c' })];
  const moved = moveClip(clips, 2, -1);
  assert.deepEqual(moved.map((c) => c.id), ['a', 'c', 'b']);
  assert.deepEqual(clips.map((c) => c.id), ['a', 'b', 'c']); // original untouched
});

test('moveClip: down swaps with next', () => {
  const clips = [clip({ id: 'a' }), clip({ id: 'b' }), clip({ id: 'c' })];
  assert.deepEqual(moveClip(clips, 0, 1).map((c) => c.id), ['b', 'a', 'c']);
});

test('moveClip: out-of-range no-op returns equal order', () => {
  const clips = [clip({ id: 'a' }), clip({ id: 'b' })];
  assert.deepEqual(moveClip(clips, 0, -1).map((c) => c.id), ['a', 'b']);
  assert.deepEqual(moveClip(clips, 1, 1).map((c) => c.id), ['a', 'b']);
});

test('splitClipAt: source time within span produces two contiguous clips', () => {
  const clips = [clip({ id: 'a', in: 0, out: 10 })];
  const out = splitClipAt(clips, 0, 6, (n) => `a_${n}`);
  assert.equal(out.length, 2);
  assert.deepEqual([out[0].in, out[0].out], [0, 6]);
  assert.deepEqual([out[1].in, out[1].out], [6, 10]);
  assert.notEqual(out[0].id, out[1].id);
  // carries speed/volume/mute
  assert.equal(out[1].asset_id, 'a1');
});

test('splitClipAt: split point at/near boundary is a no-op (needs both sides > 0)', () => {
  const clips = [clip({ id: 'a', in: 0, out: 10 })];
  assert.equal(splitClipAt(clips, 0, 0, (n) => n).length, 1);
  assert.equal(splitClipAt(clips, 0, 10, (n) => n).length, 1);
});

test('splitClipAt: preserves other clips and order', () => {
  const clips = [clip({ id: 'a', in: 0, out: 10 }), clip({ id: 'b', in: 0, out: 4 })];
  const out = splitClipAt(clips, 0, 5, (n) => `x${n}`);
  assert.deepEqual(out.map((c) => c.asset_id), ['a1', 'a1', 'a1']);
  assert.equal(out[2].id, 'b');
});

test('resolvePreset: known presets carry exact dimensions', () => {
  assert.deepEqual(resolvePreset('landscape'), { width: 1280, height: 720 });
  assert.deepEqual(resolvePreset('portrait'), { width: 720, height: 1280 });
  assert.deepEqual(resolvePreset('square'), { width: 1080, height: 1080 });
});

test('PRESETS: exposes the three output formats', () => {
  assert.deepEqual(Object.keys(PRESETS).sort(), ['landscape', 'portrait', 'square']);
});
