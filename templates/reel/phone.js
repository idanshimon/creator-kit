/* phone: screen recording / screenshot in a phone mockup with zoom punch-ins.
 * spec.screen: dataURI image (scrolls with beat.scroll 0..1) or {terminal:[lines], title}.
 * beat: {text (caption), zoom?: {x, y, scale}} x/y are 0..1 of the screen. */
window.R = window.R || { templates: {} };
R.templates.phone = (S, root, R, layer) => {
  const u = S.u, box = R.safeBox, items = R.content;
  const capH = Math.min(box.h * .2, 300 * u);
  const caps = items.map(b => {
    const c = R.css(R.el('div', '', root), { position: 'absolute', left: 0, right: 0, top: 0, height: capH,
      display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0, zIndex: 3 });
    const inner = R.css(R.el('div', 'display', c, R.markup(b.text || '')), { width: '100%', textAlign: 'center' });
    R.fit(inner, 76 * u, 34 * u, capH);
    return { b, c };
  });
  /* Phone sits in the safe column under the caption; zoomed pixels may cross the rail (no text there). */
  /* Punch-ins are clipped to a viewport inside the safe box, so zoomed screen text never
   * slides under the caption or the platform UI. */
  const vh = box.h - capH - 30 * u;
  const view = R.css(R.el('div', '', layer), { position: 'absolute', left: box.x - 20 * u, top: box.y + capH + 30 * u, width: box.w + 40 * u, height: vh, overflow: 'hidden',
    WebkitMaskImage: 'linear-gradient(180deg, transparent 0, #000 9%, #000 93%, transparent 100%)' });
  const ph = Math.min(vh - 40 * u, (box.w * .92) / .49), pw = ph * .49;
  const cam = R.css(R.el('div', '', view), { position: 'absolute', left: (box.w + 40 * u - pw) / 2, top: 20 * u, width: pw, height: ph, willChange: 'transform' });
  const body = R.css(R.el('div', '', cam), { position: 'absolute', inset: 0, borderRadius: pw * .14, background: '#0a0a0b',
    boxShadow: `0 0 0 ${3 * u}px #3a3b40, 0 ${60 * u}px ${140 * u}px rgba(0,0,0,.6)`, padding: pw * .035 });
  const scr = R.css(R.el('div', '', body), { position: 'relative', width: '100%', height: '100%', borderRadius: pw * .11, overflow: 'hidden', background: S.pal.surface });
  R.css(R.el('div', '', body), { position: 'absolute', top: pw * .06, left: '50%', width: pw * .28, height: pw * .075, marginLeft: -pw * .14, borderRadius: 99, background: '#000', zIndex: 2 });
  let img = null, term = null;
  const scrW = pw * .93;
  if (typeof S.screen === 'string') {
    img = R.css(R.el('img', '', scr), { position: 'absolute', left: 0, top: 0, width: '100%' }); img.src = S.screen;
  } else {
    const sc = S.screen || {};
    const fs = scrW / 21;
    const t = R.css(R.el('div', 'mono', scr), { position: 'absolute', inset: 0, padding: `${pw * .2}px ${fs * 1.2}px ${fs}px`, fontSize: fs, lineHeight: 1.55, color: S.pal.ink });
    R.css(R.el('div', '', t, R.esc(sc.title || 'terminal')), { color: S.pal.faint, borderBottom: `1px solid ${S.pal.border}`, paddingBottom: fs * .6, marginBottom: fs * .8 });
    const lines = (sc.terminal || []).map(l => {
      const e = R.css(R.el('div', '', t), { whiteSpace: 'pre-wrap', wordBreak: 'break-word', minHeight: '1.55em' });
      const col = /^\$/.test(l) ? S.pal.ink : /^(✓|ok|PASS)/i.test(l) ? S.pal.stable : /^(✕|x |FAIL|error)/i.test(l) ? S.pal.critical : S.pal.muted;
      e.style.color = col;
      return { e, l };
    });
    term = { lines };
  }
  const ring = R.css(R.el('div', '', scr), { position: 'absolute', width: scrW * .34, height: scrW * .34, borderRadius: '50%', border: `${4 * u}px solid ${S.hi}`, opacity: 0, zIndex: 3 });
  const z = b => b.zoom ? { x: b.zoom.x ?? .5, y: b.zoom.y ?? .5, s: b.zoom.scale ?? 1.8 } : { x: .5, y: .5, s: 1 };
  const T0 = items[0].start, T1 = items[items.length - 1].end;
  return t => {
    caps.forEach(({ b, c }) => {
      const L = R.life(t, b, .3, .2);
      c.style.opacity = t >= b.start ? L.v : 0;
      c.style.transform = `translateY(${(1 - L.in) * 30 * u}px) scale(${.96 + .04 * R.ease.back(L.in)})`;
    });
    const intro = R.ease.out5(R.seg(t, T0, T0 + .8));
    const i = Math.max(0, items.findIndex((b, k) => t >= b.start && (k === items.length - 1 || t < items[k + 1].start)));
    const cur = z(items[i]), prev = i > 0 ? z(items[i - 1]) : { x: .5, y: .5, s: 1 };
    const p = R.ease.out5(R.seg(t, items[i].start, items[i].start + .45));
    const x = R.lerp(prev.x, cur.x, p), y = R.lerp(prev.y, cur.y, p), s = R.lerp(prev.s, cur.s, p);
    const drift = 1 + .015 * Math.sin((t - T0) * 1.3);
    cam.style.transformOrigin = `${x * 100}% ${y * 100}%`;
    cam.style.transform = `translateY(${(1 - intro) * ph * .35}px) scale(${s * drift * (.92 + .08 * intro)})`;
    const last = items[items.length - 1];
    view.style.opacity = intro * (last.last ? 1 : 1 - R.seg(t, last.end - .3, last.end));
    ring.style.left = `calc(${x * 100}% - ${scrW * .17}px)`; ring.style.top = `calc(${y * 100}% - ${scrW * .17}px)`;
    const rp = R.seg(t, items[i].start + .3, items[i].start + 1.1);
    ring.style.opacity = items[i].zoom ? Math.sin(rp * Math.PI) * .9 : 0;
    ring.style.transform = `scale(${(.7 + .5 * rp) / Math.max(1, s)})`;
    if (img && img.naturalHeight) {
      const sc = R.lerp(i > 0 ? (items[i - 1].scroll || 0) : 0, items[i].scroll || 0, R.ease.inOut(R.seg(t, items[i].start, items[i].start + .9)));
      const over = Math.max(0, img.offsetHeight - scr.clientHeight);
      img.style.transform = `translateY(${-sc * over}px)`;
    }
    if (term) {
      const n = term.lines.length, span = (T1 - T0) * .85;
      term.lines.forEach(({ e, l }, k) => {
        const a = T0 + .5 + span * k / Math.max(1, n), b = a + Math.min(.6, span / n * .7);
        const q = R.seg(t, a, b);
        e.textContent = l.slice(0, Math.round(l.length * q)) + (q > 0 && q < 1 ? '▍' : '');
      });
    }
  };
};
