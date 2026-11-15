/* kinetic: word-by-word punch captions / karaoke highlight. Hook-first short-form staple.
 * beat: {text, mode?: "punch"|"karaoke", words?: [{s,e}]}  *word* = emphasis colour. */
window.R = window.R || { templates: {} };
R.templates.kinetic = (S, root, R) => {
  const u = S.u, box = R.safeBox;
  let eyebrow = null;
  if (S.title) {
    eyebrow = R.css(R.el('div', 'eyebrow', root, R.esc(S.title)), { position: 'absolute', left: 0, right: 0, top: 0, textAlign: 'center', fontSize: 30 * u });
  }
  const B = R.content.map(b => {
    const wrap = R.css(R.el('div', 'fill center', root), { opacity: 0 });
    const line = R.css(R.el('div', 'display', wrap), { width: '88%', textAlign: 'center', lineHeight: 1.08 });
    const words = R.wordTimes(b).map(k => ({ ...k, el: R.el('span', 'word', null, R.esc(k.w)) }));
    words.forEach((k, i) => { line.appendChild(k.el); if (i < words.length - 1) line.appendChild(document.createTextNode(' ')); });
    R.fit(line, (b.size || 140) * u, 52 * u, box.h * .7);
    return { b, wrap, line, words, mode: b.mode || S.mode || 'punch' };
  });
  return t => {
    if (eyebrow) eyebrow.style.opacity = R.ease.out(R.seg(t, 0, .6));
    B.forEach(({ b, wrap, words, mode }) => {
      const L = R.life(t, b, .12, .22);
      const vis = t >= b.start - .01 && L.out > 0;
      wrap.style.opacity = vis ? L.out : 0;
      wrap.style.transform = `translateY(${-(1 - L.out) * 70 * u}px) scale(${1 - (1 - L.out) * .04})`;
      if (!vis) return;
      words.forEach(k => {
        const on = R.seg(t, k.s, k.s + .14), active = t >= k.s && t < k.e + .04;
        const e = k.el.style;
        if (mode === 'karaoke') {
          e.opacity = Math.max(.5, on);
          e.transform = `scale(${active ? 1 + .05 * (1 - R.seg(t, k.s, k.s + .2)) : 1})`;
          e.color = t >= k.s ? (k.hl ? S.hi : S.pal.ink) : S.pal.muted;
        } else {
          const p = R.ease.back(on);
          e.opacity = R.ease.out(on);
          e.transform = `translateY(${(1 - p) * 0.35}em) scale(${.86 + .14 * p})`;
          e.color = active && !k.hl ? S.onhi : (k.hl ? S.hi : S.pal.ink);
        }
        e.background = active && !k.hl ? S.hi : 'transparent';
        if (active && k.hl) e.color = S.hi;
      });
    });
  };
};
