/* stat: number reveal. beat: {value: "93%" | "$1.2M" | "10x", label, text}
 * Counts up with expo ease; percentages get a ring, others an underline sweep. */
window.R = window.R || { templates: {} };
R.templates.stat = (S, root, R) => {
  const u = S.u, box = R.safeBox;
  const parse = v => {
    const m = String(v).match(/^([^0-9-]*)(-?[0-9][0-9,]*\.?[0-9]*)(.*)$/);
    if (!m) return { pre: '', n: null, post: String(v), dec: 0 };
    const num = m[2].replace(/,/g, '');
    return { pre: m[1], n: parseFloat(num), post: m[3], dec: (num.split('.')[1] || '').length, comma: m[2].includes(',') };
  };
  const fmt = (p, x) => { let s = x.toFixed(p.dec); if (p.comma) s = Number(s).toLocaleString('en-US', { minimumFractionDigits: p.dec, maximumFractionDigits: p.dec }); return p.pre + s + p.post; };
  const eyebrow = S.title ? R.css(R.el('div', 'eyebrow', root, R.esc(S.title)), { position: 'absolute', left: 0, right: 0, top: 0, textAlign: 'center', fontSize: 30 * u }) : null;
  const B = R.content.map(b => {
    const p = parse(b.value);
    const wrap = R.css(R.el('div', 'fill center', root), { flexDirection: 'column', opacity: 0 });
    const D = Math.min(box.w * .92, box.h * .48);
    const ringBox = R.css(R.el('div', '', wrap), { position: 'relative', width: D, height: p.post.trim() === '%' ? D : 'auto', display: 'flex', alignItems: 'center', justifyContent: 'center' });
    let ring = null;
    if (p.post.trim() === '%') {
      const sw = 22 * u, r = D / 2 - sw;
      ringBox.innerHTML = `<svg width="${D}" height="${D}" style="position:absolute;inset:0;transform:rotate(-90deg)"><circle cx="${D / 2}" cy="${D / 2}" r="${r}" fill="none" stroke="${S.pal.border}" stroke-width="${sw}"/><circle class="arc" cx="${D / 2}" cy="${D / 2}" r="${r}" fill="none" stroke="${S.hi}" stroke-width="${sw}" stroke-linecap="round" stroke-dasharray="${2 * Math.PI * r}" stroke-dashoffset="${2 * Math.PI * r}"/></svg>`;
      ring = { el: ringBox.querySelector('.arc'), c: 2 * Math.PI * r };
    }
    const num = R.css(R.el('div', 'display', ringBox, R.esc(b.value)), { position: 'relative', width: ring ? D * .74 : D, textAlign: 'center', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums', letterSpacing: '-.05em' });
    R.fit(num, (ring ? 230 : 300) * u, 60 * u, ring ? D * .5 : box.h * .3);
    const line = ring ? null : R.css(R.el('div', '', wrap), { height: 8 * u, width: D * .5, background: S.hi, borderRadius: 9, marginTop: 10 * u, transformOrigin: 'center' });
    const lab = R.css(R.el('div', 'display', wrap, R.markup(b.label || '')), { width: '100%', marginTop: 48 * u, textAlign: 'center' });
    R.fit(lab, 72 * u, 32 * u, box.h * .18);
    const sub = b.text ? R.css(R.el('div', 'body', wrap, R.markup(b.text)), { width: '92%', marginTop: 22 * u, textAlign: 'center' }) : null;
    if (sub) R.fit(sub, 40 * u, 24 * u, box.h * .14);
    return { b, p, wrap, num, ring, line, lab, sub };
  });
  return t => {
    if (eyebrow) eyebrow.style.opacity = R.ease.out(R.seg(t, 0, .5));
    B.forEach(({ b, p, wrap, num, ring, line, lab, sub }) => {
      const L = R.life(t, b, .3, .3);
      wrap.style.opacity = t >= b.start ? L.v : 0;
      wrap.style.transform = `scale(${.97 + .03 * L.in}) translateY(${-(1 - L.out) * 50 * u}px)`;
      const k = R.ease.expo(R.seg(t, b.start + .1, b.start + 1.4));
      if (p.n != null) num.textContent = fmt(p, p.n * k);
      if (ring) ring.el.setAttribute('stroke-dashoffset', ring.c * (1 - k * Math.min(1, p.n / 100)));
      if (line) line.style.transform = `scaleX(${R.ease.out(R.seg(t, b.start + .3, b.start + 1))})`;
      const q = R.ease.out(R.seg(t, b.start + .6, b.start + 1.1));
      lab.style.opacity = q; lab.style.transform = `translateY(${(1 - q) * 30 * u}px)`;
      if (sub) sub.style.opacity = R.ease.out(R.seg(t, b.start + .9, b.start + 1.4));
    });
  };
};
