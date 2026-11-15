/* before-after: split wipe. beats[0] = before, beats[1] = after; extra beats are captions.
 * panel beat: {label, text, lines?: [..], media?: dataURI}. Divider sweeps, then settles at 50%. */
window.R = window.R || { templates: {} };
R.templates['before-after'] = (S, root, R) => {
  const u = S.u, box = R.safeBox, [A, B, ...caps] = R.content;
  const head = S.title ? R.css(R.el('div', 'display', root, R.markup(S.title)), { position: 'absolute', left: 0, right: 0, top: 0, textAlign: 'center' }) : null;
  if (head) R.fit(head, 76 * u, 36 * u, box.h * .15);
  const top = head ? head.offsetHeight + 44 * u : 0;
  const capH = caps.length ? box.h * .14 : 0;
  const ch = box.h - top - capH - (caps.length ? 36 * u : 0);
  const frame = R.css(R.el('div', 'card', root), { position: 'absolute', left: 0, right: 0, top, height: ch, overflow: 'hidden' });
  const panel = (b, after) => {
    const p = R.css(R.el('div', 'fill', frame), { background: after ? S.pal.panel : S.pal.surface, padding: `${120 * u}px ${56 * u}px ${56 * u}px` });
    if (b.media) { R.css(R.el('img', '', p), { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }).src = b.media; }
    else {
      const col = R.css(R.el('div', '', p), { width: '100%', display: 'flex', flexDirection: 'column', gap: '.55em' });
      if (b.text) R.css(R.el('div', 'display', col, R.markup(b.text)), { fontSize: '1.5em', marginBottom: '.3em', color: after ? S.pal.ink : S.pal.muted });
      (b.lines || []).forEach(l => {
        const row = R.css(R.el('div', '', col), { display: 'flex', gap: '.6em', alignItems: 'baseline', lineHeight: 1.25, color: after ? S.pal.ink : S.pal.muted });
        R.css(R.el('span', 'mono', row, after ? '✓' : '✕'), { color: after ? S.hi : S.pal.critical, fontWeight: 700, flex: 'none' });
        R.el('span', '', row, R.markup(l));
      });
      R.fit(col, 50 * u, 22 * u, ch - 180 * u);
    }
    const lab = R.css(R.el('div', 'pill mono', p, R.esc(b.label || (after ? 'After' : 'Before'))), { position: 'absolute', top: 36 * u,
      fontSize: 26 * u, textTransform: 'uppercase', letterSpacing: '.14em', background: after ? S.hi : S.pal.raised, color: after ? S.onhi : S.pal.muted });
    lab.style[after ? 'right' : 'left'] = 36 * u + 'px';
    return p;
  };
  panel(A, false);
  const after = panel(B, true);
  const div = R.css(R.el('div', '', frame), { position: 'absolute', top: 0, bottom: 0, width: 4 * u, marginLeft: -2 * u, background: S.pal.ink, boxShadow: `0 0 ${30 * u}px rgba(0,0,0,.6)` });
  const knob = R.css(R.el('div', 'mono', div, '‹ ›'), { position: 'absolute', top: '50%', left: '50%', width: 92 * u, height: 92 * u, margin: `${-46 * u}px 0 0 ${-46 * u}px`,
    borderRadius: '50%', background: S.pal.ink, color: S.pal.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 34 * u, fontWeight: 700 });
  const C = caps.map(b => {
    const c = R.css(R.el('div', '', root), { position: 'absolute', left: 0, right: 0, bottom: 0, height: capH,
      display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0 });
    const inner = R.css(R.el('div', 'display', c, R.markup(b.text)), { width: '100%', textAlign: 'center' });
    R.fit(inner, 64 * u, 30 * u, capH);
    return { b, c };
  });
  const lastEnd = R.content[R.content.length - 1];
  return t => {
    const out = lastEnd.last ? 1 : 1 - R.ease.in(R.seg(t, lastEnd.end - .3, lastEnd.end));
    const inn = R.ease.out(R.seg(t, A.start, A.start + .5));
    frame.style.opacity = inn * out; if (head) head.style.opacity = inn * out;
    frame.style.transform = `scale(${.96 + .04 * inn})`;
    const w1 = R.ease.inOut(R.seg(t, B.start, B.start + 1.0));
    const settle = R.ease.inOut(R.seg(t, B.start + (B.end - B.start) * .55, B.start + (B.end - B.start) * .55 + .8));
    const half = (A.media && B.media) ? .5 : 0; /* text panels don't split: mixed lines read as garbage */
    const x = t < B.start ? 1 : (1 - w1) + settle * half; /* fraction of width still showing "before" */
    const xr = Math.min(1, Math.max(0, x));
    after.style.clipPath = `inset(0 0 0 ${xr * 100}%)`;
    div.style.left = xr * 100 + '%';
    div.style.opacity = t >= B.start - .2 && xr > .005 && xr < .995 ? 1 : 0;
    C.forEach(({ b, c }) => { const L = R.life(t, b, .4, .25); c.style.opacity = t >= b.start ? L.v : 0; c.style.transform = `translateY(${(1 - L.in) * 30 * u}px)`; });
  };
};
