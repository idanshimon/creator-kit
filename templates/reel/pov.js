/* pov: "POV:" text-on-screen story. Beat 0 is the premise; later beats stack as
 * caption labels (classic text-with-background look) that pop in and stay. */
window.R = window.R || { templates: {} };
R.templates.pov = (S, root, R) => {
  const u = S.u, box = R.safeBox;
  const col = R.css(R.el('div', '', root), { position: 'absolute', left: 0, right: 0, top: '50%', transform: 'translateY(-50%)',
    display: 'flex', flexDirection: 'column', alignItems: S.align === 'left' ? 'flex-start' : 'center', textAlign: S.align === 'left' ? 'left' : 'center' });
  const [head, ...rest] = R.content;
  const tag = String(head.tag || 'POV:');
  const h = R.css(R.el('div', 'display', col, `<span class="hl">${R.esc(tag)}</span> ${R.markup(head.text)}`), { width: '100%', fontSize: '1.45em', marginBottom: '.7em' });
  const items = rest.map(b => {
    const row = R.css(R.el('div', '', col), { marginTop: '.32em', maxWidth: '100%', textWrap: 'balance' });
    const lab = R.css(R.el('span', '', row, R.markup(b.text)), { background: S.pal.ink, color: S.pal.bg, fontWeight: 700, lineHeight: 1.42,
      padding: '.08em .38em', borderRadius: '.22em', boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone', letterSpacing: '-.01em' });
    if (lab.querySelector('.hl')) { lab.style.background = S.hi; lab.style.color = S.onhi; lab.querySelectorAll('.hl').forEach(e => { e.style.color = S.onhi; }); }
    return { b, row };
  });
  R.fit(col, 64 * u, 26 * u, box.h);
  return t => {
    const L = R.life(t, head, .45, .3);
    const last = R.content[R.content.length - 1];
    const out = last.last ? 1 : 1 - R.ease.in(R.seg(t, last.end - .3, last.end));
    col.style.opacity = out;
    h.style.opacity = L.in;
    h.style.transform = `translateY(${(1 - L.in) * 40 * u}px)`;
    items.forEach(({ b, row }) => {
      const p = R.seg(t, b.start, b.start + .32);
      row.style.opacity = R.ease.out(p);
      row.style.transform = `translateY(${(1 - R.ease.out(p)) * 24 * u}px) scale(${.94 + .06 * R.ease.back(p)})`;
    });
  };
};
