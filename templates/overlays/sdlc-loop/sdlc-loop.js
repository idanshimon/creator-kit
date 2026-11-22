// Classic script: works beside an HTML file without a server or build step.
(() => {
  if (customElements.get('sdlc-loop')) return;
  const defaults = [
    ['Issue', 'What prompted the change?'], ['Triage', 'Clarify the scope and priority.'],
    ['Plan', 'Describe the intended approach.'], ['Implement', 'Explore the proposed change.'],
    ['Checks', 'Examine the checks and their results.'], ['Review', 'Consider feedback and open questions.'],
    ['Merge', 'Discuss integration into the target branch.'], ['Resolved', 'What evidence would demonstrate resolution?']
  ].map(([label, detail]) => ({id: label.toLowerCase(), label, detail}));

  class SdlcLoop extends HTMLElement {
    #stages = [];
    #active = null;
    #dial; #status; #toggle; #inspector; #picker; #detail; #count;

    constructor() {
      super();
      const root = this.attachShadow({mode:'open'});
      root.innerHTML = `<style>
        :host {display:block;position:absolute;left:.75rem;top:.75rem;z-index:2;width:min(11rem,calc(100% - 1.5rem));color-scheme:light dark;font:normal 14px/1.4 system-ui,sans-serif;text-align:left}
        :host([theme=light]) {color-scheme:light} :host([theme=dark]) {color-scheme:dark}
        * {box-sizing:border-box} .panel {--paper:light-dark(#fafaf7,#19212a);--ink:light-dark(#19212a,#eef2f6);--line:light-dark(#77828c,#95a2ae);--accent:light-dark(#07559e,#a9d2ff);background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:.65rem;overflow-wrap:anywhere}
        header {font-weight:650;font-size:.75rem;letter-spacing:.07em;text-transform:uppercase}
        .dial {width:min(7.8rem,100%);aspect-ratio:1;margin:.25rem auto;position:relative;display:grid;place-items:center}
        .dial::before {content:'';position:absolute;inset:12%;border:1px solid var(--line);border-radius:50%}
        .count {font:600 .85rem ui-monospace,monospace}
        button,select {font:inherit;color:inherit;background:var(--paper);cursor:pointer} button:focus-visible,select:focus-visible {outline:3px solid var(--accent);outline-offset:2px}
        .node {position:absolute;transform:translate(-50%,-50%);width:1.75rem;height:1.75rem;min-width:24px;min-height:24px;padding:0;border-radius:50%;border:1px solid var(--line);font-size:.8rem;transition:background-color .12s}
        .node:hover {border-color:var(--accent)} .node[aria-current] {border:3px double var(--paper);background:var(--accent);color:var(--paper);font-weight:bold}
        .status {font-size:1.2rem;line-height:1.25;font-weight:750;margin:.15rem 0 .4rem} .toggle {margin-top:.35rem;width:100%;min-height:32px;border:1px solid var(--line);border-radius:4px}
        .inspector {border-top:1px solid var(--line);padding-top:.6rem;margin-top:.6rem} select {width:100%;min-height:32px} .inspection {margin:.5rem 0 0}
        @media(prefers-reduced-motion:reduce){.node {transition:none}}
      </style><section class="panel" aria-label="SDLC stage map"><header>Current stage</header>
      <div class="status" role="status"></div>
      <div class="dial" role="group" aria-label="Inspect a stage"><span class="count" aria-hidden="true"></span></div>
      <button class="toggle" aria-controls="inspector" aria-expanded="false">Inspect stages</button>
      <div id="inspector" class="inspector" hidden><label>Stage to inspect<select></select></label><p class="inspection" role="status"></p></div></section>`;
      this.#dial = root.querySelector('.dial'); this.#count = root.querySelector('.count');
      this.#status = root.querySelector('.status'); this.#toggle = root.querySelector('.toggle');
      this.#inspector = root.querySelector('.inspector'); this.#picker = root.querySelector('select');
      this.#detail = root.querySelector('.inspection');
      this.#toggle.onclick = () => this.#inspector.hidden ? this.#inspect(this.#active ?? this.#stages[0].id) : this.#close();
      this.#picker.onchange = () => this.#describe();
      this.#picker.onkeydown = e => {
        if (e.key !== 'Home' && e.key !== 'End') return;
        e.preventDefault();
        this.#picker.selectedIndex = e.key === 'Home' ? 0 : this.#stages.length - 1;
        this.#describe();
      };
      root.addEventListener('keydown', e => {
        if (e.key === 'Escape' && !this.#inspector.hidden) { e.stopPropagation(); this.#close(); this.#toggle.focus(); }
      });
      // Adopt property assignments made before custom element registration.
      const initial = Object.hasOwn(this,'stages') ? this.stages : defaults;
      delete this.stages;
      this.stages = initial;
    }

    get stages() { return this.#stages.map(s => ({...s})); }
    set stages(value) {
      if (!Array.isArray(value) || !value.length) throw new TypeError('Expected a non-empty stages array');
      const ids = new Set();
      const stages = Array.from(value, s => {
        if (!s || typeof s.id !== 'string' || !s.id.trim() || ids.has(s.id) ||
            typeof s.label !== 'string' || !s.label.trim() || typeof s.detail !== 'string') {
          throw new TypeError('Stages require unique non-empty string ids, labels and string detail');
        }
        ids.add(s.id); return {id:s.id, label:s.label, detail:s.detail};
      });
      this.#stages = stages;
      if (!ids.has(this.#active)) this.#active = null;
      this.#close(); this.#dial.replaceChildren(this.#count); this.#picker.replaceChildren();
      stages.forEach(({id,label}, i) => {
        const name = `${i+1}. ${label}`;
        this.#picker.add(new Option(name,id));
        // Dense maps use the named picker instead of overlapping touch targets.
        if (stages.length > 8) return;
        const angle = 2*Math.PI*i/stages.length;
        const node = document.createElement('button'); node.className = 'node';
        node.textContent = i+1; node.dataset.id = id; node.title = name; node.setAttribute('aria-label',name);
        node.style.left = `${50 + 38*Math.sin(angle)}%`; node.style.top = `${50 - 38*Math.cos(angle)}%`;
        node.onclick = () => this.#inspect(id); this.#dial.append(node);
      });
      this.#renderPosition();
    }

    setStage(id) {
      if (id === this.#active) return;
      if (id !== null && !this.#stages.some(s => s.id === id)) throw new RangeError('Unknown stage: '+String(id));
      this.#active = id; this.#renderPosition();
    }
    #renderPosition() {
      const i = this.#stages.findIndex(s=>s.id === this.#active);
      const position = `${i+1}/${this.#stages.length}`;
      this.#count.textContent = i < 0 ? 'SDLC' : position;
      this.#status.textContent = i < 0 ? 'Overview' : this.#stages[i].label;
      for (const node of this.#dial.querySelectorAll('button')) {
        if (node.dataset.id === this.#active) node.setAttribute('aria-current','step');
        else node.removeAttribute('aria-current');
      }
    }
    #inspect(id) {
      this.#inspector.hidden = false; this.#toggle.setAttribute('aria-expanded','true');
      this.#toggle.textContent = 'Close inspector'; this.#picker.value = id; this.#describe(); this.#picker.focus();
    }
    #describe() {
      const {label,detail} = this.#stages[this.#picker.selectedIndex];
      this.#detail.textContent = `Inspecting: ${label}. ${detail}`;
    }
    #close() {
      this.#inspector.hidden = true; this.#toggle.setAttribute('aria-expanded','false');
      this.#toggle.textContent = 'Inspect stages';
    }
  }
  customElements.define('sdlc-loop', SdlcLoop);
})();
