"""Domain-agnostic Mission Control cockpit generator & video renderer.

Turns a typed JSON specification of ANY governed agentic loop (sectors, severity
rings, 7-beat center dial, entity nodes, per-entity rule/model/human/system
watchers, persona lens, and step sequence) into:
  1. A self-contained, zero-CDN interactive HTML cockpit (`viewer.html`) with:
     - 2D orbital canvas (starfield backdrop, sector arcs, concentric severity
       rings, 7-beat agent hub, hex human-approval gate, clinical/ops beacon,
       selected-entity satellite watcher ring with live beams)
     - Left rail: Entity count + live tick, Viewing-As persona card, Cohort Mix
       severity bars, Search/filter + entity worklist
     - Top bar: Scope filter tabs (`All` + each sector), whole-cohort vs
       scoped critical counts, pending review badge, Light/Dark theme toggle
     - Right rail: Selected entity inspector (metric tiles + watcher list +
       human approval gate) and 7-beat loop trace
     - Full interactive zoom/pan, sector filtering, entity click, agent-core
       click, and deterministic `window.__ready` / `window.__advance(ms)` /
       `window.__done()` hooks for frame-exact MP4 recording via `showcase`.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

STAGES = ("critical", "concerning", "at-risk", "stable")
WATCHER_KINDS = ("rule", "model", "human", "system")
DEFAULT_BEATS = ["Change", "Notice", "Decide", "Approve", "Act", "Adapt", "Prove"]


PHONE_LIMITS = {
    "title_word": 12, "badge": 6, "banner": 26, "model": 14, "sector_label": 12,
    "entity_label": 32, "token": 28, "watcher_value": 16,
}


def lint_spec(norm: dict) -> list[str]:
    """Non-fatal authoring warnings learned from real renders: copy that overflows a 390px phone,
    and wording that hides meaning. The engine now wraps long text, but short copy still reads better."""
    L, out = PHONE_LIMITS, []
    for w in norm["title"].split():
        if len(w) > L["title_word"]:
            out.append(f"title word '{w}' is {len(w)} chars; long single words cannot wrap in the top bar on phones")
    for key, lim in (("badge", L["badge"]), ("banner", L["banner"])):
        if len(norm[key]) > lim:
            out.append(f"{key} is {len(norm[key])} chars (keep <= {lim}); it shares the phone top bar")
    if len(norm["agent"]["model"]) > L["model"]:
        out.append(f"agent.model '{norm['agent']['model']}' is long; put detail in status_line instead")
    for s in norm["sectors"]:
        if len(s["label"]) > L["sector_label"]:
            out.append(f"sector '{s['id']}' label is {len(s['label'])} chars; sector tabs share one row")
    for e in norm["entities"]:
        if len(e["label"]) > L["entity_label"]:
            out.append(f"entity {e['id']} label is {len(e['label'])} chars (keep <= {L['entity_label']}; detail goes in summary)")
        texts = [e["summary"], e["draft"]] + [w["line"] for w in e["watchers"]] + [str(v) for v in e["metrics"].values()]
        for t in texts:
            if "http://" in t or "https://" in t:
                out.append(f"entity {e['id']} text contains a URL; link evidence elsewhere, show a short label")
                break
            long = [tok for tok in t.split() if len(tok) > L["token"]]
            if long:
                out.append(f"entity {e['id']} has an unbroken token '{long[0][:40]}'; shorten paths/ids")
                break
        if e["stage"] == "critical" and not (e.get("detail") and (e["detail"]["why_you"] or e["detail"]["decision"])):
            out.append(f"entity {e['id']} is critical but has no detail.why_you / detail.decision; the owner cannot tell what to decide")
        for w in e["watchers"]:
            if len(w["value"]) > L["watcher_value"]:
                out.append(f"entity {e['id']} watcher {w['key']} value '{w['value']}' is long; chips sit on the map")
            if w["value"].lower() in ("unleveled", "unknown", "n/a", "none set"):
                out.append(f"entity {e['id']} watcher {w['key']} value '{w['value']}' hides the reason; say what is missing or who it waits for")
    return out


def _url(u) -> str | None:
    u = str(u or "").strip()
    return u if u.startswith(("https://", "http://")) and not any(c in u for c in ' "<>') else None


def _links(raw, where: str) -> list[dict]:
    out = []
    for i, l in enumerate(raw or []):
        if not isinstance(l, dict) or not str(l.get("label") or "").strip():
            raise ValueError(f"{where} link {i} requires label")
        out.append({"label": str(l["label"]).strip(), "url": _url(l.get("url"))})
    return out


def _detail(raw, where: str) -> dict | None:
    """Optional click-through detail. Everything is plain text (escaped at render); URLs must be http(s)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{where}.detail must be an object")
    d = {"title": str(raw.get("title") or "").strip(), "why_you": str(raw.get("why_you") or "").strip(), "sections": [], "evidence": _links(raw.get("evidence"), where),
         "timeline": [], "decision": None, "text": str(raw.get("text") or "").strip(), "url": _url(raw.get("url"))}
    for i, sec in enumerate(raw.get("sections") or []):
        if not isinstance(sec, dict) or not str(sec.get("title") or "").strip():
            raise ValueError(f"{where}.detail section {i} requires title")
        items = [str(x).strip() for x in (sec.get("items") or []) if str(x).strip()]
        d["sections"].append({"title": str(sec["title"]).strip(), "text": str(sec.get("text") or "").strip(), "items": items})
    for i, ev in enumerate(raw.get("timeline") or []):
        if not isinstance(ev, dict) or not str(ev.get("text") or "").strip():
            raise ValueError(f"{where}.detail timeline {i} requires text")
        d["timeline"].append({"t": str(ev.get("t") or "").strip(), "text": str(ev["text"]).strip(), "url": _url(ev.get("url"))})
    dec = raw.get("decision")
    if dec is not None:
        if not isinstance(dec, dict) or not str(dec.get("question") or "").strip():
            raise ValueError(f"{where}.detail.decision requires question")
        opts = []
        for i, o in enumerate(dec.get("options") or []):
            if not isinstance(o, dict) or not str(o.get("label") or "").strip():
                raise ValueError(f"{where}.detail.decision option {i} requires label")
            val = str(o.get("value") or "").strip()
            opts.append({"label": str(o["label"]).strip(), "effect": str(o.get("effect") or "").strip(),
                         "url": _url(o.get("url")), "recommended": bool(o.get("recommended")),
                         "value": val if re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", val) else "",
                         "needs_note": bool(o.get("needs_note"))})
        ep = str(dec.get("endpoint") or "").strip()
        d["decision"] = {"question": str(dec["question"]).strip(), "options": opts,
                         "how": str(dec.get("how") or "").strip(), "url": _url(dec.get("url")),
                         # same-origin POST target that records the answer (the host authenticates the owner)
                         "endpoint": ep if re.fullmatch(r"/[A-Za-z0-9/_-]{1,80}", ep) else None}
    return d


