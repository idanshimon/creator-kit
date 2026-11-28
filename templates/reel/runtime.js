/* Creator Kit reel runtime. Deterministic: every frame is a pure function of t.
 * Contract for creator_tools/showcase.py: window.__ready, window.__advance(ms), window.__done().
 * No network, no Date, no timers in render mode. Open index.html#play for a live preview. */
(function () {
  const S = window.__SPEC;
  const R = window.R = window.R || { templates: {} };
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  R.clamp = clamp;
  R.seg = (t, a, b) => (b <= a ? (t >= b ? 1 : 0) : clamp((t - a) / (b - a)));
  R.lerp = (a, b, p) => a + (b - a) * p;
  R.ease = {
    out: p => 1 - Math.pow(1 - p, 3),
    out5: p => 1 - Math.pow(1 - p, 5),
    inOut: p => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    in: p => p * p * p,
    back: p => { const c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); },
    expo: p => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
  };
  R.esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  /* *word* or *a phrase* marks emphasis (accent colour). */
  R.markup = s => R.esc(s).replace(/(\w)-(\w)/g, '$1\u2011$2').replace(/\*([^*]+)\*/g, '<span class="hl">$1</span>');
  R.tokens = s => {
    const out = []; let hl = false;
    String(s || '').split(/(\*)/).forEach(part => {
      if (part === '*') { hl = !hl; return; }
      part.split(/\s+/).filter(Boolean).forEach(w => out.push({ w, hl }));
    });
    return out;
  };
  R.el = (tag, cls, parent, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  };
  R.css = (e, o) => { for (const k in o) e.style[k] = typeof o[k] === 'number' && !/opacity|zIndex|flex|fontWeight|lineHeight/.test(k) ? o[k] + 'px' : o[k]; return e; };
  /* Shrink font until the element's content fits its own box (no clipped text). */
  R.fit = (e, max, min, maxH) => {
    let size = max;
    e.style.fontSize = size + 'px';
    const ok = () => e.scrollWidth <= e.clientWidth + 1 &&
      (maxH ? e.offsetHeight <= maxH : e.scrollHeight <= e.clientHeight + 1) &&
      [...e.querySelectorAll('.word')].every(w => w.offsetWidth <= e.clientWidth + 1);
    for (let i = 0; i < 80 && size > min; i++) {
      if (ok()) break;
      size *= 0.95; e.style.fontSize = size + 'px';
    }
    return size;
  };
  /* Word timings for a beat: explicit beat.words [{w,s,e}] (absolute seconds) or spread by length. */
  R.wordTimes = (beat, from = 0.05, span = 0.78) => {
    const toks = R.tokens(beat.text);
    if (beat.words && beat.words.length === toks.length) return toks.map((k, i) => ({ ...k, s: beat.words[i].s, e: beat.words[i].e }));
    const d = beat.end - beat.start, a = beat.start + Math.min(from, d * .1), b = beat.start + d * span;
    const total = toks.reduce((n, k) => n + k.w.length + 2, 0) || 1;
    let c = a;
    return toks.map(k => { const s = c; c += (b - a) * (k.w.length + 2) / total; return { ...k, s, e: c }; });
  };
  R.beatIndex = t => { let i = 0; S.beats.forEach((b, k) => { if (t >= b.start) i = k; }); return i; };
  /* Enter/exit envelope for a beat: 0 before, 1 while on screen, back to 0 at exit. */
  R.life = (t, b, inS = .35, outS = .28) => {
    const i = R.ease.out(R.seg(t, b.start, b.start + inS));
    const o = b.last ? 1 : 1 - R.ease.in(R.seg(t, b.end - outS, b.end));
    return { in: i, out: o, v: Math.min(i, o) };
  };

  const root = document.documentElement, u = S.u, P = S.pal;
  const vars = { '--W': S.W + 'px', '--H': S.H + 'px', '--u': u, '--bg': P.bg, '--panel': P.panel, '--raised': P.raised,
    '--ink': P.ink, '--muted': P.muted, '--faint': P.faint, '--border': P.border, '--accent': P.accent, '--hi': S.hi,
    '--onhi': S.onhi, '--font': S.font, '--mono': S.mono, '--r': (S.radius * u) + 'px' };
  for (const k in vars) root.style.setProperty(k, vars[k]);

  const stage = R.el('div', '', document.body); stage.id = 'stage';
  const bg = R.el('div', '', stage); bg.id = 'bg';
  const g1 = R.el('div', 'glow', bg), g2 = R.el('div', 'glow', bg), g3 = R.el('div', 'glow', bg);
  const D = Math.max(S.W, S.H);
  R.css(g1, { width: D * .7, height: D * .7, background: S.hi, opacity: .16 });
  R.css(g2, { width: D * .6, height: D * .6, background: S.hi2, opacity: .14 });
  R.css(g3, { width: D * .5, height: D * .5, background: P.raised, opacity: .9 });
  const media = R.el('div', '', stage); media.id = 'media';
  if (S.background) { R.el('img', '', media).src = S.background; R.el('div', 'shade', media); }
  R.el('div', '', stage).id = 'vignette';
  const layer = R.el('div', 'layer', stage); /* full-bleed template layer (behind safe text) */
  const safe = R.el('div', '', stage); safe.id = 'safe';
  const sz = S.safe;
  /* A handle watermark gets its own strip at the bottom of the safe box; templates lay out above it. */
  /* Inner gutter keeps glyphs off the safe-zone edge; progress bar and handle get their own strips. */
  const g = 28 * u, hs = S.handle ? 70 * u : 0, ps = S.progress ? 44 * u : 0;
  R.safeBox = { x: sz.l + g, y: sz.t + ps + g * .5, w: S.W - sz.l - sz.r - 2 * g, h: S.H - sz.t - sz.b - hs - ps - g };
  R.css(safe, { left: R.safeBox.x, top: R.safeBox.y, width: R.safeBox.w, height: R.safeBox.h });
  R.el('div', '', stage).id = 'grain';

  let bar = null;
  if (S.progress) {
    const p = R.el('div', '', stage); p.id = 'progress';
    R.css(p, { left: sz.l + g, width: S.W - sz.l - sz.r - 2 * g, top: sz.t + 12 * u });
    bar = R.el('i', '', p);
  }
  let handle = null;
  if (S.handle) {
    handle = R.el('div', '', stage, R.esc(S.handle)); handle.id = 'handle';
    R.css(handle, { left: sz.l, width: S.W - sz.l - sz.r, textAlign: 'center', top: S.H - sz.b - 54 * u, fontSize: 30 * u, color: S.pal.ink });
  }
  const qs = new URLSearchParams(location.search);
  const RENDER = qs.get('render') === '1';
  if (RENDER) document.body.classList.add('render');

  const zones = R.el('div', '', stage); zones.id = 'zones';
  zones.style.display = S.showSafe ? 'block' : 'none';
  {
    const add = (o, label) => { const e = R.css(R.el('div', 'z', zones), o); if (label) R.css(R.el('div', 'lbl', e, label), { left: 12, top: 12 }); };
    add({ left: 0, top: 0, width: S.W, height: sz.t }, 'top UI ' + sz.t + 'px');
    add({ left: 0, top: S.H - sz.b, width: S.W, height: sz.b }, 'caption / sound ' + sz.b + 'px');
    if (sz.l) add({ left: 0, top: sz.t, width: sz.l, height: S.H - sz.t - sz.b });
    add({ left: S.W - sz.r, top: sz.t, width: sz.r, height: S.H - sz.t - sz.b }, sz.r > 120 ? 'rail' : '');
    R.css(R.el('div', 'box', zones), { left: sz.l, top: sz.t, width: S.W - sz.l - sz.r, height: S.H - sz.t - sz.b });
  }

  R.content = S.beats.filter(b => b.kind !== 'end');
  const make = R.templates[S.template];
  if (!make) throw new Error('unknown reel template ' + S.template);
  const drawTemplate = make(S, safe, R, layer);

  /* Shared end card (beat kind "end"): loop-friendly CTA every template can finish on. */
  const ends = S.beats.filter(b => b.kind === 'end').map(b => {
    const box = R.css(R.el('div', 'fill center', safe), { flexDirection: 'column', gap: 0, opacity: 0 });
    const mark = R.css(R.el('div', '', box), { width: 120 * u, height: 120 * u, borderRadius: '50%', marginBottom: 56 * u,
      background: `conic-gradient(from 210deg, ${S.hi}, ${S.hi2}, ${S.hi})`, boxShadow: `0 0 ${90 * u}px ${S.hi}55` });
    const h = R.css(R.el('div', 'display', box, R.markup(b.text)), { width: '100%' });
    const sub = b.sub ? R.css(R.el('div', 'body', box, R.markup(b.sub)), { width: '88%', marginTop: 28 * u }) : null;
    const pill = b.cta ? R.css(R.el('div', 'pill', box, R.esc(b.cta)), { marginTop: 56 * u, background: S.hi, color: S.onhi, fontSize: 40 * u }) : null;
    R.fit(h, 112 * u, 48 * u, R.safeBox.h * .38);
    if (sub) R.fit(sub, 44 * u, 26 * u, R.safeBox.h * .2);
    return { b, box, mark, h, sub, pill };
  });
  function drawEnds(t) {
    ends.forEach(({ b, box, mark, h, sub, pill }) => {
      const L = R.life(t, b, .5, .3);
      box.style.opacity = L.v;
      const p = R.ease.back(R.seg(t, b.start, b.start + .6));
      mark.style.transform = `scale(${.4 + .6 * p}) rotate(${(t - b.start) * 40}deg)`;
      h.style.transform = `translateY(${(1 - R.ease.out(R.seg(t, b.start + .1, b.start + .6))) * 60 * u}px)`;
      if (sub) sub.style.opacity = R.ease.out(R.seg(t, b.start + .3, b.start + .8));
      if (pill) { const q = R.ease.back(R.seg(t, b.start + .5, b.start + 1)); pill.style.opacity = q; pill.style.transform = `scale(${.8 + .2 * q})`; }
    });
  }

  function draw(t) {
    t = Math.min(t, S.duration);
    const k = t / Math.max(S.duration, .001);
    bg.style.transform = `translate(${Math.sin(k * 6.283) * 2}%, ${Math.cos(k * 6.283) * 2}%)`;
    R.css(g1, { left: S.W * (.05 + .1 * Math.sin(k * 6.283)), top: S.H * (.02 + .06 * Math.cos(k * 6.283)) });
    R.css(g2, { left: S.W * (.45 - .08 * Math.cos(k * 6.283)), top: S.H * (.55 + .05 * Math.sin(k * 6.283)) });
    R.css(g3, { left: S.W * .25, top: S.H * .3 });
    if (S.background) {
      const img = media.firstChild; img.style.transform = `scale(${1.06 + .08 * k}) translateY(${-1.5 * k}%)`;
    }
    /* Loop-friendly: content fades in from and out to the bare background, so last frame == first frame. */
    let env = 1;
    if (S.loop) env = Math.min(R.ease.out(R.seg(t, 0, .3)), 1 - R.ease.in(R.seg(t, S.duration - .4, S.duration)));
    safe.style.opacity = env; layer.style.opacity = env;
    if (handle) handle.style.opacity = env * .85;
    if (bar) bar.style.width = (k * 100).toFixed(3) + '%';
    drawTemplate(t);
    drawEnds(t);
  }

  let T = 0, syncHud = null;
  window.__advance = ms => { T += ms; draw(T / 1000); };
  window.__done = () => T / 1000 >= S.duration;
  window.__seek = s => { T = clamp(s, 0, S.duration) * 1000; draw(T / 1000); if (syncHud) syncHud(); };
  const qt = qs.get('t'); /* ?t=2.5 -> still at 2.5 s */
  if (qt) window.__seek(Math.max(0, +qt || 0)); else draw(0);
  window.__ready = true;

  if (!RENDER) {
    const hud = R.el('div', '', document.body); hud.id = 'hud';
    const btn = (label, act, title) => {
      const b = R.el('button', '', hud, label);
      b.type = 'button'; b.dataset.act = act; b.title = title;
      return b;
    };
    const bPlay = btn('▶', 'play', 'Play / Pause (Space)');
    const bReset = btn('↺', 'reset', 'Reset (R)');
    const bPrev = btn('⏮', 'prev', 'Prev Beat (←)');
    const bNext = btn('⏭', 'next', 'Next Beat (→)');
    R.el('span', 'sep', hud);
    const slider = R.el('input', 'scrub', hud);
    slider.type = 'range'; slider.min = '0'; slider.max = String(S.duration); slider.step = '0.01'; slider.value = String(T / 1000);
    const readout = R.el('span', 'readout', hud);
    R.el('span', 'sep', hud);
    const bZones = btn('Safe', 'zones', 'Toggle Safe Zones (Z)');
    const speeds = [0.5, 1, 1.5];
    let spIdx = 1;
    const bSpeed = btn('1×', 'speed', 'Playback Speed');

    let playing = false, rafId = null, last = null;
    let zonesOn = !!S.showSafe;

    const fmtT = s => s.toFixed(1) + 's';
    syncHud = () => {
      const sec = clamp(T / 1000, 0, S.duration);
      const bi = R.beatIndex(sec) + 1;
      slider.value = sec.toFixed(2);
      readout.textContent = `${fmtT(sec)} / ${fmtT(S.duration)} · ${bi}/${S.beats.length}`;
      bPlay.textContent = playing ? '⏸' : '▶';
      bPlay.classList.toggle('active', playing);
      bZones.classList.toggle('active', zonesOn);
      bSpeed.textContent = speeds[spIdx] + '×';
    };

    const tick = now => {
      if (!playing) return;
      if (last != null) {
        T += (now - last) * speeds[spIdx];
        if (T / 1000 > S.duration) T = 0;
        draw(T / 1000);
        syncHud();
      }
      last = now;
      rafId = requestAnimationFrame(tick);
    };
    const setPlaying = on => {
      playing = !!on;
      if (playing) { last = null; if (!rafId) rafId = requestAnimationFrame(tick); }
      else { if (rafId) { cancelAnimationFrame(rafId); rafId = null; } last = null; }
      syncHud();
    };
    const toggleZones = () => { zonesOn = !zonesOn; zones.style.display = zonesOn ? 'block' : 'none'; syncHud(); };
    const jumpBeat = dir => {
      const sec = T / 1000;
      const cur = R.beatIndex(sec);
      let target = cur;
      if (dir < 0) target = (sec - S.beats[cur].start > 0.25) ? cur : Math.max(0, cur - 1);
      else target = Math.min(S.beats.length - 1, cur + 1);
      window.__seek(S.beats[target].start);
    };

    bPlay.addEventListener('click', () => setPlaying(!playing));
    bReset.addEventListener('click', () => { window.__seek(0); });
    bPrev.addEventListener('click', () => jumpBeat(-1));
    bNext.addEventListener('click', () => jumpBeat(1));
    bZones.addEventListener('click', toggleZones);
    bSpeed.addEventListener('click', () => { spIdx = (spIdx + 1) % speeds.length; syncHud(); });
    slider.addEventListener('input', () => { window.__seek(parseFloat(slider.value) || 0); });

    document.addEventListener('keydown', e => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key;
      if (k === ' ') { e.preventDefault(); setPlaying(!playing); }
      else if (k === 'ArrowLeft') { e.preventDefault(); jumpBeat(-1); }
      else if (k === 'ArrowRight') { e.preventDefault(); jumpBeat(1); }
      else if (k === 'r' || k === 'R') { e.preventDefault(); window.__seek(0); }
      else if (k === 'z' || k === 'Z') { e.preventDefault(); toggleZones(); }
    });

    syncHud();
    if (location.hash === '#play') setPlaying(true);
  }
})();
