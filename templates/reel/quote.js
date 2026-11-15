/* quote: quote card. beat: {text, author, role}. Words resolve from blur, *emphasis*
 * gets an accent underline sweep, author row lands last. */
window.R = window.R || { templates: {} };
R.templates.quote = (S, root, R) => {
  const u = S.u, box = R.safeBox;
  const B = R.content.map(b => {
    const wrap = R.css(R.el('div', 'fill', root), { display: 'flex', flexDirection: 'column', justifyContent: 'center', opacity: 0 });
    const mark = R.css(R.el('div', 'display', wrap, '“'), { fontSize: 260 * u, lineHeight: .7, height: 150 * u, color: S.hi, fontFamily: 'Georgia, "Times New Roman", serif' });
    const q = R.css(R.el('div', '', wrap), { width: '100%', fontWeight: 650, letterSpacing: '-.025em', lineHeight: 1.16, textWrap: 'balance' });
    const words = R.wordTimes(b, .25, .55).map(k => {
      const e = R.el('span', 'word', null, R.esc(k.w));
      if (k.hl) { e.style.color = S.hi; e.style.backgroundImage = `linear-gradient(${S.hi},${S.hi})`; e.style.backgroundRepeat = 'no-repeat'; e.style.backgroundPosition = '0 92%'; e.style.backgroundSize = '0% .05em'; }
      return { ...k, e };
    });
    words.forEach((k, i) => { q.appendChild(k.e); if (i < words.length - 1) q.appendChild(document.createTextNode(' ')); });
    const who = R.css(R.el('div', '', wrap), { display: 'flex', alignItems: 'center', gap: 28 * u, marginTop: 64 * u });
    const ini = String(b.author || '?').split(/\s+/).map(s => s[0]).join('').slice(0, 2).toUpperCase();
    R.css(R.el('div', 'mono', who, R.esc(ini)), { width: 96 * u, height: 96 * u, borderRadius: '50%', flex: 'none', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: `linear-gradient(135deg, ${S.hi}, ${S.hi2})`, color: S.onhi, fontWeight: 700, fontSize: 34 * u });
    const meta = R.el('div', '', who);
    R.css(R.el('div', '', meta, R.esc(b.author || '')), { fontWeight: 700, fontSize: 40 * u });
    if (b.role) R.css(R.el('div', 'body', meta, R.esc(b.role)), { fontSize: 30 * u, marginTop: 4 * u });
    R.fit(q, 96 * u, 40 * u, box.h - 150 * u - 220 * u);
    return { b, wrap, words, who };
  });
  return t => {
    B.forEach(({ b, wrap, words, who }) => {
      const L = R.life(t, b, .4, .3);
      wrap.style.opacity = t >= b.start ? L.v : 0;
      words.forEach(k => {
        const p = R.ease.out(R.seg(t, k.s, k.s + .35));
        k.e.style.opacity = .08 + .92 * p;
        k.e.style.filter = `blur(${(1 - p) * 10 * u}px)`;
        k.e.style.transform = `translateY(${(1 - p) * 14 * u}px)`;
        if (k.hl) k.e.style.backgroundSize = `${R.ease.inOut(R.seg(t, k.e_s = k.s + .3, k.s + .8)) * 100}% .05em`;
      });
      const w = R.ease.out(R.seg(t, b.start + (b.end - b.start) * .62, b.start + (b.end - b.start) * .62 + .5));
      who.style.opacity = w; who.style.transform = `translateY(${(1 - w) * 30 * u}px)`;
    });
  };
};