def _brief(raw, entity_ids) -> dict | None:
    """Optional top strip for briefings: one lead line (e.g. a warning) + up to 8 labelled cards.
    A card with `entity` opens that entity's detail sheet."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("spec.brief must be an object")
    items = raw.get("items") or []
    if not isinstance(items, list) or len(items) > 8:
        raise ValueError("spec.brief.items must be a list of at most 8 items")
    out = []
    for i, it in enumerate(items):
        if not isinstance(it, dict) or not str(it.get("label") or "").strip():
            raise ValueError(f"spec.brief item {i} requires label")
        ent = str(it.get("entity") or "").strip() or None
        if ent and ent not in entity_ids:
            raise ValueError(f"spec.brief item {i} references unknown entity '{ent}'")
        lines = it.get("lines") or []
        if not isinstance(lines, list):
            raise ValueError(f"spec.brief item {i} lines must be a list")
        out.append({"label": str(it["label"]).strip(), "text": str(it.get("text") or "").strip(),
                    "lines": [str(x).strip() for x in lines if str(x).strip()][:6],
                    "entity": ent, "tone": "warn" if it.get("tone") == "warn" else ""})
    return {"lead": str(raw.get("lead") or "").strip(), "items": out}


def validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise ValueError("Mission Control spec must be a JSON object")
    title = str(spec.get("title") or "").strip()
    if not title:
        raise ValueError("spec.title is required")
    subtitle = str(spec.get("subtitle") or "Connected trends, rule evidence and human decisions.").strip()
    badge = str(spec.get("badge") or "v3").strip()
    banner = str(spec.get("banner") or "Synthetic data only").strip()

    agent = spec.get("agent") or {}
    if not isinstance(agent, dict):
        raise ValueError("spec.agent must be an object")
    model_name = str(agent.get("model") or "gpt-5.4-mini").strip()
    beats = agent.get("beats") or list(DEFAULT_BEATS)
    if not isinstance(beats, list) or len(beats) < 3 or len(beats) > 10 or not all(isinstance(b, str) and b.strip() for b in beats):
        raise ValueError("spec.agent.beats must be a list of 3..10 non-empty step names")
    gate_beat = int(agent.get("gate_beat", 4))

    persona = spec.get("persona") or {}
    if not isinstance(persona, dict):
        raise ValueError("spec.persona must be an object")
    persona_norm = {
        "role": str(persona.get("role") or "Lead Operator — Operations").strip(),
        "question": str(persona.get("question") or "Which item in my scope needs my decision now, and is the change real?").strip(),
        "context": str(persona.get("context") or "Operational review · measure: minutes from threshold crossing to acknowledgement").strip(),
        "metric": str(persona.get("metric") or "Crossing → acknowledgement: not measured").strip(),
        "scope_label": str(persona.get("scope_label") or "my scope only").strip(),
    }

    sectors_raw = spec.get("sectors")
    if not isinstance(sectors_raw, list) or not (1 <= len(sectors_raw) <= 8):
        raise ValueError("spec.sectors must be a list of 1..8 sector objects")
    sectors = []
    sector_ids = set()
    for idx, s in enumerate(sectors_raw):
        if not isinstance(s, dict) or not str(s.get("id") or "").strip() or not str(s.get("label") or "").strip():
            raise ValueError(f"sector {idx} requires id and label")
        sid = str(s["id"]).strip()
        if sid in sector_ids:
            raise ValueError(f"duplicate sector id: {sid}")
        sector_ids.add(sid)
        sectors.append({
            "id": sid,
            "label": str(s["label"]).strip(),
            "faults": int(s.get("faults", 0)),
        })

    entities_raw = spec.get("entities")
    if not isinstance(entities_raw, list) or not (1 <= len(entities_raw) <= 200):
        raise ValueError("spec.entities must be a list of 1..200 entity objects")
    entities = []
    entity_ids = set()
    for idx, e in enumerate(entities_raw):
        if not isinstance(e, dict):
            raise ValueError(f"entity {idx} must be an object")
        eid = str(e.get("id") or "").strip()
        if not eid or eid in entity_ids:
            raise ValueError(f"entity {idx} requires a unique id")
        entity_ids.add(eid)
        sec = str(e.get("sector") or "").strip()
        if sec not in sector_ids:
            raise ValueError(f"entity {eid} references unknown sector '{sec}'")
        stage = str(e.get("stage") or "stable").strip().lower()
        if stage not in STAGES:
            raise ValueError(f"entity {eid} stage must be one of {STAGES}")
        score = float(e.get("score", 20.0))
        watchers_raw = e.get("watchers") or []
        if not isinstance(watchers_raw, list):
            raise ValueError(f"entity {eid} watchers must be a list")
        watchers = []
        for widx, w in enumerate(watchers_raw):
            if not isinstance(w, dict) or not str(w.get("key") or "").strip():
                raise ValueError(f"entity {eid} watcher {widx} requires key")
            wkind = str(w.get("kind") or "rule").strip().lower()
            if wkind not in WATCHER_KINDS:
                raise ValueError(f"entity {eid} watcher {widx} kind must be one of {WATCHER_KINDS}")
            watchers.append({
                "key": str(w["key"]).strip(),
                "short": str(w.get("short") or str(w["key"]).strip()[:6].upper()),
                "kind": wkind,
                "name": str(w.get("name") or w["key"]).strip(),
                "status": str(w.get("status") or "watching").strip(),
                "value": str(w.get("value") or "").strip(),
                "line": str(w.get("line") or "").strip(),
                "weight": max(0.05, min(1.0, float(w.get("weight", 0.35)))),
                "detail": _detail(w.get("detail"), f"entity {eid} watcher {widx}"),
            })
        entities.append({
            "id": eid,
            "label": str(e.get("label") or eid).strip(),
            "sector": sec,
            "stage": stage,
            "score": round(score, 1),
            "pulse_rate": float(e.get("pulse_rate", 68.0)),
            "summary": str(e.get("summary") or "").strip(),
            "draft": str(e.get("draft") or "").strip(),
            "metrics": e.get("metrics") if isinstance(e.get("metrics"), dict) else {},
            "watchers": watchers,
            "detail": _detail(e.get("detail"), f"entity {eid}"),
        })

    active_id = spec.get("active_entity")
    if active_id is not None and str(active_id) not in entity_ids:
        raise ValueError(f"active_entity '{active_id}' not in entities")
    selected_id = spec.get("selected_entity")
    if selected_id is not None and str(selected_id) not in entity_ids:
        raise ValueError(f"selected_entity '{selected_id}' not in entities")

    return {
        "schema_version": 1,
        "title": title,
        "subtitle": subtitle,
        "brief": _brief(spec.get("brief"), entity_ids),
        "badge": badge,
        "banner": banner,
        "entity_noun": str(spec.get("entity_noun") or "entities").strip(),
        "default_scope": str(spec.get("default_scope") or "all").strip(),
        "default_theme": "light" if str(spec.get("default_theme", "dark")).lower() == "light" else "dark",
        "tick": int(spec.get("tick", 75075)),
        "pending_reviews": int(spec.get("pending_reviews", 1 if active_id else 0)),
        "active_entity": str(active_id) if active_id else None,
        "selected_entity": str(selected_id) if selected_id else None,
        "awaiting_approval": bool(spec.get("awaiting_approval", bool(active_id))),
        "agent": {
            "model": model_name,
            "beats": [b.strip() for b in beats],
            "gate_beat": gate_beat,
            "active_beat": int(agent.get("active_beat", gate_beat if active_id else 0)),
            "status_line": str(agent.get("status_line") or f"Watching {len(entities)} {spec.get('entity_noun', 'entities')}"),
            "beat_help": [str(x).strip() for x in (agent.get("beat_help") or [])][:len(beats)],
        },
        "persona": persona_norm,
        "sectors": sectors,
        "entities": entities,
    }


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="__DEFAULT_THEME__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__ — Mission Control</title>
<style>
:root, [data-theme="dark"] {
  --mc-bg: #0b1422;
  --mc-panel: #121d2f;
  --mc-surface: #080d18;
  --mc-raised: #17253b;
  --mc-ink: #f1f5fa;
  --mc-muted: #acbcd0;
  --mc-faint: #7d8fa6;
  --mc-border: #28374e;
  --mc-grid: #253248;
  --mc-accent: #55c9df;
  --mc-critical: #ff5263;
  --mc-concerning: #ff914d;
  --mc-atRisk: #f2b544;
  --mc-stable: #6ea8ff;
  --mc-model: #f0b94a;
  --mc-human: #ff4f9a;
  --mc-system: #a98bff;
}
[data-theme="light"] {
  --mc-bg: #edf2f7;
  --mc-panel: #ffffff;
  --mc-surface: #f8fafc;
  --mc-raised: #e8eff7;
  --mc-ink: #142338;
  --mc-muted: #4a5b70;
  --mc-faint: #64768c;
  --mc-border: #c6d2df;
  --mc-grid: #b8c8d9;
  --mc-accent: #087f99;
  --mc-critical: #d92535;
  --mc-concerning: #c9500b;
  --mc-atRisk: #9a6200;
  --mc-stable: #2563eb;
  --mc-model: #8a5a00;
  --mc-human: #b62e78;
  --mc-system: #6e42bb;
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: var(--mc-surface); color: var(--mc-ink); font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
.shell { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
.shell > .topbar, .shell > .brief, .shell > .scope-bar { flex: none; }
.topbar { display: flex; align-items: center; gap: 14px; padding: 0 18px; min-height: 52px; background: var(--mc-panel); border-bottom: 1px solid var(--mc-border); }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; letter-spacing: 0.01em; }
.brand-icon { width: 28px; height: 28px; border-radius: 7px; background: rgba(85,201,223,0.16); border: 1px solid var(--mc-accent); display: grid; place-items: center; color: var(--mc-accent); font-size: 14px; }
.brand-sub { display: block; font-size: 9px; font-weight: 600; letter-spacing: 0.14em; color: var(--mc-faint); text-transform: uppercase; }
.title-badge { font-size: 11px; padding: 2px 7px; border-radius: 5px; background: var(--mc-raised); border: 1px solid var(--mc-border); color: var(--mc-accent); font-family: ui-monospace, Menlo, monospace; }
.search-top { margin-left: 16px; flex: 0 1 320px; }
.search-top input { width: 100%; padding: 6px 11px; border-radius: 7px; border: 1px solid var(--mc-border); background: var(--mc-surface); color: var(--mc-ink); font-size: 12px; }
.topbar-right { margin-left: auto; display: flex; align-items: center; gap: 10px; min-width: 0; }
/* Real data has long words, paths and ids: wrap them instead of widening the page on phones. */
.brand, .brand > div, .topbar-right, .card, .entity-item > span, .watcher-row, .metric-tile, .persona-role, .persona-q, .persona-ctx, .persona-metric { min-width: 0; overflow-wrap: anywhere; }
.pill-warn { font-size: 11px; padding: 4px 10px; border-radius: 999px; background: rgba(242,181,68,0.14); border: 1px solid var(--mc-atRisk); color: var(--mc-atRisk); font-weight: 600; }
.btn { cursor: pointer; padding: 5px 11px; border-radius: 7px; border: 1px solid var(--mc-border); background: var(--mc-raised); color: var(--mc-ink); font-size: 12px; font-weight: 500; }
.btn:hover { border-color: var(--mc-accent); }
.btn.active { border-color: var(--mc-accent); color: var(--mc-accent); background: rgba(85,201,223,0.12); }
.scope-bar { margin: 10px 18px 0; padding: 10px 14px; background: var(--mc-panel); border: 1px solid var(--mc-border); border-radius: 10px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.scope-tabs { display: flex; flex-wrap: wrap; gap: 6px; }
.scope-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-left: auto; min-width: 0; font-size: 12px; color: var(--mc-muted); font-family: ui-monospace, Menlo, monospace; }
.scope-meta b { color: var(--mc-ink); }
.crit-tag { color: var(--mc-critical); font-weight: 600; }
.needs-you { display: inline-flex; align-items: center; gap: 7px; color: var(--mc-critical); font-weight: 650; padding: 2px 10px 2px 8px; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--mc-critical) 45%, transparent); background: color-mix(in srgb, var(--mc-critical) 10%, transparent); }
.needs-you::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--mc-critical); animation: mc-ping 2s ease-out infinite; }
@keyframes mc-ping { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--mc-critical) 60%, transparent); } 100% { box-shadow: 0 0 0 9px transparent; } }
@media (prefers-reduced-motion: reduce) { .needs-you::before { animation: none; box-shadow: 0 0 0 3px color-mix(in srgb, var(--mc-critical) 35%, transparent); } }
.workspace { flex: 1 1 auto; display: grid; grid-template-columns: 290px 1fr 330px; gap: 12px; padding: 10px 18px 14px; min-height: 0; overflow: hidden; }
.rail { display: flex; flex-direction: column; gap: 10px; min-height: 0; overflow-y: auto; padding-right: 2px; }
.card { background: var(--mc-panel); border: 1px solid var(--mc-border); border-radius: 10px; padding: 12px 14px; }
.card-h { font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--mc-faint); margin: 0 0 8px; display: flex; justify-content: space-between; align-items: center; }
.stat-hero { display: flex; justify-content: space-between; align-items: baseline; }
.stat-num { font-size: 34px; font-weight: 700; line-height: 1; font-family: ui-monospace, Menlo, monospace; }
.stat-lbl { font-size: 10px; letter-spacing: 0.14em; color: var(--mc-faint); text-transform: uppercase; margin-top: 4px; }
.live-pill { font-size: 11px; font-family: ui-monospace, Menlo, monospace; color: var(--mc-accent); display: flex; align-items: center; gap: 6px; }
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--mc-accent); box-shadow: 0 0 8px var(--mc-accent); }
.persona-role { font-weight: 600; font-size: 13px; margin: 4px 0; }
.persona-q { font-style: italic; color: var(--mc-ink); font-size: 12.5px; margin: 6px 0; padding-left: 8px; border-left: 2px solid var(--mc-accent); }
.persona-ctx { font-size: 11.5px; color: var(--mc-muted); }
.persona-metric { font-size: 11.5px; color: var(--mc-accent); margin-top: 6px; font-family: ui-monospace, Menlo, monospace; }
.mix-row { display: grid; grid-template-columns: 82px 1fr 28px; align-items: center; gap: 8px; margin: 5px 0; font-size: 12px; cursor: pointer; }
.mix-bar { height: 7px; background: var(--mc-surface); border-radius: 4px; overflow: hidden; }
.mix-bar > i { display: block; height: 100%; border-radius: 4px; }
.entity-list { display: flex; flex-direction: column; gap: 5px; max-height: 220px; overflow-y: auto; margin-top: 6px; }
.entity-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-radius: 6px; background: var(--mc-surface); border: 1px solid transparent; cursor: pointer; font-size: 12px; }
.entity-item:hover, .entity-item.sel { border-color: var(--mc-accent); background: var(--mc-raised); }
.entity-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 7px; }
.map-stage { position: relative; background: var(--mc-surface); border: 1px solid var(--mc-border); border-radius: 10px; overflow: hidden; min-height: 420px; }
.map-stage canvas { display: block; width: 100%; height: 100%; cursor: grab; touch-action: none; }
.map-hud-tl { position: absolute; left: 14px; top: 12px; font: 600 11px ui-monospace, Menlo, monospace; color: var(--mc-accent); letter-spacing: 0.1em; text-transform: uppercase; pointer-events: none; background: color-mix(in srgb, var(--mc-surface) 70%, transparent); -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); padding: 4px 11px; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--mc-accent) 30%, var(--mc-border)); }
.map-controls { position: absolute; right: 12px; bottom: 12px; display: flex; gap: 5px; }
.map-legend { position: absolute; left: 12px; bottom: 12px; max-width: calc(100% - 170px); display: flex; gap: 10px; flex-wrap: wrap; font: 11px ui-monospace, Menlo, monospace; background: color-mix(in srgb, var(--mc-surface) 70%, transparent); -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); padding: 5px 12px; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--mc-border) 80%, transparent); color: var(--mc-muted); }
.map-legend span { display: inline-flex; align-items: center; gap: 5px; }
.map-legend i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.metric-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin: 8px 0; }
.metric-tile { background: var(--mc-surface); border: 1px solid var(--mc-border); border-radius: 6px; padding: 6px 8px; font-family: ui-monospace, Menlo, monospace; }
.metric-tile small { display: block; font-size: 9.5px; color: var(--mc-faint); text-transform: uppercase; }
.metric-tile strong { font-size: 13px; color: var(--mc-ink); }
/* ---- Click-through detail sheet (entity, watcher, beat, help) ---- */
.mc-scrim { position: fixed; inset: 0; background: rgba(4,8,16,0.42); z-index: 2147483000; opacity: 0; pointer-events: none; transition: opacity .18s; }
.mc-scrim.open { opacity: 1; pointer-events: auto; }
.mc-sheet { position: fixed; top: 0; right: 0; bottom: 0; width: min(480px, 100vw); z-index: 2147483001; background: var(--mc-panel); color: var(--mc-ink);
  border-left: 1px solid var(--mc-border); box-shadow: -24px 0 60px -30px rgba(0,0,0,.6); transform: translateX(105%); transition: transform .22s ease;
  display: flex; flex-direction: column; overflow-wrap: anywhere; }
.mc-sheet.open { transform: none; }
.mc-sheet-h { display: flex; gap: 10px; align-items: flex-start; justify-content: space-between; padding: 16px 18px 10px; border-bottom: 1px solid var(--mc-border); }
.mc-sheet-h h2 { margin: 2px 0 0; font-size: 18px; line-height: 1.25; }
.mc-kicker { font: 600 11px/1 var(--mc-mono, ui-monospace, Menlo, monospace); color: var(--mc-muted); }
.mc-x { flex: none; width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--mc-border); background: transparent; color: inherit; font-size: 18px; cursor: pointer; }
.mc-sheet-b { padding: 14px 18px 28px; overflow-y: auto; font-size: 14px; line-height: 1.5; }
.mc-sheet-b h3 { font-size: 12px; font-weight: 650; color: var(--mc-muted); margin: 18px 0 6px; }
.mc-sheet-b p { margin: 0 0 6px; } .mc-sheet-b ul { margin: 0; padding-left: 18px; } .mc-sheet-b li { margin: 3px 0; }
.mc-why { border: 1px solid color-mix(in srgb, var(--mc-critical) 45%, transparent); background: color-mix(in srgb, var(--mc-critical) 9%, transparent);
  border-radius: 12px; padding: 12px 14px; }
.mc-why b { color: var(--mc-critical); }
.mc-decision { border: 1px solid color-mix(in srgb, var(--mc-human) 50%, transparent); background: color-mix(in srgb, var(--mc-human) 8%, transparent); border-radius: 12px; padding: 12px 14px; margin-top: 12px; }
.mc-q { font-weight: 650; font-size: 15px; margin-bottom: 10px; }
.mc-opt { display: block; width: 100%; text-align: left; text-decoration: none; color: inherit; border: 1px solid var(--mc-border); background: var(--mc-surface);
  border-radius: 10px; padding: 9px 12px; margin: 6px 0; cursor: pointer; font: inherit; }
.mc-opt:hover, .mc-opt:focus-visible { border-color: var(--mc-accent); outline: none; }
.mc-opt b { display: block; } .mc-opt small { color: var(--mc-muted); }
.mc-opt.rec { border-color: color-mix(in srgb, var(--mc-accent) 60%, var(--mc-border)); }
.mc-tag { display: inline-block; font-size: 11px; font-weight: 650; color: var(--mc-accent); margin-left: 6px; }
.mc-how { color: var(--mc-muted); font-size: 12.5px; margin-top: 6px; }
.mc-w { border-left: 3px solid var(--mc-stable); background: var(--mc-surface); border-radius: 8px; padding: 8px 10px; margin: 6px 0; }
.mc-w.model { border-left-color: var(--mc-model); } .mc-w.human { border-left-color: var(--mc-human); } .mc-w.system { border-left-color: var(--mc-system); } .mc-w.alert { border-left-color: var(--mc-critical); }
.mc-w.focus { outline: 2px solid var(--mc-accent); outline-offset: 2px; }
.mc-w-h { display: flex; justify-content: space-between; gap: 8px; font-weight: 600; }
.mc-w-h span:last-child { color: var(--mc-muted); font-weight: 500; }
.mc-tl { list-style: none; padding: 0 !important; } .mc-tl li { display: grid; grid-template-columns: 92px 1fr; gap: 8px; }
.mc-tl time { color: var(--mc-faint); font: 12px var(--mc-mono, ui-monospace, Menlo, monospace); }
.mc-dk { display: flex; justify-content: space-between; align-items: center; }
.mc-gh { display: inline-flex; width: 26px; height: 26px; align-items: center; justify-content: center; border-radius: 7px; color: var(--mc-muted);
  border: 1px solid transparent; }
.mc-gh:hover, .mc-gh:focus-visible { color: var(--mc-accent); border-color: var(--mc-border); outline: none; }
.mc-opt.picked { border-color: var(--mc-accent); border-width: 2px; background: color-mix(in srgb, var(--mc-accent) 14%, var(--mc-surface)); }
.mc-opt.picked b::before { content: "✓ "; color: var(--mc-accent); }
.mc-gh { color: var(--mc-ink) !important; border-color: var(--mc-border) !important; }
.mc-confirm { margin: 8px 0 2px; display: grid; gap: 8px; }
.mc-confirm textarea { width: 100%; min-height: 70px; resize: vertical; border-radius: 8px; border: 1px solid var(--mc-border); background: var(--mc-surface);
  color: var(--mc-ink); font: inherit; padding: 8px 10px; }
.mc-send { justify-self: start; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--mc-accent); background: var(--mc-accent); color: var(--mc-bg, #0b1220);
  font-weight: 650; cursor: pointer; }
.mc-send[disabled] { opacity: .6; cursor: progress; }
.mc-result { font-size: 13px; } .mc-result.ok { color: var(--mc-stable); } .mc-result.err { color: var(--mc-critical); }
.mc-links a { margin-right: 12px; }
.mc-sheet a { color: var(--mc-accent); text-underline-offset: 2px; }
.mc-open { width: 100%; margin-top: 8px; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--mc-accent); background: color-mix(in srgb, var(--mc-accent) 12%, transparent);
  color: var(--mc-ink); font-weight: 600; cursor: pointer; }
.watcher-row.clickable, .beat-item.clickable { cursor: pointer; }
.watcher-row.clickable:hover, .beat-item.clickable:hover { outline: 1px solid var(--mc-accent); }
@media (max-width: 700px) { .mc-sheet { top: auto; left: 0; width: 100vw; max-height: 86vh; border-left: 0; border-top: 1px solid var(--mc-border); border-radius: 16px 16px 0 0; transform: translateY(105%); } .mc-sheet.open { transform: none; } }
@media (prefers-reduced-motion: reduce) { .mc-sheet, .mc-scrim { transition: none; } }
.watcher-row { padding: 5px 8px; border-radius: 6px; background: var(--mc-surface); margin: 3px 0; font-size: 11px; border-left: 3px solid var(--mc-stable); }
.watcher-row.model { border-left-color: var(--mc-model); }
.watcher-row.human { border-left-color: var(--mc-human); }
.watcher-row.system { border-left-color: var(--mc-system); }
.watcher-row.alert { border-left-color: var(--mc-critical); }
.watcher-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-weight: 600; }
.watcher-head span:last-child { font-family: ui-monospace, Menlo, monospace; color: var(--mc-accent); }
.watcher-sub { color: var(--mc-muted); font-size: 10.5px; margin-top: 1px; }
.beat-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px; font-family: ui-monospace, Menlo, monospace; font-size: 11px; }
.beat-item { display: flex; justify-content: space-between; padding: 3px 7px; border-radius: 5px; background: var(--mc-surface); }
.beat-item.done { color: var(--mc-stable); }
.beat-item.halted { color: var(--mc-human); border: 1px solid var(--mc-human); font-weight: 600; }
.beat-item.running { color: var(--mc-model); }
.gate-box { margin-top: 8px; padding: 9px 10px; border-radius: 8px; background: rgba(255,79,154,0.1); border: 1px solid var(--mc-human); font-size: 12px; }
.gate-actions { display: flex; gap: 8px; margin-top: 8px; }
.btn-approve { background: var(--mc-stable); color: var(--mc-onStable, #fff); border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: 600; }
.btn-reject { background: transparent; color: var(--mc-critical); border: 1px solid var(--mc-critical); padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: 600; }
.brief { margin: 10px 18px 0; display: grid; gap: 8px; }
/* With a brief, the page scrolls: brief on top, the cockpit keeps a full viewport below it. */
.shell.has-brief { height: auto; min-height: 100vh; overflow: visible; }
.shell.has-brief .workspace { flex: none; height: calc(100vh - 92px); min-height: 640px; }
.brief[hidden] { display: none; }
.brief-lead { padding: 8px 12px; border-radius: 10px; border: 1px solid var(--mc-critical); background: color-mix(in srgb, var(--mc-critical) 12%, var(--mc-panel)); color: var(--mc-ink); font-weight: 650; font-size: 13px; }
.brief-lead::before { content: ""; display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: var(--mc-critical); margin-right: 8px; vertical-align: 1px; }
.brief-items { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 8px; }
.brief-item { display: flex; flex-direction: column; justify-content: flex-start; text-align: left; font: inherit; color: var(--mc-ink); padding: 8px 11px; border-radius: 10px; border: 1px solid var(--mc-border); background: var(--mc-panel); min-width: 0; overflow-wrap: anywhere; }
button.brief-item { cursor: pointer; }
button.brief-item:hover { border-color: var(--mc-accent); }
.brief-item.warn { border-color: var(--mc-concerning); }
.brief-item b { display: block; font-size: 12.5px; color: var(--mc-ink); font-weight: 700; margin-bottom: 3px; }
.brief-item.warn b { color: var(--mc-concerning); }
.brief-item ol { margin: 2px 0 0; padding-left: 18px; font-size: 12px; }
.brief-item span, .brief-item ol { font-size: 12.5px; color: var(--mc-muted); }
/* Themed scrollbars (UI-DECISIONS: scrollbars follow the theme). color-scheme makes native
   widgets dark/light; scrollbar-color covers Chrome 121+/Firefox, ::-webkit-scrollbar older Safari/Chrome. */
[data-theme="dark"] { color-scheme: dark; }
[data-theme="light"] { color-scheme: light; }
:root { --mc-scroll-thumb: color-mix(in srgb, var(--mc-faint) 55%, transparent); --mc-scroll-thumb-hover: var(--mc-muted); --mc-scroll-track: transparent; }
* { scrollbar-width: thin; scrollbar-color: var(--mc-scroll-thumb) var(--mc-scroll-track); }
html { scrollbar-color: var(--mc-scroll-thumb) var(--mc-surface); }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--mc-scroll-track); }
::-webkit-scrollbar-thumb { background: var(--mc-scroll-thumb); border-radius: 999px; border: 2px solid transparent; background-clip: padding-box; }
::-webkit-scrollbar-thumb:hover { background: var(--mc-scroll-thumb-hover); background-clip: padding-box; }
::-webkit-scrollbar-corner { background: transparent; }
/* Ask pane (served by `creator.py mission-control serve`; disabled when opened as a file). */
.mc-ask { position: fixed; top: 0; right: 0; bottom: 0; width: min(400px, 100vw); z-index: 2147482990; display: none; flex-direction: column;
  background: var(--mc-panel); color: var(--mc-ink); border-left: 1px solid var(--mc-border); box-shadow: -12px 0 32px rgba(0,0,0,.28); }
.mc-ask.open { display: flex; }
@media (min-width: 1280px) { body.ask-open .shell { margin-right: 400px; } }
.mc-ask-h { display: flex; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--mc-border); }
.mc-ask-h b { font-size: 14px; flex: 1; }
.mc-ask-h small { color: var(--mc-muted); font: 11px var(--mc-mono, ui-monospace, Menlo, monospace); }
.mc-ask-log { flex: 1 1 auto; overflow-y: auto; padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; font-size: 13.5px; line-height: 1.5; }
.mc-ask-off { padding: 10px 12px; border-radius: 10px; border: 1px dashed var(--mc-border); color: var(--mc-muted); }
.mc-ask-off code { font: 12px var(--mc-mono, ui-monospace, Menlo, monospace); color: var(--mc-ink); }
.mc-msg { padding: 9px 11px; border-radius: 10px; overflow-wrap: anywhere; }
.mc-msg.q { align-self: flex-end; max-width: 88%; background: color-mix(in srgb, var(--mc-accent) 16%, var(--mc-panel)); border: 1px solid color-mix(in srgb, var(--mc-accent) 40%, var(--mc-border)); white-space: pre-wrap; }
.mc-msg.a { background: var(--mc-raised, var(--mc-surface)); border: 1px solid var(--mc-border); }
.mc-msg.err { border: 1px solid var(--mc-critical); color: var(--mc-ink); white-space: pre-wrap; }
.mc-msg.a p { margin: 0 0 6px; } .mc-msg.a ul, .mc-msg.a ol { margin: 4px 0 6px; padding-left: 20px; }
.mc-msg.a h4 { margin: 8px 0 4px; font-size: 13px; }
.mc-msg.a code { font: 12px var(--mc-mono, ui-monospace, Menlo, monospace); background: var(--mc-surface); padding: 1px 4px; border-radius: 4px; }
.mc-msg.a pre { background: var(--mc-surface); padding: 8px; border-radius: 8px; overflow-x: auto; white-space: pre; }
.mc-msg.a table { border-collapse: collapse; display: block; overflow-x: auto; font-size: 12.5px; }
.mc-msg.a td, .mc-msg.a th { border: 1px solid var(--mc-border); padding: 3px 6px; text-align: left; }
.mc-msg a, .mc-src a { color: var(--mc-accent); }
.mc-msg .mc-who { display: block; font: 600 11px var(--mc-mono, ui-monospace, Menlo, monospace); color: var(--mc-muted); margin-bottom: 4px; }
.mc-src { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 6px; }
.mc-src a, .mc-src span { font: 11px var(--mc-mono, ui-monospace, Menlo, monospace); padding: 2px 8px; border-radius: 999px; border: 1px solid var(--mc-border); background: var(--mc-panel); text-decoration: none; overflow-wrap: anywhere; }
.mc-src span { color: var(--mc-muted); }
.mc-thinking { color: var(--mc-muted); font-style: italic; }
.mc-thinking::before { content: ""; display: inline-block; width: 8px; height: 8px; margin-right: 8px; border-radius: 50%; background: var(--mc-accent); animation: mcAskPulse 1.2s ease-in-out infinite; }
@keyframes mcAskPulse { 0%,100% { opacity: .3; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .mc-thinking::before { animation: none; } }
.mc-ask-f { border-top: 1px solid var(--mc-border); padding: 10px 14px 14px; display: grid; gap: 8px; }
.mc-ask-f textarea { width: 100%; min-height: 58px; max-height: 160px; resize: vertical; font: inherit; color: var(--mc-ink); background: var(--mc-surface); border: 1px solid var(--mc-border); border-radius: 8px; padding: 8px; }
.mc-ask-row { display: flex; gap: 8px; flex-wrap: wrap; }
.mc-ask-row .btn { flex: 1 1 auto; }
.mc-ask-row .mc-send { flex: none; }
.mc-ask-f :disabled { opacity: .45; cursor: not-allowed; }
@media (max-width: 700px) { .mc-ask { top: auto; left: 0; width: 100vw; height: 78vh; border-left: 0; border-top: 1px solid var(--mc-border); border-radius: 14px 14px 0 0; } }
@media (max-width: 700px) {
  .topbar { flex-wrap: wrap; gap: 8px 10px; padding: 8px 12px; }
  .search-top { order: 3; flex: 1 1 100%; margin-left: 0; }
  .topbar-right { flex-wrap: wrap; gap: 6px; }
  .brief, .scope-bar { margin-left: 10px; margin-right: 10px; }
}
@media (max-width: 980px) {
  .shell { height: auto; overflow: visible; }
  .workspace { grid-template-columns: 1fr; overflow: visible; }
  .map-stage { height: 420px; order: -1; }
  .shell.has-brief .workspace { height: auto; min-height: 0; }
}
/*__STYLE_CSS__*/
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand">
      <div class="brand-icon">◈</div>
      <div>
        <span id="brand-title">__TITLE__</span>
        <span class="brand-sub" id="brand-sub">MISSION CONTROL</span>
      </div>
      <span class="title-badge" id="title-badge">__BADGE__</span>
    </div>
    <div class="search-top">
      <input id="entity-search" type="search" placeholder="Find ID, label, or watcher…" aria-label="Find entity">
    </div>
    <div class="topbar-right">
      <span class="pill-warn" id="banner-pill">__BANNER__</span>
      <button type="button" class="btn" id="btn-ask" aria-controls="mc-ask" aria-expanded="false">Ask</button>
      <button type="button" class="btn" id="btn-help" aria-haspopup="dialog">What can I click?</button>
      <button type="button" class="btn" id="btn-theme" aria-label="Toggle theme">Theme</button>
    </div>
  </header>

  <section class="brief" id="brief" aria-label="Briefing" hidden></section>

  <section class="scope-bar" aria-label="Cohort scope">
    <div class="scope-tabs" id="scope-tabs"></div>
    <div class="scope-meta" id="scope-meta"></div>
  </section>

  <main class="workspace">
    <aside class="rail" aria-label="Left statistics and cohort controls">
      <div class="card">
        <div class="stat-hero">
          <div>
            <div class="stat-num" id="stat-total">0</div>
            <div class="stat-lbl" id="stat-noun">ENTITIES WATCHED</div>
          </div>
          <div class="live-pill"><span class="live-dot"></span><span id="live-tick">LIVE</span></div>
        </div>
      </div>

      <div class="card">
        <div class="card-h"><span>VIEWING AS</span><span id="persona-scope-tag"></span></div>
        <div class="persona-role" id="persona-role"></div>
        <div class="persona-q" id="persona-q"></div>
        <div class="persona-ctx" id="persona-ctx"></div>
        <div class="persona-metric" id="persona-metric"></div>
      </div>

      <div class="card">
        <div class="card-h"><span>COHORT MIX</span><span id="mix-scope-label"></span></div>
        <div id="mix-bars"></div>
      </div>

      <div class="card">
        <div class="card-h"><span>FIND · <em id="match-count" style="font-style:normal">0</em> MATCHES</span></div>
        <div class="entity-list" id="entity-list"></div>
      </div>
    </aside>

    <section class="map-stage" id="map-host" aria-label="Mission Control orbital map">
      <canvas id="map-canvas"></canvas>
      <div class="map-hud-tl" id="map-hud-tl">ALL · 0 in view</div>
      <div class="map-legend">
        <span><i style="background:var(--mc-critical)"></i>Critical</span>
        <span><i style="background:var(--mc-concerning)"></i>Concerning</span>
        <span><i style="background:var(--mc-atRisk)"></i>At-Risk</span>
        <span><i style="background:var(--mc-stable)"></i>Stable</span>
      </div>
      <div class="map-controls">
        <button type="button" class="btn" id="zoom-in" title="Zoom in">+</button>
        <button type="button" class="btn" id="zoom-out" title="Zoom out">−</button>
        <button type="button" class="btn" id="zoom-reset" title="Reset view">100%</button>
      </div>
    </section>

    <aside class="rail" aria-label="Selected entity inspector and loop beats">
      <div class="card" id="inspector-card">
        <div class="card-h"><span id="inspector-title">INSPECTOR</span><span id="inspector-stage"></span></div>
        <div id="inspector-body"></div>
      </div>

      <div class="card">
        <div class="card-h"><span>LOOP · <em id="beat-count-lbl" style="font-style:normal">SEVEN</em> BEATS</span><span id="agent-model-lbl"></span></div>
        <div id="loop-status-line" style="font-size:12px;color:var(--mc-muted);margin-bottom:8px"></div>
        <div class="beat-list" id="beat-list"></div>
      </div>
    </aside>
  </main>
</div>

<div class="mc-scrim" id="mc-scrim"></div>
<section class="mc-sheet" id="mc-sheet" role="dialog" aria-modal="true" aria-labelledby="mc-sheet-title" aria-hidden="true">
  <div class="mc-sheet-h"><div><div class="mc-kicker" id="mc-sheet-kicker"></div><h2 id="mc-sheet-title"></h2></div>
    <button type="button" class="mc-x" id="mc-sheet-close" aria-label="Close details">×</button></div>
  <div class="mc-sheet-b" id="mc-sheet-body"></div>
</section>
<script id="mission-control-spec" type="application/json">__SPEC_JSON__</script>
<script>
(function() {
  const SPEC = JSON.parse(document.getElementById('mission-control-spec').textContent);
  const PALETTES = {
    dark: {bg:'#0b1422',panel:'#121d2f',surface:'#080d18',ink:'#f1f5fa',muted:'#acbcd0',faint:'#7d8fa6',grid:'#253248',accent:'#55c9df',critical:'#ff5263',concerning:'#ff914d',atRisk:'#f2b544',stable:'#6ea8ff',model:'#f0b94a',human:'#ff4f9a',system:'#a98bff',outline:'#ffffff',idle:'#262434'},
    light: {bg:'#edf2f7',panel:'#ffffff',surface:'#f8fafc',ink:'#142338',muted:'#4a5b70',faint:'#64768c',grid:'#b8c8d9',accent:'#087f99',critical:'#d92535',concerning:'#c9500b',atRisk:'#9a6200',stable:'#2563eb',model:'#8a5a00',human:'#b62e78',system:'#6e42bb',outline:'#ffffff',idle:'#c6d2df'}
  };
  /*__STYLE_JS__*/
  const STAGE_RING = {critical: 0.40, concerning: 0.56, 'at-risk': 0.72, stable: 0.87};  // critical clears the beat-dial labels (R0 0.20 + label gap)
  const STAGE_LABEL = {critical: 'Critical', concerning: 'Concerning', 'at-risk': 'At-Risk', stable: 'Stable'};

  let theme = SPEC.default_theme || 'dark';
  let scope = SPEC.default_scope || 'all';
  let stageFilter = null;
  let query = '';

  // ---- Click-through detail sheet --------------------------------------------------------
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const link = (l) => l.url ? `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>` : esc(l.label);
  const sheet = document.getElementById('mc-sheet'), scrim = document.getElementById('mc-scrim');
  let sheetReturn = null, sheetOpenedAt = 0;
  function openSheet(kicker, title, html, focusSel) {
    document.getElementById('mc-sheet-kicker').textContent = kicker;
    document.getElementById('mc-sheet-title').textContent = title;
    document.getElementById('mc-sheet-body').innerHTML = html;
    sheetReturn = document.activeElement; sheetOpenedAt = performance.now();
    sheet.classList.add('open'); scrim.classList.add('open'); sheet.setAttribute('aria-hidden', 'false');
    const f = focusSel && sheet.querySelector(focusSel);
    if (f) { f.classList.add('focus'); f.scrollIntoView({block: 'center'}); }
    document.getElementById('mc-sheet-close').focus({preventScroll: true});
  }
  function closeSheet() {
    sheet.classList.remove('open'); scrim.classList.remove('open'); sheet.setAttribute('aria-hidden', 'true');
    if (sheetReturn && sheetReturn.focus) sheetReturn.focus({preventScroll: true});
  }
  document.getElementById('mc-sheet-close').onclick = closeSheet;
  // A touch tap that opens the sheet is followed by a synthetic click on the new scrim; ignore it.
  scrim.onclick = () => { if (performance.now() - sheetOpenedAt > 450) closeSheet(); };
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && sheet.classList.contains('open')) closeSheet(); });

  function watcherHtml(w, i) {
    const cls = w.status === 'alert' ? 'alert' : w.kind;
    const d = w.detail || {};
    return `<div class="mc-w ${cls}" id="mc-w-${i}"><div class="mc-w-h"><span>${esc(w.name)}</span><span>${esc(w.value || w.status)}</span></div>` +
      (w.line ? `<div>${esc(w.line)}</div>` : '') + (d.text ? `<div style="margin-top:4px">${esc(d.text)}</div>` : '') +
      (d.url ? `<div class="mc-links"><a href="${esc(d.url)}" target="_blank" rel="noopener">Open evidence</a></div>` : '') +
      `<div class="mc-how">${esc({rule: 'Rule check', model: 'AI agent', human: 'A person', system: 'Automated system'}[w.kind] || w.kind)} · status: ${esc(w.status)}</div></div>`;
  }
  const GH_ICON = '<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M9 2h5v5h-1.5V4.6L7.3 9.8 6.2 8.7l5.2-5.2H9V2zM3 4h4v1.5H3.5v7h7V9H12v4.5a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5v-9A.5.5 0 0 1 3 4z"/></svg>';
  function decisionHtml(dec) {
    if (!dec) return '';
    const live = !!dec.endpoint;
    const kick = `<div class="mc-dk"><span class="mc-kicker">THE DECISION</span>` +
      (dec.url ? `<a class="mc-gh" href="${esc(dec.url)}" target="_blank" rel="noopener" title="Open in GitHub" aria-label="Open in GitHub">${GH_ICON}</a>` : '') + `</div>`;
    return `<div class="mc-decision" data-endpoint="${esc(dec.endpoint || '')}">${kick}<div class="mc-q">${esc(dec.question)}</div>` +
      dec.options.map((o, i) => {
        const inner = `<b>${esc(o.label)}${o.recommended ? '<span class="mc-tag">recommended</span>' : ''}</b>${o.effect ? `<small>${esc(o.effect)}</small>` : ''}`;
        if (live && o.value) return `<button type="button" class="mc-opt${o.recommended ? ' rec' : ''}" data-i="${i}">${inner}</button>`;
        return o.url ? `<a class="mc-opt${o.recommended ? ' rec' : ''}" href="${esc(o.url)}" target="_blank" rel="noopener">${inner}</a>`
                     : `<div class="mc-opt${o.recommended ? ' rec' : ''}">${inner}</div>`;
      }).join('') + `<div class="mc-confirm" hidden></div>` + (dec.how ? `<div class="mc-how">${esc(dec.how)}</div>` : '') + `</div>`;
  }
  function wireDecision(root, item, dec) {
    const box = root.querySelector('.mc-decision'); if (!box || !dec || !dec.endpoint) return;
    const conf = box.querySelector('.mc-confirm');
    box.querySelectorAll('button.mc-opt').forEach(btn => btn.onclick = () => {
      const o = dec.options[Number(btn.dataset.i)];
      box.querySelectorAll('.mc-opt').forEach(x => x.classList.toggle('picked', x === btn));
      conf.hidden = false;
      conf.innerHTML = `<textarea placeholder="${o.needs_note ? 'Write what the agent should do instead (required)' : 'Optional note for the agent'}" aria-label="Note"></textarea>` +
        `<button type="button" class="mc-send">Send: ${esc(o.label)}</button><div class="mc-result" aria-live="polite"></div>`;
      const ta = conf.querySelector('textarea'), send = conf.querySelector('.mc-send'), out = conf.querySelector('.mc-result');
      ta.focus();
      send.onclick = async () => {
        const note = ta.value.trim();
        if (o.needs_note && !note) { out.className = 'mc-result err'; out.textContent = 'Write what to do instead first.'; ta.focus(); return; }
        send.disabled = true; out.className = 'mc-result'; out.textContent = 'Sending…';
        try {
          const r = await fetch(dec.endpoint, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
                                              body: JSON.stringify({item, value: o.value, option: o.label, note})});
          const j = await r.json().catch(() => ({}));
          out.className = 'mc-result ' + (r.ok ? 'ok' : 'err');
          out.textContent = r.ok ? (j.message || 'Recorded.') : ((j.error || ('Failed (' + r.status + ')')) + (j.how ? ' ' + j.how : ''));
          if (r.ok) { box.querySelectorAll('button.mc-opt').forEach(x => x.disabled = true); send.remove(); ta.readOnly = true; }
          else send.disabled = false;
        } catch (e) { out.className = 'mc-result err'; out.textContent = 'Could not reach the server.'; send.disabled = false; }
      };
    });
  }
  function openEntity(id, watcherIdx) {
    const e = SPEC.entities.find(x => x.id === id); if (!e) return;
    const d = e.detail || {};
    const sector = (SPEC.sectors.find(s => s.id === e.sector) || {}).label || e.sector;
    let h = '';
    if (d.why_you) h += `<div class="mc-why"><b>Why you are needed</b><p>${esc(d.why_you)}</p></div>`;
    else if (e.stage === 'critical') h += `<div class="mc-why"><b>Needs attention</b><p>${esc(e.summary || 'No reason was recorded for this item.')}</p></div>`;
    h += decisionHtml(d.decision);
    if (!d.decision && e.draft) h += `<h3>Proposed next step</h3><p>${esc(e.draft)}</p>`;
    if (e.summary && d.why_you) h += `<h3>Summary</h3><p>${esc(e.summary)}</p>`;
    const mk = Object.keys(e.metrics || {});
    if (mk.length) h += `<h3>Facts</h3><div class="metric-grid">` + mk.map(k => `<div class="metric-tile"><small>${esc(k)}</small><strong>${esc(e.metrics[k])}</strong></div>`).join('') + `</div>`;
    (d.sections || []).forEach(sec => {
      h += `<h3>${esc(sec.title)}</h3>` + (sec.text ? `<p>${esc(sec.text)}</p>` : '') +
        (sec.items.length ? `<ul>${sec.items.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '');
    });
    if (e.watchers.length) h += `<h3>Who is watching it (${e.watchers.length})</h3>` + e.watchers.map(watcherHtml).join('');
    if ((d.timeline || []).length) h += `<h3>What happened</h3><ul class="mc-tl">` +
      d.timeline.map(t => `<li><time>${esc(t.t)}</time><span>${t.url ? `<a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(t.text)}</a>` : esc(t.text)}</span></li>`).join('') + `</ul>`;
    if ((d.evidence || []).length) h += `<h3>Evidence</h3><div class="mc-links">${d.evidence.map(link).join(' ')}</div>`;
    openSheet(`${sector.toUpperCase()} · ${STAGE_LABEL[e.stage].toUpperCase()}`, `${e.id} · ${d.title || e.label}`, h,
              watcherIdx == null ? null : `#mc-w-${watcherIdx}`);
    wireDecision(document.getElementById('mc-sheet-body'), e.id, d.decision);
  }
  function openBeat(i) {
    const b = SPEC.agent.beats[i], help = (SPEC.agent.beat_help || [])[i];
    const gate = i + 1 === SPEC.agent.gate_beat;
    openSheet(`LOOP STEP ${i + 1} OF ${SPEC.agent.beats.length}`, b,
      `<p>${esc(help || 'No description was provided for this step.')}</p>` +
      (gate ? `<div class="mc-why" style="margin-top:10px"><b>This is the human gate.</b><p>Work stops here until a person decides. Items waiting here pulse on the map.</p></div>` : ''));
  }
  function openHelp() {
    openSheet('HOW TO READ THIS SCREEN', 'What can I click?',
      `<ul>
        <li><b>A dot on the map</b> is one ${esc(SPEC.entity_noun)}. Click it to open everything about it: why it matters, the decision, who is watching, what happened and the evidence.</li>
        <li><b>A pulsing dot or the red "needs you" pill</b> means a person must decide. The sheet starts with <i>Why you are needed</i> and <i>The decision</i>.</li>
        <li><b>The small labels around a selected dot</b> are its watchers (rules, AI agents, systems, people). Click one to jump to its detail.</li>
        <li><b>The list on the left</b> and the <b>search</b> find an item when the map is crowded. Click a row to open it.</li>
        <li><b>The loop steps on the right</b> explain each stage; the gate step is where people decide.</li>
        <li><b>Rings:</b> closer to the centre is more urgent (critical, concerning, at risk, stable). <b>Sectors</b> group items by type; the tabs above filter them.</li>
        <li><b>Map:</b> scroll or pinch to zoom, drag to pan, double-click to reset. Press Esc to close this sheet.</li>
      </ul>`);
  }
  document.getElementById('btn-help').onclick = openHelp;
  let selectedId = SPEC.selected_entity || SPEC.active_entity || (SPEC.entities[0] && SPEC.entities[0].id) || null;
  window.__mcSelected = () => { const e = SPEC.entities.find(x => x.id === selectedId); return e ? {id: e.id, label: e.label} : null; };
  let activeId = SPEC.active_entity || selectedId;
  let halted = !!SPEC.awaiting_approval;
  let gateOutcome = null;
  let simClockMs = 0;
  let view = {k: 1, x: 0, y: 0};

  const rgba = (hex, a) => {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
  };

  // Assign sector angles evenly around the circle starting at top (-PI/2)
  const sectorAngle = {};
  SPEC.sectors.forEach((s, i) => {
    sectorAngle[s.id] = -Math.PI / 2 + (i / SPEC.sectors.length) * Math.PI * 2;
  });

  // Deterministic node layout within each (sector, stage) band
  const nodes = SPEC.entities.map((e, idx) => {
    const sameBucket = SPEC.entities.filter(x => x.sector === e.sector && x.stage === e.stage);
    const posInBucket = sameBucket.indexOf(e);
    const countInBucket = Math.max(1, sameBucket.length);
    const spread = Math.min((Math.PI * 2 / Math.max(2.2, SPEC.sectors.length)) * 0.78, 1.2);  // use most of the sector so a busy bucket does not pile up
    const offsetAngle = countInBucket === 1 ? 0 : ((posInBucket / (countInBucket - 1)) - 0.5) * spread;
    const baseAngle = sectorAngle[e.sector] || 0;
    const radiusFrac = (STAGE_RING[e.stage] || 0.8) + (countInBucket > 3 ? ((posInBucket % 2) * 0.05 - 0.02) : ((idx % 3) - 1) * 0.025);  // stagger busy buckets so dots do not chain
    return {
      id: e.id,
      row: e,
      angle: baseAngle + offsetAngle,
      radiusFrac: radiusFrac,
      r: 4 + Math.min(6, Math.max(0, e.score) / 18),
      x: 0,
      y: 0
    };
  });
  const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]));

  function inScopeRows() {
    return SPEC.entities.filter(e => scope === 'all' || e.sector === scope);
  }
  function filteredRows() {
    return inScopeRows().filter(e => {
      if (stageFilter && e.stage !== stageFilter) return false;
      if (query) {
        const q = query.toLowerCase();
        const hay = (e.id + ' ' + e.label + ' ' + e.summary).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function renderUI() {
    document.documentElement.setAttribute('data-theme', theme);
    document.getElementById('btn-theme').textContent = theme === 'dark' ? '☀ Light' : '☾ Dark';
    document.getElementById('stat-total').textContent = String(SPEC.entities.length);
    document.getElementById('stat-noun').textContent = (SPEC.entity_noun || 'ENTITIES').toUpperCase() + ' WATCHED';
    document.getElementById('live-tick').textContent = 'LIVE · tick ' + SPEC.tick;
    document.getElementById('persona-scope-tag').textContent = SPEC.persona.scope_label;
    document.getElementById('persona-role').textContent = SPEC.persona.role;
    document.getElementById('persona-q').textContent = '“' + SPEC.persona.question + '”';
    document.getElementById('persona-ctx').textContent = SPEC.persona.context;
    document.getElementById('persona-metric').textContent = SPEC.persona.metric;
    document.getElementById('agent-model-lbl').textContent = SPEC.agent.model;
    document.getElementById('beat-count-lbl').textContent = String(SPEC.agent.beats.length);

    // Scope tabs
    const tabsEl = document.getElementById('scope-tabs');
    tabsEl.innerHTML = '';
    const allTab = document.createElement('button');
    allTab.type = 'button';
    allTab.className = 'btn' + (scope === 'all' ? ' active' : '');
    allTab.textContent = `All ${SPEC.entity_noun} · ${SPEC.entities.length}`;
    allTab.onclick = () => { scope = 'all'; renderUI(); };
    tabsEl.appendChild(allTab);
    SPEC.sectors.forEach(s => {
      const cnt = SPEC.entities.filter(e => e.sector === s.id).length;
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn' + (scope === s.id ? ' active' : '');
      b.dataset.sectorTab = s.id;
      b.textContent = `${s.label} · ${cnt}`;
      b.onclick = () => { scope = s.id; renderUI(); };
      tabsEl.appendChild(b);
    });

    const scoped = inScopeRows();
    const totalCrit = SPEC.entities.filter(e => e.stage === 'critical').length;
    const scopedCrit = scoped.filter(e => e.stage === 'critical').length;
    const scopeName = scope === 'all' ? 'all' : (SPEC.sectors.find(s => s.id === scope)?.label || scope);
    document.getElementById('scope-meta').innerHTML =
      `<span>Whole cohort: <b>${SPEC.entities.length}</b> · <span class="crit-tag">Critical: ${totalCrit}</span></span>` +
      `<span>Current scope: <b>${scopeName} · ${scoped.length}</b> · <span class="crit-tag">Critical: ${scopedCrit}</span></span>` +
      (totalCrit ? `<span class="needs-you" role="status">${totalCrit} need${totalCrit === 1 ? 's' : ''} you</span>` : '') +
      `<span>Pending reviews: <b>${halted ? SPEC.pending_reviews : 0}</b></span>` +
      `<span><b>${SPEC.agent.model}</b></span>`;

    document.getElementById('mix-scope-label').textContent = `${scopeName} · ${scoped.length}`;
    document.getElementById('map-hud-tl').textContent = `${scopeName.toUpperCase()} · ${scoped.length} in view`;

    // Cohort mix bars
    const mixEl = document.getElementById('mix-bars');
    mixEl.innerHTML = '';
    const P = PALETTES[theme];
    const stageCols = {critical: P.critical, concerning: P.concerning, 'at-risk': P.atRisk, stable: P.stable};
    ['critical', 'concerning', 'at-risk', 'stable'].forEach(st => {
      const cnt = scoped.filter(e => e.stage === st).length;
      const pct = scoped.length ? Math.round((cnt / scoped.length) * 100) : 0;
      const row = document.createElement('div');
      row.className = 'mix-row';
      row.innerHTML = `<span style="color:${stageCols[st]};font-weight:${stageFilter===st?'700':'500'}">${STAGE_LABEL[st]}</span>` +
        `<div class="mix-bar"><i style="width:${pct}%;background:${stageCols[st]}"></i></div>` +
        `<span style="text-align:right;font-family:ui-monospace,Menlo,monospace">${cnt}</span>`;
      row.onclick = () => { stageFilter = stageFilter === st ? null : st; renderUI(); };
      mixEl.appendChild(row);
    });

    // Filtered list
    const listed = filteredRows();
    document.getElementById('match-count').textContent = String(listed.length);
    const listEl = document.getElementById('entity-list');
    listEl.innerHTML = '';
    listed.forEach(e => {
      const item = document.createElement('div');
      item.className = 'entity-item' + (e.id === selectedId ? ' sel' : '');
      item.dataset.entityId = e.id;
      item.innerHTML = `<span><i class="entity-dot" style="background:${stageCols[e.stage]}"></i><b>${esc(e.id)}</b> · ${esc(e.label)}</span>` +
        `<span class="entity-score" style="font-family:ui-monospace,Menlo,monospace;color:var(--mc-muted);white-space:nowrap;flex:none">${e.score.toFixed(1)}</span>`;
      item.onclick = () => { selectedId = e.id; renderUI(); openEntity(e.id); };
      listEl.appendChild(item);
    });

    // Inspector
    const sel = SPEC.entities.find(e => e.id === selectedId) || null;
    const inspTitle = document.getElementById('inspector-title');
    const inspStage = document.getElementById('inspector-stage');
    const inspBody = document.getElementById('inspector-body');
    if (!sel) {
      inspTitle.textContent = 'NO SELECTION';
      inspStage.textContent = '';
      inspBody.innerHTML = '<div style="color:var(--mc-muted);font-size:12px">Click any node on the orbital map or worklist to inspect its live watchers, metrics, and approval gate.</div>';
    } else {
      inspTitle.textContent = `${sel.id} · ${sel.label}`;
      inspStage.innerHTML = `<span style="color:${stageCols[sel.stage]};font-weight:700">${STAGE_LABEL[sel.stage].toUpperCase()} · ${sel.score.toFixed(1)}</span>`;
      let html = '';
      if (sel.summary) {
        html += `<div style="font-size:12px;color:var(--mc-muted);margin-bottom:6px">${esc(sel.summary)}</div>`;
      }
      const mKeys = Object.keys(sel.metrics || {});
      if (mKeys.length) {
        html += '<div class="metric-grid">';
        mKeys.forEach(k => {
          html += `<div class="metric-tile"><small>${esc(k)}</small><strong>${esc(sel.metrics[k])}</strong></div>`;
        });
        html += '</div>';
      }
      html += `<button type="button" class="mc-open" id="btn-open-detail">${sel.stage === 'critical' ? 'Why am I needed? Open details' : 'Open details'}</button>`;
      const dec = sel.detail && sel.detail.decision;
      if (dec && !gateOutcome) {
        html += `<div class="gate-box"><div style="font-weight:700;color:var(--mc-human)">YOUR DECISION</div>` +
          `<div style="margin-top:4px">${esc(dec.question)}</div>` +
          `<div class="gate-actions"><button type="button" class="btn-approve" id="btn-decide">Decide…</button></div></div>`;
      } else if (sel.id === activeId && (halted || gateOutcome || sel.draft)) {
        html += `<div class="gate-box"><div style="font-weight:700;color:var(--mc-human)">GATE · HUMAN APPROVAL REQUIRED</div>` +
          `<div style="margin-top:4px">${esc(sel.draft || 'Proposed action prepared by agent; awaiting human decision.')}</div>`;
        if (gateOutcome) {
          html += `<div style="margin-top:6px;font-weight:700;color:var(--mc-accent)">Outcome: ${gateOutcome.toUpperCase()}</div>`;
        } else {
          html += `<div class="gate-actions">` +
            `<button type="button" class="btn-approve" id="btn-approve-gate">Approve action</button>` +
            `<button type="button" class="btn-reject" id="btn-reject-gate">Reject</button></div>`;
        }
        html += `</div>`;
      }
      if (sel.watchers && sel.watchers.length) {
        html += '<div style="margin-top:8px;font-size:10px;letter-spacing:0.12em;color:var(--mc-faint);text-transform:uppercase">WATCHERS (' + sel.watchers.length + ')</div>';
        sel.watchers.forEach((w, wi) => {
          const cls = w.status === 'alert' ? 'alert' : w.kind;
          html += `<div class="watcher-row clickable ${cls}" role="button" tabindex="0" data-w="${wi}"><div class="watcher-head"><span>${esc(w.name)}</span><span>${esc(w.value || w.status)}</span></div>` +
            (w.line ? `<div class="watcher-sub">${esc(w.line)}</div>` : '') + `</div>`;
        });
      }
      inspBody.innerHTML = html;
      document.getElementById('btn-open-detail').onclick = () => openEntity(sel.id);
      const decBtn = document.getElementById('btn-decide');
      if (decBtn) decBtn.onclick = () => openEntity(sel.id);
      inspBody.querySelectorAll('.watcher-row.clickable').forEach(r => {
        const go = () => openEntity(sel.id, Number(r.dataset.w));
        r.onclick = go; r.onkeydown = (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); go(); } };
      });
      const appBtn = document.getElementById('btn-approve-gate');
      const rejBtn = document.getElementById('btn-reject-gate');
      if (appBtn) appBtn.onclick = () => { halted = false; gateOutcome = 'approved'; renderUI(); };
      if (rejBtn) rejBtn.onclick = () => { halted = false; gateOutcome = 'rejected'; renderUI(); };
    }

    // Loop beats
    document.getElementById('loop-status-line').textContent = SPEC.agent.status_line;
    const beatList = document.getElementById('beat-list');
    beatList.innerHTML = '';
    const activeBeat = gateOutcome === 'approved' ? SPEC.agent.beats.length : SPEC.agent.active_beat;
    SPEC.agent.beats.forEach((b, idx) => {
      const bnum = idx + 1;
      let st = 'idle';
      if (bnum < activeBeat) st = 'done';
      else if (bnum === activeBeat) st = halted && bnum === SPEC.agent.gate_beat ? 'halted' : 'done';
      const row = document.createElement('div');
      row.className = 'beat-item clickable ' + st;
      row.setAttribute('role', 'button'); row.tabIndex = 0;
      row.innerHTML = `<span>${bnum} · ${esc(b)}</span><span>${st.toUpperCase()}</span>`;
      row.onclick = () => openBeat(idx);
      row.onkeydown = (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); openBeat(idx); } };
      beatList.appendChild(row);
    });
  }

  // Canvas Setup & Render Loop
  const host = document.getElementById('map-host');
  const cv = document.getElementById('map-canvas');
  const ctx = cv.getContext('2d');
  const bg = document.createElement('canvas');
  let W = 0, H = 0, DPR = Math.min(2, window.devicePixelRatio || 1), paintedTheme = null;

  function paintBackdrop(P) {
    bg.width = W * DPR; bg.height = H * DPR;
    const b = bg.getContext('2d');
    b.setTransform(DPR, 0, 0, DPR, 0, 0);
    b.fillStyle = P.bg; b.fillRect(0, 0, W, H);
    const isLight = theme === 'light';
    [[P.system, 0.25, 0.3, 0.55], [P.accent, 0.8, 0.65, 0.45], [P.human, 0.18, 0.82, 0.32]].forEach(([c, x, y, r]) => {
      const g = b.createRadialGradient(W * x, H * y, 0, W * x, H * y, Math.max(W, H) * r);
      g.addColorStop(0, rgba(c, isLight ? 0.04 : 0.16));
      g.addColorStop(1, rgba(c, 0));
      b.fillStyle = g; b.fillRect(0, 0, W, H);
    });
    // Deterministic starfield seed
    let seed = 1337;
    const rand = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
    for (let i = 0; i < 280; i++) {
      const r = rand() * rand();
      b.fillStyle = rgba(isLight ? P.faint : P.ink, isLight ? 0.05 : 0.08 + r * 0.35);
      b.beginPath(); b.arc(rand() * W, rand() * H, 0.35 + r, 0, 7); b.fill();
    }
    paintedTheme = theme;
  }

  function resize() {
    W = Math.max(300, host.clientWidth);
    H = Math.max(300, host.clientHeight);
    cv.width = W * DPR; cv.height = H * DPR;
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    paintBackdrop(PALETTES[theme]);
  }
  window.addEventListener('resize', resize);
  // Re-measure when the stage changes size without a window resize (e.g. a brief strip above it).
  if (window.ResizeObserver) new ResizeObserver(() => { if (host.clientWidth !== W || host.clientHeight !== H) resize(); }).observe(host);

  function curve(ax, ay, bx, by, bend) {
    return [(ax + bx) / 2 - (by - ay) * bend, (ay + by) / 2 + (bx - ax) * bend];
  }
  function at(ax, ay, m, bx, by, t) {
    const u = 1 - t;
    return [u * u * ax + 2 * u * t * m[0] + t * t * bx, u * u * ay + 2 * u * t * m[1] + t * t * by];
  }
  function arm(ax, ay, bx, by, bend, w0, w1, fill) {
    const m = curve(ax, ay, bx, by, bend), N = 16, L = [], R = [];
    for (let i = 0; i <= N; i++) {
      const t = i / N, u = 1 - t, [x, y] = at(ax, ay, m, bx, by, t);
      const tx = 2 * u * (m[0] - ax) + 2 * t * (bx - m[0]), ty = 2 * u * (m[1] - ay) + 2 * t * (by - m[1]), len = Math.hypot(tx, ty) || 1;
      const w = (w0 + (w1 - w0) * Math.pow(t, 0.7)) / 2;
      L.push([x - (ty / len) * w, y + (tx / len) * w]);
      R.push([x + (ty / len) * w, y - (tx / len) * w]);
    }
    ctx.beginPath(); ctx.moveTo(L[0][0], L[0][1]);
    for (const p of L) ctx.lineTo(p[0], p[1]);
    for (let i = R.length - 1; i >= 0; i--) ctx.lineTo(R[i][0], R[i][1]);
    ctx.closePath(); ctx.fillStyle = fill; ctx.fill();
    return m;
  }
  function glow(x, y, r, col, a) {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, rgba(col, a)); g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }

  // Needs-attention cue: a calm 2 s ping (ring grows and fades). With reduced motion: a steady double ring.
  const REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function attentionRing(x, y, r, col, tSec) {
    ctx.lineWidth = 1.6 / view.k;
    if (REDUCED) {
      ctx.strokeStyle = rgba(col, 0.85);
      ctx.beginPath(); ctx.arc(x, y, r + 5 / view.k, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = rgba(col, 0.4);
      ctx.beginPath(); ctx.arc(x, y, r + 10 / view.k, 0, Math.PI * 2); ctx.stroke();
      return;
    }
    for (const off of [0, 0.5]) {
      const ph = ((tSec / 2) + off) % 1;
      ctx.strokeStyle = rgba(col, 0.75 * (1 - ph));
      ctx.beginPath(); ctx.arc(x, y, r + (4 + ph * 18) / view.k, 0, Math.PI * 2); ctx.stroke();
    }
  }

  let chipHits = [];
  function drawFrame(tSec) {
    const P = PALETTES[theme];
    if (paintedTheme !== theme) paintBackdrop(P);
    const STAGE_COL = {critical: P.critical, concerning: P.concerning, 'at-risk': P.atRisk, stable: P.stable};
    const KIND_COL = {rule: P.stable, model: P.model, human: P.human, system: P.system};
    const cx = W / 2, cy = H / 2, M = Math.max(60, Math.min(W, H) / 2 - 58);

    nodes.forEach(n => {
      n.x = cx + Math.cos(n.angle) * (n.radiusFrac * M);
      n.y = cy + Math.sin(n.angle) * (n.radiusFrac * M);
    });

    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.drawImage(bg, 0, 0, W, H);
    ctx.setTransform(DPR * view.k, 0, 0, DPR * view.k, DPR * (cx * (1 - view.k) + view.x), DPR * (cy * (1 - view.k) + view.y));

    const inScopeSet = new Set(filteredRows().map(r => r.id));
    const sel = selectedId ? nodeById[selectedId] : null;
    const active = activeId ? nodeById[activeId] : null;

    // Sector dividers, outer copper/amber arcs, and labels
    ctx.font = '600 11px ui-monospace, Menlo, monospace';
    ctx.textAlign = 'center';
    const sectorSpan = (Math.PI * 2) / SPEC.sectors.length;
    SPEC.sectors.forEach(s => {
      const a = sectorAngle[s.id], edge = a + sectorSpan / 2;
      ctx.strokeStyle = rgba(P.grid, theme === 'light' ? 0.65 : 0.32);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(edge) * M * 0.22, cy + Math.sin(edge) * M * 0.22);
      ctx.lineTo(cx + Math.cos(edge) * M * 0.96, cy + Math.sin(edge) * M * 0.96);
      ctx.stroke();

      const cnt = SPEC.entities.filter(e => e.sector === s.id).length;
      const faulty = s.faults > 0 || SPEC.entities.some(e => e.sector === s.id && e.stage === 'critical');
      ctx.strokeStyle = faulty ? rgba(P.concerning, 0.36 + 0.14 * Math.sin(tSec * 3)) : rgba(P.accent, theme === 'light' ? 0.35 : 0.22);
      ctx.lineWidth = faulty ? 9 : 6;
      ctx.beginPath();
      ctx.arc(cx, cy, M * 0.95, a - sectorSpan / 2 + 0.06, a + sectorSpan / 2 - 0.06);
      ctx.stroke();
      const statusSuffix = s.faults ? ` · ${s.faults} ALERT${s.faults > 1 ? 'S' : ''}` : ' · NOMINAL';
      let lbl = `${s.label.toUpperCase()} · ${cnt}${statusSuffix}`;
      const ideal = cx + Math.cos(a) * (M * 1.03);
      const room = 2 * Math.min(ideal, W - ideal) - 12;  // width that fits without being pushed over the ring
      if (ctx.measureText(lbl).width > Math.min(W * 0.42, Math.max(room, W * 0.2))) lbl = s.faults ? `${s.label.toUpperCase()} · ${cnt} · !${s.faults}` : `${s.label.toUpperCase()} · ${cnt}`;
      const lw = ctx.measureText(lbl).width;
      // keep the label inside the canvas at 100% (labels at 3/9 o'clock used to clip)
      const lx = Math.max(lw / 2 + 6, Math.min(W - lw / 2 - 6, cx + Math.cos(a) * (M * 1.03))), ly = cy + Math.sin(a) * (M * 1.03);
      // halo in the map background so arcs and dots never strike through the label
      ctx.lineJoin = 'round'; ctx.lineWidth = 4; ctx.strokeStyle = rgba(P.bg, 0.9);
      ctx.strokeText(lbl, lx, ly + (Math.sin(a) > 0.3 ? 13 : -6));
      ctx.fillStyle = faulty ? P.concerning : P.muted;
      ctx.fillText(lbl, lx, ly + (Math.sin(a) > 0.3 ? 13 : -6));
    });

    // Concentric stage rings
    Object.entries(STAGE_RING).forEach(([st, frac]) => {
      ctx.strokeStyle = rgba(STAGE_COL[st], theme === 'light' ? 0.26 : 0.14);
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 6]);
      ctx.beginPath(); ctx.arc(cx, cy, frac * M, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);
    });

    // Tapered arms from center to entities
    nodes.forEach(n => {
      const c = STAGE_COL[n.row.stage] || P.faint;
      const isA = n === active, isS = n === sel;
      const alpha = (isA ? 0.32 : isS ? 0.22 : 0.06) * (inScopeSet.has(n.id) ? 1 : 0.25);
      arm(cx, cy, n.x, n.y, 0.12, isA ? 9 : isS ? 5 : 2, 0.4, rgba(c, alpha));
      if (isA) {
        const m = curve(cx, cy, n.x, n.y, 0.12);
        for (let k = 0; k < 3; k++) {
          const p = (tSec * 0.35 + k / 3) % 1, [px, py] = at(cx, cy, m, n.x, n.y, p);
          glow(px, py, 13, P.model, 0.55);
        }
      }
    });

    // Agent center hub + beat dial
    const R0 = Math.max(36, M * 0.20) / Math.max(1, Math.pow(view.k, 0.6));
    const B = SPEC.agent.beats;
    const activeBeat = gateOutcome === 'approved' ? B.length : SPEC.agent.active_beat;
    for (let i = 0; i < B.length; i++) {
      const bnum = i + 1;
      const st = bnum < activeBeat ? 'done' : (bnum === activeBeat ? (halted && bnum === SPEC.agent.gate_beat ? 'halted' : 'running') : 'idle');
      const a0 = -Math.PI / 2 + (i / B.length) * Math.PI * 2 + 0.05;
      const a1 = a0 + (Math.PI * 2) / B.length - 0.1;
      const col = st === 'done' ? P.stable : st === 'halted' ? P.human : st === 'running' ? P.model : P.idle;
      ctx.strokeStyle = col;
      ctx.lineWidth = (st === 'idle' ? 5 : 8) / Math.max(1, view.k);
      ctx.beginPath(); ctx.arc(cx, cy, R0, a0, a1); ctx.stroke();
      const am = (a0 + a1) / 2;
      ctx.font = `${10 / Math.max(1, view.k)}px ui-monospace, Menlo, monospace`;
      ctx.fillStyle = st === 'idle' ? P.muted : P.ink;
      ctx.textAlign = 'center';
      ctx.lineJoin = 'round'; ctx.lineWidth = 3 / Math.max(1, view.k); ctx.strokeStyle = rgba(P.bg, 0.85);
      ctx.strokeText(`${bnum} ${B[i]}`, cx + Math.cos(am) * (R0 + 14 / Math.max(1, view.k)), cy + Math.sin(am) * (R0 + 14 / Math.max(1, view.k)) + 3);
      ctx.fillText(`${bnum} ${B[i]}`, cx + Math.cos(am) * (R0 + 14 / Math.max(1, view.k)), cy + Math.sin(am) * (R0 + 14 / Math.max(1, view.k)) + 3);
    }
    glow(cx, cy, R0 * 0.85, halted ? P.human : P.stable, 0.20);
    ctx.font = `700 ${11 / Math.max(1, view.k)}px ui-monospace, Menlo, monospace`;
    ctx.fillStyle = P.ink;
    ctx.textAlign = 'center';
    ctx.fillText(halted ? 'AWAITING GATE' : 'WATCHING', cx, cy - 2);
    ctx.font = `${9 / Math.max(1, view.k)}px ui-monospace, Menlo, monospace`;
    ctx.fillStyle = P.muted;
    ctx.fillText(SPEC.agent.model, cx, cy + 11 / Math.max(1, view.k));

    // Hex GATE on active arm
    if (active && halted) {
      const gx = cx + (active.x - cx) * 0.82, gy = cy + (active.y - cy) * 0.82, s = 14 + 2 * Math.sin(tSec * 4);
      ctx.strokeStyle = P.human; ctx.lineWidth = 2;
      ctx.beginPath();
      for (let k = 0; k <= 6; k++) {
        const a = (k / 6) * Math.PI * 2 + Math.PI / 6;
        ctx[k ? 'lineTo' : 'moveTo'](gx + Math.cos(a) * s, gy + Math.sin(a) * s);
      }
      ctx.stroke();
      ctx.font = '700 8.5px ui-monospace, Menlo, monospace';
      ctx.fillStyle = P.human;
      ctx.fillText('GATE', gx, gy + 3);
    }

    // Entity nodes
    nodes.forEach(n => {
      const c = STAGE_COL[n.row.stage] || P.accent;
      const inS = inScopeSet.has(n.id);
      glow(n.x, n.y, inS ? n.r * 3.5 : n.r * 1.5, c, inS ? 0.48 : 0.08);
      ctx.fillStyle = inS ? c : rgba(P.faint, 0.45);
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r / Math.pow(view.k, 0.4), 0, Math.PI * 2); ctx.fill();
      if (inS) {
        ctx.strokeStyle = P.outline; ctx.lineWidth = 1.4 / view.k; ctx.stroke();
      }
      if (n.row.stage === 'critical' && inS) attentionRing(n.x, n.y, n.r / Math.pow(view.k, 0.4), c, tSec);
    });

    // Selected entity watcher satellite ring
    chipHits = [];
    if (sel && sel.row.watchers && sel.row.watchers.length) {
      const team = sel.row.watchers;
      const Rs = Math.min(82, W * 0.24) / view.k;
      const dist = Math.hypot(sel.x - cx, sel.y - cy), clearance = R0 + Rs + 44 / view.k;
      const dx = dist > 1 ? (sel.x - cx) / dist : 1, dy = dist > 1 ? (sel.y - cy) / dist : 0;
      const tx = dist < clearance ? cx + dx * clearance : sel.x;
      const ty = dist < clearance ? cy + dy * clearance : sel.y;

      ctx.strokeStyle = rgba(P.accent, 0.55); ctx.lineWidth = 1 / view.k;
      ctx.beginPath(); ctx.moveTo(sel.x, sel.y); ctx.lineTo(tx, ty); ctx.stroke();
      ctx.strokeStyle = rgba(P.grid, 0.65); ctx.setLineDash([2, 4]);
      ctx.beginPath(); ctx.arc(tx, ty, Rs, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);

      team.forEach((w, i) => {
        const a = -Math.PI / 2 + (i / team.length) * Math.PI * 2;
        const sx = tx + Math.cos(a) * Rs, sy = ty + Math.sin(a) * Rs;
        const col = w.status === 'alert' ? P.critical : (KIND_COL[w.kind] || P.stable);
        arm(sx, sy, sel.x, sel.y, 0.16, 1.2 + (w.weight || 0.3) * 5, 0.3, rgba(col, 0.28));
        glow(sx, sy, 12, col, 0.55);
        if (w.kind === 'human' && w.status === 'waiting') attentionRing(sx, sy, 3 / view.k, col, tSec);
        ctx.fillStyle = P.ink; ctx.beginPath(); ctx.arc(sx, sy, 2.8 / Math.pow(view.k, 0.4), 0, Math.PI * 2); ctx.fill();
        const text = (w.short || w.key) + (w.value ? ' ' + w.value : '');
        ctx.font = `600 ${10 / view.k}px ui-monospace, Menlo, monospace`;
        const tw = ctx.measureText(text).width;
        const labelR = Rs + 16 / view.k;
        const half = tw / 2 + 10 / view.k;
        let lx = tx + Math.cos(a) * labelR; const ly = ty + Math.sin(a) * labelR + 3 / view.k;
        if (view.k === 1) lx = Math.max(half, Math.min(W - half, lx));  // keep chips on-canvas at 100%
        // Watcher chip: rounded, tinted with the watcher's own colour over the map background
        // (not a flat panel rectangle, which reads as a white box in light mode).
        const px = 6 / view.k, ph = 16 / view.k, bx = lx - tw / 2 - px, by = ly - 11.5 / view.k, bw = tw + px * 2;
        const rr = ph / 2;
        chipHits.push({x0: bx, y0: by, x1: bx + bw, y1: by + ph, sx, sy, i});
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(bx, by, bw, ph, rr); else ctx.rect(bx, by, bw, ph);
        ctx.fillStyle = rgba(P.bg, theme === 'light' ? 0.82 : 0.78); ctx.fill();
        ctx.fillStyle = rgba(col, theme === 'light' ? 0.10 : 0.16); ctx.fill();
        ctx.lineWidth = 1 / view.k; ctx.strokeStyle = rgba(col, theme === 'light' ? 0.45 : 0.55); ctx.stroke();
        ctx.fillStyle = P.ink;
        ctx.fillText(text, lx, ly);
      });
    }
  }

  // Hit-testing & map gestures (mouse wheel, drag, pinch, tap, double-click)
  const ZMIN = 0.6, ZMAX = 6;
  function toWorld(sx, sy) {
    const cx = W / 2, cy = H / 2;
    return [(sx - cx - view.x) / view.k + cx, (sy - cy - view.y) / view.k + cy];
  }
  function zoomAt(sx, sy, k2) {
    // Keep the world point under (sx, sy) fixed while changing scale.
    k2 = Math.max(ZMIN, Math.min(ZMAX, k2));
    const cx = W / 2, cy = H / 2;
    const [wx, wy] = toWorld(sx, sy);
    view.k = k2;
    view.x = sx - cx - (wx - cx) * k2;
    view.y = sy - cy - (wy - cy) * k2;
    updateZoomLabel();
  }
  function updateZoomLabel() {
    const z = document.getElementById('zoom-reset');
    if (z) z.textContent = Math.round(view.k * 100) + '%';
  }
  function localXY(e) { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
  function selectAt(sx, sy, touch) {
    const [wx, wy] = toWorld(sx, sy);
    // Watcher chips (and their dots) around the selected item open that watcher's detail.
    // A direct hit on a dot wins over the chips drawn near it.
    const direct = nodes.find(n => Math.hypot(n.x - wx, n.y - wy) < (touch ? 12 : 8) / view.k);
    if (direct) { selectedId = direct.id; renderUI(); openEntity(direct.id); return; }
    const pad = (touch ? 10 : 4) / view.k;
    const chip = chipHits.find(c => (wx >= c.x0 - pad && wx <= c.x1 + pad && wy >= c.y0 - pad && wy <= c.y1 + pad) ||
                                    Math.hypot(wx - c.sx, wy - c.sy) < (touch ? 16 : 10) / view.k);
    if (chip && selectedId) { openEntity(selectedId, chip.i); return; }
    let best = null, bestD = (touch ? 36 : 22) / view.k;  // fingers need a larger target than a mouse
    nodes.forEach(n => {
      const d = Math.hypot(n.x - wx, n.y - wy);
      if (d < bestD) { best = n; bestD = d; }
    });
    if (best) { selectedId = best.id; renderUI(); openEntity(best.id); }
  }
  cv.addEventListener('wheel', (e) => {
    e.preventDefault();
    const [sx, sy] = localXY(e);
    const step = e.ctrlKey ? 0.01 : 0.0015;  // trackpad pinch arrives as ctrl+wheel
    zoomAt(sx, sy, view.k * Math.exp(-e.deltaY * step));
  }, {passive: false});
  const ptrs = new Map();
  let gesture = null;  // {moved, startX, startY, vx, vy, pinch:{d, mx, my, k, x, y}}
  function startPinch() {
    const [a, b] = [...ptrs.values()];
    gesture.pinch = {d: Math.hypot(a.x - b.x, a.y - b.y) || 1, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2};
    gesture.moved = true;
  }
  cv.addEventListener('pointerdown', (e) => {
    cv.setPointerCapture(e.pointerId);
    const [x, y] = localXY(e);
    ptrs.set(e.pointerId, {x, y});
    if (ptrs.size === 1) gesture = {moved: false, startX: x, startY: y, lastX: x, lastY: y, touch: e.pointerType !== 'mouse'};
    else if (ptrs.size === 2 && gesture) startPinch();
    cv.style.cursor = 'grabbing';
  });
  cv.addEventListener('pointermove', (e) => {
    if (!ptrs.has(e.pointerId) || !gesture) return;
    const [x, y] = localXY(e);
    ptrs.set(e.pointerId, {x, y});
    if (ptrs.size >= 2 && gesture.pinch) {
      const [a, b] = [...ptrs.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      view.x += mx - gesture.pinch.mx; view.y += my - gesture.pinch.my;  // pan with the midpoint
      zoomAt(mx, my, view.k * d / gesture.pinch.d);
      gesture.pinch = {d, mx, my};
      return;
    }
    if (!gesture.moved && Math.hypot(x - gesture.startX, y - gesture.startY) > (gesture.touch ? 10 : 4)) gesture.moved = true;
    if (gesture.moved) { view.x += x - gesture.lastX; view.y += y - gesture.lastY; }
    gesture.lastX = x; gesture.lastY = y;
  });
  function endPointer(e, cancelled) {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.delete(e.pointerId);
    if (ptrs.size === 1 && gesture) {
      // Rebase so the remaining finger keeps panning without a jump.
      const [p] = [...ptrs.values()];
      gesture.pinch = null; gesture.lastX = p.x; gesture.lastY = p.y;
      return;
    }
    if (ptrs.size === 0) {
      if (gesture && !gesture.moved && !cancelled) selectAt(gesture.startX, gesture.startY, gesture.touch);
      gesture = null;
      cv.style.cursor = '';
    }
  }
  cv.addEventListener('pointerup', (e) => endPointer(e, false));
  cv.addEventListener('pointercancel', (e) => endPointer(e, true));
  // Read-only geometry probe for browser verification (no state changes).
  window.__mcDebug = () => {
    const cx = W / 2, cy = H / 2;
    return {k: view.k, x: view.x, y: view.y, selected: selectedId,
      nodes: nodes.map(n => ({id: n.id, sx: (n.x - cx) * view.k + cx + view.x, sy: (n.y - cy) * view.k + cy + view.y}))};
  };
  cv.addEventListener('dblclick', () => { view = {k: 1, x: 0, y: 0}; updateZoomLabel(); });

  document.getElementById('btn-theme').onclick = () => {
    theme = theme === 'dark' ? 'light' : 'dark';
    renderUI();
  };
  document.getElementById('entity-search').oninput = (e) => {
    query = e.target.value || '';
    renderUI();
  };
  document.getElementById('zoom-in').onclick = () => zoomAt(W / 2, H / 2, view.k * 1.25);
  document.getElementById('zoom-out').onclick = () => zoomAt(W / 2, H / 2, view.k / 1.25);
  document.getElementById('zoom-reset').onclick = () => { view = {k: 1, x: 0, y: 0}; updateZoomLabel(); };

  // Deterministic Showcase Contract (window.__ready, window.__advance(ms), window.__done())
  const DWELL_MS = __DWELL_MS__;
  // Choreography phases: 0 = Overview + initial selection, 1..K = each sector scope + top entity in that sector, K+1 = return to active entity & approve
  const phases = [{scope: 'all', select: selectedId}];
  SPEC.sectors.forEach(s => {
    const topInSec = SPEC.entities.filter(e => e.sector === s.id).sort((a, b) => b.score - a.score)[0];
    phases.push({scope: s.id, select: topInSec ? topInSec.id : selectedId});
  });
  if (activeId) {
    phases.push({scope: 'all', select: activeId, approve: true});
  }
  let currentPhaseIdx = -1;
  let showcaseDone = false;

  function applyPhase(idx) {
    if (idx < 0 || idx >= phases.length) return;
    const p = phases[idx];
    scope = p.scope;
    selectedId = p.select;
    if (p.approve) {
      halted = false;
      gateOutcome = 'approved';
    }
    renderUI();
  }

  let manualRaf = true;
  window.__ready = false;
  window.__done = function() { return showcaseDone; };
  window.__advance = function(ms) {
    manualRaf = false;
    simClockMs += Number(ms) || 0;
    const pIdx = Math.floor(simClockMs / DWELL_MS);
    if (pIdx !== currentPhaseIdx) {
      currentPhaseIdx = pIdx;
      if (pIdx < phases.length) {
        applyPhase(pIdx);
      } else {
        showcaseDone = true;
      }
    }
    drawFrame(simClockMs / 1000.0);
  };

  (function attentionBuzz() {
    if (!('vibrate' in navigator)) return;
    const key = 'mc-seen-attention:' + (SPEC.title || '');
    const crit = SPEC.entities.filter(e => e.stage === 'critical').map(e => e.id);
    let seen = [];
    try { seen = JSON.parse(localStorage.getItem(key) || '[]'); } catch (_) {}
    const fresh = crit.filter(id => !seen.includes(id));
    if (!fresh.length) return;
    window.addEventListener('pointerdown', () => {
      try { navigator.vibrate([60, 80, 60]); localStorage.setItem(key, JSON.stringify(crit)); } catch (_) {}
    }, { once: true });
  })();

  resize();
  (function renderBrief() {
    const b = SPEC.brief, host = document.getElementById('brief');
    if (!b || (!b.lead && !b.items.length)) return;
    host.hidden = false;
    host.closest('.shell').classList.add('has-brief');
    if (b.lead) { const d = document.createElement('div'); d.className = 'brief-lead'; d.setAttribute('role', 'alert'); d.textContent = b.lead; host.appendChild(d); }
    if (!b.items.length) return;
    const grid = document.createElement('div'); grid.className = 'brief-items'; host.appendChild(grid);
    b.items.forEach(it => {
      const el = document.createElement(it.entity ? 'button' : 'div');
      if (it.entity) { el.type = 'button'; el.onclick = () => { selectedId = it.entity; renderUI(); openEntity(it.entity); }; }
      el.className = 'brief-item' + (it.tone ? ' ' + it.tone : '');
      const lb = document.createElement('b'); lb.textContent = it.label; el.appendChild(lb);
      if (it.text) { const t = document.createElement('span'); t.textContent = it.text; el.appendChild(t); }
      if (it.lines.length) { const ol = document.createElement('ol'); it.lines.forEach(x => { const li = document.createElement('li'); li.textContent = x; ol.appendChild(li); }); el.appendChild(ol); }
      grid.appendChild(el);
    });
  })();
  resize();
  renderUI();
  drawFrame(0);
  window.__ready = true;

  function loop(now) {
    if (manualRaf) {
      drawFrame(now / 1000.0);
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
})();
</script>
<aside class="mc-ask" id="mc-ask" aria-label="Ask about this dashboard" aria-hidden="true">
  <div class="mc-ask-h"><b>Ask</b><small id="mc-ask-state">off</small>
    <button type="button" class="mc-x btn" id="mc-ask-close" aria-label="Close Ask">×</button></div>
  <div class="mc-ask-log" id="mc-ask-log" aria-live="polite"></div>
  <form class="mc-ask-f" id="mc-ask-form">
    <textarea id="mc-ask-q" aria-label="Your question" placeholder="Ask about this account…" disabled></textarea>
    <div class="mc-ask-row">
      <button type="button" class="btn" id="mc-ask-sel" disabled>Ask about selected item</button>
      <button type="submit" class="mc-send" id="mc-ask-send" disabled>Send</button>
    </div>
  </form>
</aside>
<script>
(function () {
  // Ask pane: same-origin POST /ask on the local `mission-control serve` server. Opened as a
  // file (or without the server) it stays visible but disabled with one line on how to start it.
  const pane = document.getElementById('mc-ask'), log = document.getElementById('mc-ask-log');
  const q = document.getElementById('mc-ask-q'), send = document.getElementById('mc-ask-send');
  const selBtn = document.getElementById('mc-ask-sel'), state = document.getElementById('mc-ask-state');
  const btn = document.getElementById('btn-ask');
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // Only http(s) and repo-relative paths become links; relative paths open read-only via /src.
  const href = (u) => {
    u = String(u || '').trim();
    if (/^https?:\/\//i.test(u)) return u;
    if (/^[a-z][a-z0-9+.-]*:/i.test(u) || u.startsWith('//') || u.startsWith('/') || !u) return null;
    return '/src?p=' + encodeURIComponent(u.replace(/^\.\//, ''));
  };
  const fmt = (t) => esc(t).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/(^|[^*\w])\*([^*\s][^*]*?)\*/g, '$1<em>$2</em>');
  function inline(t) {
    return String(t).split(/(`[^`]+`)/).map(seg => {
      if (/^`[^`]+`$/.test(seg)) return '<code>' + esc(seg.slice(1, -1)) + '</code>';
      let out = '', last = 0, m;
      const re = /\[([^\]]+)\]\(([^)\s]+)\)|(https?:\/\/[^\s<>()]*[^\s<>().,;:!?'"])/g;
      while ((m = re.exec(seg))) {
        out += fmt(seg.slice(last, m.index));
        const h = href(m[2] || m[3]);
        out += h ? `<a href="${esc(h)}" target="_blank" rel="noopener noreferrer">${fmt(m[1] || m[3])}</a>` : fmt(m[0]);
        last = re.lastIndex;
      }
      return out + fmt(seg.slice(last));
    }).join('');
  }
  // Sanitized markdown: everything is escaped first; only our own tags are emitted.
  function md(src) {
    const lines = String(src || '').replace(/\r/g, '').split('\n');
    let html = '', list = null, para = [], i = 0;
    const flush = () => { if (para.length) { html += '<p>' + inline(para.join(' ')) + '</p>'; para = []; } };
    const endList = () => { if (list) { html += `</${list}>`; list = null; } };
    while (i < lines.length) {
      const l = lines[i];
      if (/^```/.test(l)) { flush(); endList(); const buf = []; i++; while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]); html += '<pre><code>' + esc(buf.join('\n')) + '</code></pre>'; i++; continue; }
      if (/^\s*\|.*\|\s*$/.test(l)) { flush(); endList(); const rows = []; while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
        html += '<table>' + rows.filter(r => !/^\s*\|[\s:|-]+\|\s*$/.test(r)).map((r, k) => '<tr>' + r.trim().slice(1, -1).split('|').map(c => k ? `<td>${inline(c.trim())}</td>` : `<th>${inline(c.trim())}</th>`).join('') + '</tr>').join('') + '</table>'; continue; }
      let m;
      if ((m = /^#{1,6}\s+(.*)$/.exec(l))) { flush(); endList(); html += '<h4>' + inline(m[1]) + '</h4>'; i++; continue; }
      if ((m = /^\s*([-*•]|\d+[.)])\s+(.*)$/.exec(l))) { flush(); const t = /\d/.test(m[1]) ? 'ol' : 'ul'; if (list !== t) { endList(); html += `<${t}>`; list = t; } html += '<li>' + inline(m[2]) + '</li>'; i++; continue; }
      if (!l.trim()) { flush(); endList(); i++; continue; }
      endList(); para.push(l.trim()); i++;
    }
    flush(); endList();
    return html;
  }
  window.__mcAskMd = md;  // exposed for tests
  function add(cls, html) { const d = document.createElement('div'); d.className = 'mc-msg ' + cls; d.innerHTML = html; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; }
  function open(v) {
    pane.classList.toggle('open', v); document.body.classList.toggle('ask-open', v);
    pane.setAttribute('aria-hidden', v ? 'false' : 'true'); btn.setAttribute('aria-expanded', v ? 'true' : 'false');
    btn.classList.toggle('active', v); window.dispatchEvent(new Event('resize'));
    if (v && !q.disabled) q.focus({preventScroll: true});
  }
  btn.onclick = () => open(!pane.classList.contains('open'));
  document.getElementById('mc-ask-close').onclick = () => open(false);
  let ready = false, busy = false;
  function setReady(on, note) {
    ready = on; q.disabled = send.disabled = selBtn.disabled = !on;
    state.textContent = on ? (note || 'ready') : 'off';
  }
  function offNote(extra) {
    add('mc-ask-off', 'Ask is off: this page was opened as a file. Start it with <code>creator.py mission-control serve</code> (see the README next to this page) and open the URL it prints.' + (extra ? '<br>' + esc(extra) : ''));
  }
  async function ask(question) {
    if (!ready || busy || !question.trim()) return;
    busy = true; send.disabled = selBtn.disabled = true;
    add('q', esc(question));
    const t0 = Date.now(), th = add('a mc-thinking', 'Thinking…');
    const tick = setInterval(() => { th.textContent = 'Thinking… ' + Math.round((Date.now() - t0) / 1000) + 's (reading the record' + ' and WorkIQ if needed)'; }, 1000);
    try {
      const sel = window.__mcSelected ? window.__mcSelected() : null;
      const r = await fetch('/ask', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-MC-Ask': '1'},
        body: JSON.stringify({question, selected: sel})});
      const j = await r.json().catch(() => ({error: 'Bad reply (HTTP ' + r.status + ')'}));
      th.remove();
      if (!r.ok || j.error) { add('err', esc(j.error || ('HTTP ' + r.status))); return; }
      let html = '<span class="mc-who">AI · GitHub Copilot' + (j.seconds ? ' · ' + esc(j.seconds) + 's' : '') + '</span>' + md(j.answer);
      const chips = (j.sources || []).map(s => { const h = href(s.href); return h ? `<a href="${esc(h)}" target="_blank" rel="noopener noreferrer">${esc(s.label)}</a>` : `<span>${esc(s.label)}</span>`; });
      (j.tools || []).forEach(t => chips.push(`<span title="${esc(t.args || '')}">used ${esc(t.name)}</span>`));
      if (chips.length) html += '<div class="mc-src">' + chips.join('') + '</div>';
      add('a', html);
    } catch (e) { th.remove(); add('err', 'Ask failed: ' + esc(e.message || e)); }
    finally { clearInterval(tick); busy = false; send.disabled = selBtn.disabled = !ready; }
  }
  document.getElementById('mc-ask-form').onsubmit = (e) => { e.preventDefault(); const v = q.value; q.value = ''; ask(v); };
  q.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); document.getElementById('mc-ask-form').requestSubmit(); } });
  selBtn.onclick = () => {
    const s = window.__mcSelected && window.__mcSelected();
    if (!s) { add('mc-ask-off', 'Select an item on the map or list first.'); return; }
    ask(`Tell me about "${s.label}" (${s.id}): what it is, why it matters for this account, and what I should do. Cite sources.`);
  };
  if (!/^https?:$/.test(location.protocol)) { setReady(false); offNote(); return; }
  fetch('/ask/health', {headers: {'X-MC-Ask': '1'}}).then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
    .then(j => { setReady(true, j.label || 'ready'); add('mc-ask-off', esc(j.intro || 'Ask about this account. Answers cite the record or WorkIQ; "not in record" means nothing was found.'));
      if (window.matchMedia('(min-width: 1280px)').matches) open(true); })
    .catch(() => { setReady(false); offNote('The Ask server did not answer at this address.'); });
})();
</script>
</body>
</html>
"""


