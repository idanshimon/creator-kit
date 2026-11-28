/* terminal: animated CLI / code demo reel.
 * Dark terminal chrome (traffic-light dots + window title), typing command prompt,
 * output lines revealing with status/accent pills (PASS, OK, 0.0s), optional punchline beat.
 * beat: {cmd?, prompt?, lines?: [str | {text, status?, tone?}], caption?, text?, sub?} */
window.R = window.R || { templates: {} };
R.templates.terminal = (S, root, R) => {
  const u = S.u, box = R.safeBox, all = R.content;
  const termBeats = all.filter(b => b.cmd || (b.lines && b.lines.length));
  const punchBeats = all.filter(b => !b.cmd && !(b.lines && b.lines.length) && b.text);
  const hasCaps = termBeats.some(b => b.caption || b.text);

  /* Top header (kicker + title) */
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
  const capH = hasCaps ? Math.min(box.h * .15, 160 * u) : 0;
  const winH = box.h - headH - capH - (hasCaps ? 28 * u : 0);

  /* Terminal window card */
  const win = R.css(R.el('div', '', root), {
    position: 'absolute', left: 0, right: 0, top: headH, height: winH,
    borderRadius: 24 * u, overflow: 'hidden', background: '#0b0d13',
    border: '1px solid rgba(255,255,255,.13)',
    boxShadow: `0 ${36 * u}px ${100 * u}px rgba(0,0,0,.6), 0 0 0 1px rgba(255,255,255,.04) inset`,
    display: 'flex', flexDirection: 'column', opacity: 0,
  });

  /* Window chrome bar */
  const chromeH = Math.round(62 * u);
  const chrome = R.css(R.el('div', '', win), {
    height: chromeH, flex: 'none', background: '#131722',
    borderBottom: '1px solid rgba(255,255,255,.08)',
    padding: `0 ${26 * u}px`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 * u,
  });
  const dots = R.css(R.el('div', '', chrome), { display: 'flex', alignItems: 'center', gap: 10 * u, flex: 'none' });
  ['#ff5f56', '#ffbd2e', '#27c93f'].forEach(col =>
    R.css(R.el('span', '', dots), { width: 14 * u, height: 14 * u, borderRadius: '50%', background: col, display: 'block' })
  );
  const winTitle = S.windowTitle || (S.screen && S.screen.title) || 'zsh — creator-kit';
  R.css(R.el('div', 'mono', chrome, R.esc(winTitle)), {
    fontSize: 22 * u, color: '#b4bcd0', letterSpacing: '.02em',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'center', flex: 1,
  });
  const stepPill = R.css(R.el('div', 'mono', chrome, `1/${Math.max(1, termBeats.length)}`), {
    fontSize: 18 * u, fontWeight: 700, color: S.hi,
    background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.1)',
    padding: `${5 * u}px ${12 * u}px`, borderRadius: 99, flex: 'none',
  });

  /* Terminal body */
  const bodyWrap = R.css(R.el('div', 'mono', win), {
    flex: 1, minHeight: 0, overflow: 'hidden',
    padding: `${28 * u}px ${30 * u}px`,
    display: 'flex', flexDirection: 'column', justifyContent: 'flex-start',
  });
  const bodyInner = R.css(R.el('div', '', bodyWrap), {
    display: 'flex', flexDirection: 'column', gap: `${22 * u}px`, width: '100%',
  });

  const pillTone = (status, tone) => {
    const t = tone || (/^(PASS|OK|DONE|✓)/i.test(status) ? 'ok'
      : /^(FAIL|ERR|✕)/i.test(status) ? 'err'
      : /^(WARN)/i.test(status) ? 'warn' : 'accent');
    if (t === 'ok') return { bg: 'rgba(34,197,94,.16)', fg: '#4ade80', bd: 'rgba(74,222,128,.38)' };
    if (t === 'err') return { bg: 'rgba(255,82,99,.18)', fg: '#ff6b7a', bd: 'rgba(255,107,122,.4)' };
    if (t === 'warn') return { bg: 'rgba(245,158,11,.18)', fg: '#fbbf24', bd: 'rgba(251,191,36,.4)' };
    return { bg: 'rgba(255,255,255,.08)', fg: S.hi, bd: 'rgba(255,255,255,.2)' };
  };

  const blocks = termBeats.map((b, idx) => {
    const blk = R.css(R.el('div', '', bodyInner), {
      display: 'flex', flexDirection: 'column', gap: '.45em',
      paddingTop: idx > 0 ? '.35em' : 0,
      borderTop: idx > 0 ? '1px solid rgba(255,255,255,.06)' : 'none',
    });
    let cmdRow = null, cmdText = null, cursor = null;
    if (b.cmd) {
      cmdRow = R.css(R.el('div', '', blk), {
        display: 'flex', alignItems: 'flex-start', gap: '.5em', lineHeight: 1.4,
      });
      R.css(R.el('span', '', cmdRow, R.esc(b.prompt || '$')), {
        color: S.hi, fontWeight: 700, flex: 'none',
      });
      const cmdWrap = R.css(R.el('span', '', cmdRow), {
        color: '#f8fafc', fontWeight: 600, overflowWrap: 'anywhere', whiteSpace: 'pre-wrap', flex: 1,
      });
      cmdText = R.el('span', '', cmdWrap, R.esc(b.cmd));
      cursor = R.css(R.el('span', '', cmdWrap, '▍'), { color: S.hi, marginLeft: '2px' });
    }
    const lineEls = (b.lines || []).map(item => {
      const obj = typeof item === 'string' ? { text: item } : item;
      const row = R.css(R.el('div', '', blk), {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1em',
        lineHeight: 1.4, paddingLeft: '.25em',
      });
      const raw = String(obj.text || '');
      const textCol = obj.tone === 'ok' || /^✓/.test(raw) ? '#a7f3d0'
        : obj.tone === 'err' || /^(✕|FAIL|ERR)/i.test(raw) ? '#fda4af'
        : obj.tone === 'accent' ? '#e2e8f0'
        : '#d4d9e8';
      const txt = R.css(R.el('span', '', row, R.markup(raw)), {
        color: textCol, flex: 1, minWidth: 0, overflowWrap: 'break-word', whiteSpace: 'pre-wrap',
      });
      let badge = null;
      if (obj.status) {
        const c = pillTone(obj.status, obj.tone);
        badge = R.css(R.el('span', '', row, R.esc(obj.status)), {
          flex: 'none', fontSize: '.78em', fontWeight: 700, letterSpacing: '.06em',
          padding: '.18em .62em', borderRadius: 99,
          background: c.bg, color: c.fg, border: `1px solid ${c.bd}`,
        });
      }
      return { row, txt, badge };
    });
    return { b, blk, cmdRow, cmdText, cursor, lineEls };
  });

  /* Fit font size so all terminal lines fit inside bodyWrap with zero clipping */
  const availH = winH - chromeH - 56 * u;
  const availW = box.w - 60 * u;
  let fs = 27 * u;
  bodyInner.style.fontSize = fs + 'px';
  for (let i = 0; i < 60 && fs > 15 * u; i++) {
    if (bodyInner.scrollHeight <= availH + 1 && bodyInner.scrollWidth <= availW + 1) break;
    fs *= 0.94;
    bodyInner.style.fontSize = fs + 'px';
  }

  /* Optional captions under terminal window */
  const caps = termBeats.filter(b => b.caption || b.text).map(b => {
    const c = R.css(R.el('div', '', root), {
      position: 'absolute', left: 0, right: 0, bottom: 0, height: capH,
      display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0,
    });
    const inner = R.css(R.el('div', 'display', c, R.markup(b.caption || b.text)), { width: '100%', textAlign: 'center' });
    R.fit(inner, 54 * u, 28 * u, capH);
    return { b, c };
  });

  /* Optional punchline beats (centered bold typography after terminal) */
  const punches = punchBeats.map(b => {
    const wrap = R.css(R.el('div', 'fill center', root), { flexDirection: 'column', gap: 24 * u, opacity: 0 });
    if (b.tag) R.css(R.el('div', 'pill mono', wrap, R.esc(b.tag)), { background: S.hi, color: S.onhi, fontSize: 26 * u, letterSpacing: '.1em', textTransform: 'uppercase' });
    const h = R.css(R.el('div', 'display', wrap, R.markup(b.text)), { width: '94%' });
    const sub = b.sub ? R.css(R.el('div', 'body', wrap, R.markup(b.sub)), { width: '88%' }) : null;
    R.fit(h, 96 * u, 42 * u, box.h * .42);
    if (sub) R.fit(sub, 42 * u, 24 * u, box.h * .2);
    return { b, wrap, h, sub };
  });

  const T0 = termBeats.length ? termBeats[0].start : 0;
  const TLastTerm = termBeats.length ? termBeats[termBeats.length - 1] : null;

  return t => {
    /* Terminal window visibility: stays up across all terminal beats, fades out before punchline/end */
    let winVis = 0;
    if (TLastTerm) {
      const inn = R.ease.out5(R.seg(t, T0, T0 + .45));
      const out = TLastTerm.last ? 1 : 1 - R.ease.in(R.seg(t, TLastTerm.end - .3, TLastTerm.end));
      winVis = inn * out;
      win.style.opacity = winVis;
      win.style.transform = `translateY(${(1 - inn) * 36 * u}px) scale(${.96 + .04 * inn})`;
      if (headWrap) headWrap.style.opacity = winVis;
    }

    /* Active terminal step counter */
    let activeStep = 1;
    termBeats.forEach((b, k) => { if (t >= b.start) activeStep = k + 1; });
    stepPill.textContent = `${activeStep}/${Math.max(1, termBeats.length)}`;

    /* Animate each command block */
    blocks.forEach(({ b, blk, cmdRow, cmdText, cursor, lineEls }, idx) => {
      const started = t >= b.start;
      const dur = Math.max(.4, b.end - b.start);
      const isPast = idx < termBeats.length - 1 && t >= termBeats[idx + 1].start;
      blk.style.opacity = started ? (isPast ? .82 : 1) : 0;

      const typeEnd = b.cmd ? b.start + Math.min(dur * .42, Math.max(.45, b.cmd.length * .022)) : b.start;
      if (b.cmd && cmdText) {
        const tp = R.seg(t, b.start + .06, typeEnd);
        const chars = Math.round(b.cmd.length * tp);
        cmdText.textContent = b.cmd.slice(0, chars);
        if (cursor) {
          const typing = started && tp < 1;
          const idleActive = !isPast && started && t < b.end;
          cursor.style.opacity = typing ? 1 : (idleActive ? (Math.sin(t * 7) > 0 ? .85 : .15) : 0);
        }
      }

      const nLines = lineEls.length;
      const outStart = b.cmd ? typeEnd + .12 : b.start + .08;
      const outSpan = Math.max(.25, (b.end - .25) - outStart);
      lineEls.forEach(({ row, badge }, li) => {
        const la = outStart + (nLines > 1 ? (outSpan * .72) * li / (nLines - 1) : 0);
        const lp = R.ease.out(R.seg(t, la, la + .24));
        row.style.opacity = started ? lp : 0;
        row.style.transform = `translateY(${(1 - lp) * 12 * u}px)`;
        if (badge) {
          const bp = R.ease.back(R.seg(t, la + .08, la + .34));
          badge.style.transform = `scale(${.75 + .25 * bp})`;
        }
      });
    });

    /* Captions */
    caps.forEach(({ b, c }) => {
      const L = R.life(t, b, .28, .22);
      c.style.opacity = t >= b.start ? L.v : 0;
      c.style.transform = `translateY(${(1 - L.in) * 20 * u}px)`;
    });

    /* Punchline beats */
    punches.forEach(({ b, wrap, h, sub }) => {
      const L = R.life(t, b, .38, .25);
      wrap.style.opacity = t >= b.start ? L.v : 0;
      h.style.transform = `translateY(${(1 - L.in) * 40 * u}px) scale(${.96 + .04 * L.in})`;
      if (sub) sub.style.opacity = R.ease.out(R.seg(t, b.start + .22, b.start + .6));
    });
  };
};
