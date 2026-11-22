# SDLC loop

Use `<sdlc-loop>` as the standard stage map for HTML SDLC walkthroughs. Open [the synthetic demo](demo.html) directly from disk. Only [sdlc-loop.js](sdlc-loop.js) is required in a production: a classic script with no imports, network requests, fonts or build step.

The dial answers **“Which stage is this chapter discussing?”**, not “Which work is done?” It starts in overview. Stages can be skipped, revisited or discussed hypothetically. Neither reaching the final chapter nor inspecting **Resolved** verifies closure. Put actual evidence in the walkthrough, not in a percentage or an inferred checkmark.

## Mount and drive it from HTML chapters

Place the element inside a positioned container for an upper-left overlay. Reserve space away from important controls; on a phone place it in flow above the content (as in the demo). Include a viewport meta tag on the host page.

```html
<script src="./sdlc-loop.js"></script>
<div style="position:relative">
  <sdlc-loop id="map"></sdlc-loop>
  <!-- chapter content or video; reserve the upper-left corner -->
</div>
<script>
  const map = document.querySelector('#map');
  const chapterStages = [null, 'issue', 'plan', 'review'];
  function onChapterShown(index) {
    map.setStage(chapterStages[index] ?? null);
  }
  onChapterShown(0); // also call from Next, Previous and direct chapter navigation
</script>
```

The default labels are Issue, Triage, Plan, Implement, Checks, Review, Merge, Resolved; IDs are their lowercase spellings. To replace them, assign a non-empty array with unique non-blank string IDs, non-blank labels and string details:

```js
map.stages = [{id:'report', label:'Report', detail:'What did the reader observe?'},
              {id:'verify', label:'Verify', detail:'Compare against the original report.'}];
map.setStage('report');
map.setStage(null); // overview; no active stage
```

The list is copied. Replacing it closes inspection and preserves the narrative ID only if still present. Invalid lists throw `TypeError`; unknown stage IDs throw `RangeError` without changing the map. IDs are case-sensitive. Each element owns its own state.

## Sync an HTML video

Use authored intervals in seconds on the video's clock, with inclusive starts and exclusive ends. This example uses the **default** IDs. Compute from `currentTime`, never from a counter: backward seeks and unmapped intros/outros must work too.

```js
const video = document.querySelector('video');
const cues = [[4, 12, 'issue'], [12, 24, 'plan'], [24, 33, 'review']];
function sync() {
  const t = video.currentTime;
  map.setStage(cues.find(([start,end]) => start <= t && t < end)?.[2] ?? null);
}
for (const event of ['loadedmetadata','timeupdate','seeked','emptied']) {
  video.addEventListener(event, sync);
}
sync();
```

This is an interactive overlay in the **HTML player**, not something burnt into the MP4. Opening the MP4 alone will not show the map. A burned-in version requires separately rendering/compositing the map into frames and loses inspection controls.

## Inspect, theme and test

Click or tap a numbered node, or Tab to it and press Enter/Space. **Inspect stages** opens a named picker; use the native selection controls or Home/End. Escape closes inspection and focuses the toggle. The picker remains independent when a chapter changes. Larger lists (more than eight stages) use the picker rather than squeezing touch targets onto the dial. The current narrative stage has a text label and ordinal as well as a visual highlight.

The default follows system light/dark appearance. Set `theme="light"` or `theme="dark"` on the element to override. Reduced motion disables the button color transition. Position and size can be overridden with ordinary CSS on `sdlc-loop`; internal styles are isolated by Shadow DOM.

From the kit root, with the kit’s `studio-ui` dev dependencies and Chrome installed:

```sh
node studio-ui/verify-sdlc-loop.mjs
```

Set `CHROME_PATH` to an alternate Chromium executable if needed. The test opens this demo via `file://` offline, including touch emulation at phone width. No browser server, account or video asset is needed.