def _esc_html(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _style_css(style: dict) -> str:
    from creator_tools import styles
    return (
        "/* style: " + style["name"] + " (" + style["source"] + ") */\n"
        + styles.style_css(style)
        + "html, body { font-family: var(--mc-font); }\n"
        + ".title-badge, .scope-meta, .stat-num, .live-pill, .persona-metric, .metric-tile, .map-hud-tl, .map-legend { font-family: var(--mc-mono); }\n"
        + ".card, .scope-bar, .map-stage { border-radius: calc(var(--mc-radius) + 2px); }\n"
        + ".btn, .entity-item, .metric-tile, .watcher-row, .search-top input { border-radius: var(--mc-radius); }\n"
        + ".map-hud-tl, .map-legend { background: color-mix(in srgb, var(--mc-surface) 70%, transparent); }\n"
        + ".brand-icon { background: color-mix(in srgb, var(--mc-accent) 16%, transparent); }\n"
        + ".btn.active { background: color-mix(in srgb, var(--mc-accent) 12%, transparent); }\n"
        + ".pill-warn { background: color-mix(in srgb, var(--mc-atRisk) 14%, transparent); }\n"
    )


def _style_js(style: dict) -> str:
    pal = {m: {k: v for k, v in p.items()} for m, p in style["palettes"].items()}
    return ("Object.assign(PALETTES.dark, " + json.dumps(pal["dark"]) + "); "
            "Object.assign(PALETTES.light, " + json.dumps(pal["light"]) + ");")


def render_html(spec: dict, dwell_ms: float = 2200.0, style: dict | None = None,
                style_theme: str | None = None) -> str:
    norm = validate_spec(spec)
    html = (
        _HTML_TEMPLATE
        .replace("__DEFAULT_THEME__", norm["default_theme"])
        .replace("__TITLE__", _esc_html(norm["title"]))
        .replace("__BADGE__", _esc_html(norm["badge"]))
        .replace("__BANNER__", _esc_html(norm["banner"]))
        .replace("__SPEC_JSON__", json.dumps(norm).replace("</", "<\\/"))
        .replace("__DWELL_MS__", str(max(250, int(round(float(dwell_ms))))))
    )
    if style:
        theme = style_theme or norm["default_theme"]
        html = (html.replace('data-theme="' + norm["default_theme"] + '"', 'data-theme="' + theme + '"', 1)
                .replace("/*__STYLE_CSS__*/", _style_css(style))
                .replace("/*__STYLE_JS__*/", _style_js(style)))
    else:
        html = html.replace("/*__STYLE_CSS__*/", "").replace("/*__STYLE_JS__*/", "")
    return html


def run(action: str, source: str | Path, output: str | Path | None = None, *,
        dwell_ms: float = 2200.0, video_output: str | Path | None = None,
        style_name: str | None = None, theme: str | None = None,
        log=print) -> dict:
    if action not in ("validate", "render"):
        raise ValueError("Unsupported mission-control action; choose validate or render")
    src = Path(source).expanduser().resolve()
    raw = src.read_bytes()
    spec = json.loads(raw)
    norm = validate_spec(spec)
    if action == "validate":
        return {
            "ok": True,
            "input": str(src),
            "title": norm["title"],
            "sectors": len(norm["sectors"]),
            "entities": len(norm["entities"]),
            "beats": len(norm["agent"]["beats"]),
            "warnings": lint_spec(norm),
        }
    if output is None:
        raise ValueError("render requires --output")
    target = Path(output).expanduser().resolve()
    if target.suffix.lower() != ".html":
        raise ValueError("Mission Control output must be .html")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Output exists; select a new path: {target}")
    from creator_tools import styles
    style = styles.build_style(style_name or "mission-control")
    if theme not in (None, "dark", "light"):
        raise ValueError("--theme must be dark or light")
    # Precedence: explicit --theme > style's native mode > spec default_theme.
    style_theme = theme or (style["default_theme"] if style_name else norm["default_theme"])
    html_bytes = render_html(norm, dwell_ms=dwell_ms, style=style or None,
                             style_theme=style_theme).encode("utf-8")
    if theme and not style:
        html_bytes = html_bytes.replace(('data-theme="' + norm["default_theme"] + '"').encode(),
                                        ('data-theme="' + theme + '"').encode(), 1)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as f:
        f.write(html_bytes)
    result = {
        "ok": True,
        "input": str(src),
        "output": str(target),
        "title": norm["title"],
        "sectors": len(norm["sectors"]),
        "entities": len(norm["entities"]),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "output_sha256": hashlib.sha256(html_bytes).hexdigest(),
        "style": style["name"],
        "theme": style_theme or norm["default_theme"],
        "warnings": lint_spec(norm),
    }
    if video_output:
        from creator_tools import showcase
        result["video"] = showcase.record(target, video_output, log=log)
    return result
