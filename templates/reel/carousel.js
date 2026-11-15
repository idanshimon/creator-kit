/* carousel: "things I wish I knew" swipe cards. beat kind "cover" = title card;
 * other beats: {title, text}. Cards slide in from the right with page count + dots. */
window.R = window.R || { templates: {} };
R.templates.carousel = (S, root, R) => {
  const u = S.u, box = R.safeBox, all = R.content, cards = all.filter(b => b.kind !== 'cover');
  const ch = Math.min(box.h * .86, box.w * 1.45), cw = box.w;
  const dotsRow = R.css(R.el('div', '', root), { position: 'absolute', left: 0, right: 0, top: (box.h + ch) / 2 + 30 * u, display: 'flex', justifyContent: 'center', gap: 14 * u });
  const dots = cards.map(() => R.css(R.el('div', '', dotsRow), { height: 12 * u, width: 12 * u, borderRadius: 9, background: S.pal.border }));
  const B = all.map(b => {
    const cover = b.kind === 'cover';
    const c = R.css(R.el('div', 'card', root), { position: 'absolute', left: 0, top: (box.h - ch) / 2, width: cw, height: ch, padding: 64 * u,
      display: 'flex', flexDirection: 'column', opacity: 0, background: cover ? `linear-gradient(155deg, ${S.pal.raised}, ${S.pal.panel})` : S.pal.panel });
    const n = cards.indexOf(b) + 1;
    const top = R.css(R.el('div', 'mono', c, cover ? R.esc(b.tag || 'Swipe →') : `${String(n).padStart(2, '0')}`), { color: S.hi, fontSize: 34 * u, fontWeight: 600, letterSpacing: '.08em' });
    const body = R.css(R.el('div', '', c), { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: cover ? 'center' : 'flex-end', minHeight: 0 });
    const h = R.css(R.el('div', 'display', body, R.markup(b.title || b.text)), { width: '100%' });
    const p = (b.title && b.text) ? R.css(R.el('div', 'body', body, R.markup(b.text)), { width: '100%', marginTop: 28 * u }) : null;
    const foot = R.css(R.el('div', 'mono', c, cover ? '' : `${n} / ${cards.length}`), { color: S.pal.faint, fontSize: 26 * u, marginTop: 36 * u, textAlign: 'right' });
    const room = ch - 128 * u - top.offsetHeight - 70 * u;
    R.fit(h, (cover ? 120 : 84) * u, 40 * u, p ? room * .55 : room);
    if (p) R.fit(p, 44 * u, 24 * u, room - h.offsetHeight - 28 * u);
    return { b, c, cover, n };
  });
  return t => {
    dotsRow.style.opacity = R.ease.out(R.seg(t, cards[0] ? cards[0].start : 0, (cards[0] ? cards[0].start : 0) + .4));
    const last = all[all.length - 1];
    if (!last.last) dotsRow.style.opacity *= 1 - R.seg(t, last.end - .3, last.end);
    B.forEach(({ b, c, n }, i) => {
      const pin = R.ease.out5(R.seg(t, b.start, b.start + .6));
      const nxt = all[i + 1];
      const pout = nxt ? R.ease.inOut(R.seg(t, nxt.start, nxt.start + .6)) : (b.last ? 0 : R.ease.in(R.seg(t, b.end - .3, b.end)));
      const x = (1 - pin) * (cw + 60 * u) - pout * cw * .18;
      c.style.opacity = t < b.start ? 0 : (nxt ? 1 - pout : 1 - pout);
      c.style.transform = `translateX(${x}px) rotate(${(1 - pin) * 5}deg) scale(${1 - pout * .08})`;
      c.style.zIndex = i;
      if (n > 0) dots[n - 1].style.cssText += `;width:${(t >= b.start && (!nxt || t < nxt.start) ? 44 : 12) * u}px;background:${t >= b.start ? S.hi : S.pal.border}`;
    });
  };
};
