/* versus: "Old Way vs New Way" / "Myth vs Reality" stacked comparison cards
 * with animated ✕ / ✓ verdict badges, crisp contrast, and takeaway beat.
 * beat: {old: {label?, title?, text?, lines?}, new: {label?, title?, text?, lines?}}
 *   (also accepts myth/reality aliases) OR takeaway beat: {tag?, text, sub?}. */
window.R = window.R || { templates: {} };
R.templates.versus = (S, root, R) => {
  const u = S.u, box = R.safeBox, all = R.content;
  const wide = box.w > box.h * 1.15;

  const isPair = b => (b.old && b.new) || (b.myth && b.reality);
  const pairBeats = all.filter(isPair);
  const takeBeats = all.filter(b => !isPair(b) && b.text);

  /* Optional top header */
  const headWrap = (S.kicker || S.title)
    ? R.css(R.el('div', '', root), { position: 'absolute', left: 0, right: 0, top: 0, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 10 * u })
    : null;
  if (headWrap) {
    if (S.kicker) R.css(R.el('div', 'eyebrow', headWrap, R.esc(S.kicker)), { fontSize: 24 * u, color: S.hi });
    if (S.title) {
      const h = R.css(R.el('div', 'display', headWrap, R.markup(S.title)), { width: '100%' });
      R.fit(h, 66 * u, 32 * u, box.h * .14);
    }
  }
  const headH = headWrap ? headWrap.offsetHeight + 34 * u : 0;
  const areaH = box.h - headH;

  /* Build each paired comparison beat */
  const gap = 46 * u;
  const cardW = wide ? (box.w - gap) / 2 : box.w;
  const cardH = wide ? areaH : (areaH - gap) / 2;

  const buildCard = (parent, side, isGood, defaultLabel) => {
    const padX = Math.round(38 * u), padY = Math.round(30 * u);
    const card = R.css(R.el('div', '', parent), {
      position: 'absolute', width: cardW, height: cardH,
      borderRadius: 28 * u, padding: `${padY}px ${padX}px`,
      display: 'flex', flexDirection: 'column', gap: 18 * u, overflow: 'hidden',
      background: isGood
        ? `linear-gradient(155deg, ${S.pal.raised}, ${S.pal.panel})`
        : S.pal.surface,
      border: isGood
        ? `${2.5 * u}px solid ${S.hi}`
        : `${1.5 * u}px solid rgba(255,82,99,.42)`,
      boxShadow: isGood
        ? `0 ${28 * u}px ${80 * u}px rgba(0,0,0,.55), 0 0 ${48 * u}px ${S.hi}22`
        : `0 ${20 * u}px ${60 * u}px rgba(0,0,0,.4)`,
      opacity: 0,
    });

    /* Top row: label pill + animated verdict badge */
    const top = R.css(R.el('div', '', card), {
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 * u, flex: 'none',
    });
    const label = side.label || defaultLabel;
    R.css(R.el('div', 'pill mono', top, R.esc(label)), {
      fontSize: 22 * u, fontWeight: 700, letterSpacing: '.12em', textTransform: 'uppercase',
      background: isGood ? S.hi : 'rgba(255,82,99,.22)',
      color: isGood ? S.onhi : '#ff7b89',
      border: isGood ? 'none' : '1px solid rgba(255,107,122,.48)',
    });

    const badgeSize = Math.round(54 * u);
    const badge = R.css(R.el('div', 'mono', top, isGood ? '✓' : '✕'), {
      width: badgeSize, height: badgeSize, borderRadius: '50%', flex: 'none',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 30 * u, fontWeight: 800,
      background: isGood ? '#22c55e' : S.pal.critical,
      color: isGood ? '#041a0d' : '#ffffff',
      boxShadow: isGood ? `0 0 ${28 * u}px rgba(34,197,94,.45)` : `0 0 ${28 * u}px rgba(255,82,99,.45)`,
      transform: 'scale(0)', opacity: 0,
    });

    /* Content wrapper (flex: 1) holds shrink-wrapped col so R.fit measures true text height */
    const bodyWrap = R.css(R.el('div', '', card), {
      flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', overflow: 'hidden',
    });
    const body = R.css(R.el('div', '', bodyWrap), {
      width: '100%', display: 'flex', flexDirection: 'column', gap: '.42em',
    });
    const headline = side.title || side.text;
    if (headline) {
      R.css(R.el('div', 'display', body, R.markup(headline)), {
        fontSize: '1.26em', lineHeight: 1.12, color: isGood ? S.pal.ink : '#d4d8e4',
      });
    }
    const lineRows = (side.lines || []).map(l => {
      const row = R.css(R.el('div', '', body), {
        display: 'flex', alignItems: 'baseline', gap: '.5em', lineHeight: 1.26,
        color: isGood ? S.pal.ink : '#bcc2d4',
      });
      R.css(R.el('span', 'mono', row, isGood ? '✓' : '✕'), {
        color: isGood ? '#4ade80' : '#ff6b7a', fontWeight: 800, flex: 'none', fontSize: '.92em',
      });
      R.el('span', '', row, R.markup(l));
      return row;
    });

    const availH = cardH - padY * 2 - badgeSize - 32 * u;
    R.fit(body, 32 * u, 20 * u, availH);
    return { card, badge, lineRows };
  };

  const pairs = pairBeats.map(b => {
    const wrap = R.css(R.el('div', '', root), {
      position: 'absolute', left: 0, right: 0, top: headH, height: areaH, opacity: 0,
    });
    const badSide = b.old || b.myth;
    const goodSide = b.new || b.reality;
    const badDef = b.myth ? 'Myth' : 'Old Way';
    const goodDef = b.reality ? 'Reality' : 'New Way';

    const topCard = buildCard(wrap, badSide, false, badDef);
    R.css(topCard.card, { left: 0, top: 0 });

    const botCard = buildCard(wrap, goodSide, true, goodDef);
    R.css(botCard.card, wide ? { left: cardW + gap, top: 0 } : { left: 0, top: cardH + gap });

    const vsSize = Math.round(74 * u);
    const vs = R.css(R.el('div', 'mono', wrap, 'VS'), {
      position: 'absolute',
      left: wide ? cardW + gap / 2 - vsSize / 2 : box.w / 2 - vsSize / 2,
      top: wide ? areaH / 2 - vsSize / 2 : cardH + gap / 2 - vsSize / 2,
      width: vsSize, height: vsSize, borderRadius: '50%', zIndex: 4,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 26 * u, fontWeight: 800, letterSpacing: '.06em',
      background: S.pal.bg, color: S.hi,
      border: `${2.5 * u}px solid ${S.hi}`,
      boxShadow: `0 ${10 * u}px ${36 * u}px rgba(0,0,0,.65)`,
      opacity: 0, transform: 'scale(0.5)',
    });

    return { b, wrap, topCard, botCard, vs };
  });

  /* Build takeaway beats */
  const takes = takeBeats.map(b => {
    const wrap = R.css(R.el('div', 'fill center', root), { flexDirection: 'column', gap: 28 * u, opacity: 0 });
    const icon = R.css(R.el('div', 'mono', wrap, '✓'), {
      width: 104 * u, height: 104 * u, borderRadius: '50%',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 54 * u, fontWeight: 800,
      background: '#22c55e', color: '#041a0d',
      boxShadow: `0 0 ${60 * u}px rgba(34,197,94,.45)`,
    });
    if (b.tag) {
      R.css(R.el('div', 'pill mono', wrap, R.esc(b.tag)), {
        background: S.hi, color: S.onhi, fontSize: 25 * u, letterSpacing: '.12em', textTransform: 'uppercase',
      });
    }
    const h = R.css(R.el('div', 'display', wrap, R.markup(b.text)), { width: '94%' });
    const sub = b.sub ? R.css(R.el('div', 'body', wrap, R.markup(b.sub)), { width: '88%' }) : null;
    R.fit(h, 92 * u, 40 * u, box.h * .38);
    if (sub) R.fit(sub, 42 * u, 24 * u, box.h * .18);
    return { b, wrap, icon, h, sub };
  });

  const firstPair = pairBeats[0];
  const lastPair = pairBeats[pairBeats.length - 1];

  return t => {
    /* Header stays visible during comparison beats */
    if (headWrap && firstPair && lastPair) {
      const hin = R.ease.out(R.seg(t, firstPair.start, firstPair.start + .4));
      const hout = lastPair.last ? 1 : 1 - R.ease.in(R.seg(t, lastPair.end - .28, lastPair.end));
      headWrap.style.opacity = hin * hout;
    }

    /* Animate each comparison pair */
    pairs.forEach(({ b, wrap, topCard, botCard, vs }) => {
      const L = R.life(t, b, .15, .28);
      const vis = t >= b.start - .01 && L.out > 0;
      wrap.style.opacity = vis ? L.out : 0;
      if (!vis) return;

      const dur = Math.max(1.2, b.end - b.start);
      const tOldIn = b.start;
      const tVs = b.start + dur * .30;
      const tNewIn = b.start + dur * .36;

      /* Old / Myth card enters first */
      const pOld = R.ease.out5(R.seg(t, tOldIn, tOldIn + .48));
      const pNew = R.ease.out5(R.seg(t, tNewIn, tNewIn + .52));
      const dimOld = 1 - .14 * pNew;
      topCard.card.style.opacity = pOld * dimOld;
      topCard.card.style.transform = `translateY(${(1 - pOld) * 32 * u}px) scale(${(.96 + .04 * pOld) * (1 - .015 * pNew)})`;

      /* Animated ✕ badge */
      const bOld = R.ease.back(R.seg(t, tOldIn + .22, tOldIn + .62));
      topCard.badge.style.opacity = R.seg(t, tOldIn + .22, tOldIn + .42);
      topCard.badge.style.transform = `scale(${.4 + .6 * bOld}) rotate(${(1 - bOld) * -20}deg)`;

      /* VS badge pops in between */
      const pVs = R.ease.back(R.seg(t, tVs, tVs + .38));
      vs.style.opacity = R.seg(t, tVs, tVs + .2);
      vs.style.transform = `scale(${.5 + .5 * pVs})`;

      /* New / Reality card enters second */
      botCard.card.style.opacity = pNew;
      botCard.card.style.transform = `translateY(${(1 - pNew) * 40 * u}px) scale(${.95 + .05 * pNew})`;

      /* Animated ✓ badge */
      const bNew = R.ease.back(R.seg(t, tNewIn + .24, tNewIn + .66));
      botCard.badge.style.opacity = R.seg(t, tNewIn + .24, tNewIn + .44);
      botCard.badge.style.transform = `scale(${.4 + .6 * bNew}) rotate(${(1 - bNew) * 18}deg)`;
    });

    /* Animate takeaway beats */
    takes.forEach(({ b, wrap, icon, h, sub }) => {
      const L = R.life(t, b, .4, .28);
      wrap.style.opacity = t >= b.start ? L.v : 0;
      const p = R.ease.back(R.seg(t, b.start, b.start + .55));
      icon.style.transform = `scale(${.4 + .6 * p})`;
      h.style.transform = `translateY(${(1 - L.in) * 44 * u}px)`;
      if (sub) sub.style.opacity = R.ease.out(R.seg(t, b.start + .25, b.start + .65));
    });
  };
};
