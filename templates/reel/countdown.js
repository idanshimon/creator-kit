/* countdown: top-N list. Big numeral rolls N..1, item title + one line, rank rail.
 * spec.title = header; beat: {title, text, rank?} */
window.R = window.R || { templates: {} };
R.templates.countdown = (S, root, R) => {
  const u = S.u, box = R.safeBox, items = R.content, N = items.length;
  const head = R.css(R.el('div', '', root), { position: 'absolute', left: 0, right: 0, top: 0, textAlign: 'center' });
  const eb = R.css(R.el('div', 'eyebrow', head, R.esc(S.kicker || 'Top ' + N)), { fontSize: 28 * u, marginBottom: 14 * u });
  const ttl = R.css(R.el('div', 'display', head, R.markup(S.title || '')), { width: '100%' });
  R.fit(ttl, 72 * u, 36 * u, box.h * .16);
  const top = head.offsetHeight + 40 * u;
  const rail = R.css(R.el('div', '', root), { position: 'absolute', left: 0, right: 0, bottom: 0, display: 'flex', justifyContent: 'center', gap: 18 * u });
  const dots = items.map((b, i) => R.css(R.el('div', 'mono', rail, String(b.rank || N - i)), {
    width: 64 * u, height: 64 * u, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 26 * u, fontWeight: 600, border: `${2 * u}px solid ${S.pal.border}`, color: S.pal.muted }));
  const avail = box.h - top - 64 * u - 50 * u;
  const B = items.map((b, i) => {
    const card = R.css(R.el('div', '', root), { position: 'absolute', left: 0, right: 0, top, height: avail, display: 'flex',
      flexDirection: 'column', justifyContent: 'center', opacity: 0 });
    const numWrap = R.css(R.el('div', '', card), { height: avail * .46, overflow: 'hidden', display: 'flex', alignItems: 'flex-end' });
    const num = R.css(R.el('div', 'display', numWrap, String(b.rank || N - i)), { fontSize: Math.min(avail * .5, 420 * u), lineHeight: .86,
      letterSpacing: '-.06em', background: `linear-gradient(160deg, ${S.pal.ink} 20%, ${S.hi})`, WebkitBackgroundClip: 'text', color: 'transparent' });
    const bar = R.css(R.el('div', '', card), { height: 6 * u, width: 140 * u, background: S.hi, borderRadius: 9, margin: `${28 * u}px 0 ${30 * u}px`, transformOrigin: 'left' });
    const t1 = R.css(R.el('div', 'display', card, R.markup(b.title)), { width: '100%' });
    const t2 = b.text ? R.css(R.el('div', 'body', card, R.markup(b.text)), { width: '100%', marginTop: 20 * u }) : null;
    R.fit(t1, 92 * u, 40 * u, avail * .26);
    if (t2) R.fit(t2, 42 * u, 24 * u, avail * .2);
    return { b, card, num, bar, t1, t2 };
  });
  return t => {
    head.style.opacity = R.ease.out(R.seg(t, 0, .5));
    rail.style.opacity = R.ease.out(R.seg(t, .2, .7)) * (R.content[N - 1].last ? 1 : 1 - R.seg(t, R.content[N - 1].end - .3, R.content[N - 1].end));
    head.style.opacity *= (R.content[N - 1].last ? 1 : 1 - R.seg(t, R.content[N - 1].end - .3, R.content[N - 1].end));
    const cur = items.findIndex(b => t >= b.start && t < b.end);
    dots.forEach((d, i) => {
      const on = i === cur;
      d.style.background = on ? S.hi : (i < cur || cur < 0 && t > items[i].end ? S.pal.raised : 'transparent');
      d.style.color = on ? S.onhi : S.pal.muted;
      d.style.borderColor = on ? S.hi : S.pal.border;
      d.style.transform = `scale(${on ? 1.12 : 1})`;
    });
    B.forEach(({ b, card, num, bar, t1, t2 }) => {
      const L = R.life(t, b, .5, .3);
      card.style.opacity = t >= b.start ? L.out : 0;
      const p = R.ease.out5(R.seg(t, b.start, b.start + .55));
      num.style.transform = `translateY(${(1 - p) * 100}%)`;
      bar.style.transform = `scaleX(${R.ease.out(R.seg(t, b.start + .2, b.start + .7))})`;
      const q = R.ease.out(R.seg(t, b.start + .18, b.start + .6));
      t1.style.opacity = q; t1.style.transform = `translateY(${(1 - q) * 40 * u}px)`;
      if (t2) { const r = R.ease.out(R.seg(t, b.start + .35, b.start + .8)); t2.style.opacity = r; t2.style.transform = `translateY(${(1 - r) * 30 * u}px)`; }
      card.style.transform = `translateY(${-(1 - L.out) * 60 * u}px)`;
    });
  };
};
