"""Pipeline Control: a CI/CD pipeline monitoring page from one run log.

Input: a typed JSON spec (stages, a run log, an optional live snapshot, the agent's
finding). Output: one offline HTML page with
  * a live Flow line (stages left to right, run dots, queues, failed stage, agent
    checkpoint) and the agent's approval panel, and
  * "What changed" insight cards in the data-story pattern: every figure derived
    in Python from the same run log, a fixed baseline to measure improvement
    against, and an "Explain this figure" disclosure per card.

Rules kept here:
  * Numbers are derived, never typed in: headlines, deltas, charts and the agent's
    evidence lines all come from the run log.
  * Cost uses an explicit per-minute rate from the spec, shown in Explain as an input.
  * The baseline is fixed (``baseline.until``) so a slow week cannot become the new
    normal; without it the page says it compares to the previous 7 days.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import statistics
from pathlib import Path

from creator_tools import styles

LIVE_STATES = ("running", "waiting", "failed", "done")
STAGE_STATES = ("ok", "slow", "failed")
BEATS = ["Change", "Notice", "Decide", "Approve", "Act", "Adapt", "Prove"]


# ---------------- validation ----------------
def _date(s, where):
    try:
        return dt.date.fromisoformat(str(s))
    except ValueError:
        raise ValueError(f"{where}: date must be YYYY-MM-DD, got {s!r}") from None


def _label(d: dt.date) -> str:
    return d.strftime("%b ") + str(d.day)


def validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise ValueError("Pipeline Control spec must be a JSON object")
    pipeline = str(spec.get("pipeline") or "").strip()
    if not pipeline:
        raise ValueError("spec.pipeline is required")
    stages = spec.get("stages")
    if not isinstance(stages, list) or len(stages) < 2:
        raise ValueError("spec.stages needs at least 2 stages")
    ids = []
    for i, s in enumerate(stages):
        if not isinstance(s, dict) or not str(s.get("id") or "").strip() or not str(s.get("name") or "").strip():
            raise ValueError(f"stages[{i}] needs id and name")
        if s["id"] in ids:
            raise ValueError(f"duplicate stage id {s['id']!r}")
        ids.append(s["id"])
    rate = spec.get("runner_rate_usd_per_min")
    if not isinstance(rate, (int, float)) or isinstance(rate, bool) or rate < 0:
        raise ValueError("runner_rate_usd_per_min must be a non-negative number")
    runs = spec.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("spec.runs (the run log) is required")
    norm_runs = []
    for i, r in enumerate(runs):
        where = f"runs[{i}]"
        if not isinstance(r, dict):
            raise ValueError(f"{where} must be an object")
        d = _date(r.get("date"), where)
        mins = r.get("stage_minutes")
        if not isinstance(mins, dict) or not mins:
            raise ValueError(f"{where}.stage_minutes is required")
        for k, v in mins.items():
            if k not in ids:
                raise ValueError(f"{where}.stage_minutes: unknown stage {k!r}")
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                raise ValueError(f"{where}.stage_minutes.{k} must be a non-negative number")
        status = r.get("status")
        if status not in ("passed", "failed"):
            raise ValueError(f"{where}.status must be passed or failed")
        fs = r.get("failed_stage")
        if status == "failed" and fs not in ids:
            raise ValueError(f"{where}.failed_stage must name a stage when status is failed")
        norm_runs.append({"id": str(r.get("id") or f"run-{i}"), "date": d, "status": status,
                          "failed_stage": fs if status == "failed" else None,
                          "first_try": bool(r.get("first_try", status == "passed")),
                          "stage_minutes": {k: float(v) for k, v in mins.items()}})
    days = sorted({r["date"] for r in norm_runs})
    if len(days) < 2:
        raise ValueError("run log must cover at least 2 days")

    baseline = spec.get("baseline") or {}
    until = _date(baseline["until"], "baseline.until") if baseline.get("until") else None
    if until and not any(d <= until for d in days):
        raise ValueError("baseline.until is before the first day of the run log")
    if until and until >= days[-1]:
        raise ValueError("baseline.until must be before the latest day")

    live = spec.get("live") or {}
    stage_state = live.get("stage_state") or {}
    for k, v in stage_state.items():
        if k not in ids or v not in STAGE_STATES:
            raise ValueError(f"live.stage_state.{k}: unknown stage or state {v!r}")
    live_runs = []
    for i, r in enumerate(live.get("runs") or []):
        if r.get("state") not in LIVE_STATES:
            raise ValueError(f"live.runs[{i}].state must be one of {LIVE_STATES}")
        si = r.get("stage")
        if si not in ids:
            raise ValueError(f"live.runs[{i}].stage must be a stage id")
        p = float(r.get("progress", 0))
        if not 0 <= p <= 1:
            raise ValueError(f"live.runs[{i}].progress must be 0..1")
        live_runs.append({"id": str(r.get("id") or f"live-{i}"), "stage": ids.index(si), "p": p,
                          "state": r["state"], "msg": str(r.get("message") or "")})

    agent = spec.get("agent") or {}
    if agent and agent.get("stage") not in ids:
        raise ValueError("agent.stage must be a stage id")
    cost_stages = spec.get("cost_stages")
    if cost_stages is not None and (not isinstance(cost_stages, list) or set(cost_stages) - set(ids)):
        raise ValueError("cost_stages must list stage ids (stages that use paid runner minutes)")
    titles = spec.get("figure_titles") or {}
    bad = set(titles) - {"stage", "cost", "lead", "pass", "failed"}
    if bad:
        raise ValueError(f"figure_titles: unknown figure ids {sorted(bad)}")

    return {
        "pipeline": pipeline,
        "title": str(spec.get("title") or "Pipeline Control").strip(),
        "subtitle": str(spec.get("subtitle") or "CI/CD").strip(),
        "data_label": str(spec.get("data_label") or "").strip(),
        "style": str(spec.get("style") or "claude"),
        "rate": float(rate),
        "rate_note": str(spec.get("rate_note") or "per runner minute"),
        "stages": [{"id": s["id"], "name": str(s["name"]).strip()} for s in stages],
        "runs": norm_runs, "days": days,
        "baseline_until": until, "baseline_label": str(baseline.get("label") or "").strip(),
        "live": {"stage_state": stage_state, "runs": live_runs},
        "cost_stages": cost_stages,
        "figure_titles": {k: str(v).strip()[:40] for k, v in titles.items() if str(v).strip()},
        "agent": {"stage": agent.get("stage"), "finding": str(agent.get("finding") or ""),
                  "action": str(agent.get("action") or ""),
                  "badge": str(agent.get("badge") or "Agent: fix drafted")[:40],
                  "badge_sub": str(agent.get("badge_sub") or "waiting for your approval")[:48],
                  "evidence": [str(e) for e in agent.get("evidence") or []]} if agent else None,
    }


# ---------------- derivation ----------------
def _r(v, n):
    return round(float(v), n)


def derive(norm: dict) -> dict:
    stages, runs, days = norm["stages"], norm["runs"], norm["days"]
    ids = [s["id"] for s in stages]
    by = {d: [r for r in runs if r["date"] == d] for d in days}
    until = norm["baseline_until"]
    base_days = [d for d in days if until and d <= until]
    rate = norm["rate"]

    paid = set(norm.get("cost_stages") or ids)

    def runner_min(r):  # paid runner minutes only (a person's wait is not compute)
        return sum(v for k, v in r["stage_minutes"].items() if k in paid)

    def daily(fn):
        return [fn(by[d]) for d in days]

    def compare(values, n):
        latest = _r(values[-1], n)
        if until:
            ref = _r(statistics.median(v for d, v in zip(days, values) if d <= until), n)
            label = f"up to {_label(until)}" + (f", before {norm['baseline_label']}" if norm["baseline_label"] else "")
            mode = "fixed"
        else:
            ref = _r(statistics.median(values[-8:-1]), n)
            label, mode = "previous 7 days", "rolling"
        return latest, ref, _r(latest - ref, n), label, mode

    # Per-stage medians: baseline vs latest day (also feeds the flow line).
    # Same method as the figures: median of daily medians over the baseline days,
    # so the flow line, the agent's evidence and the cards always agree.
    ref_days = base_days or days[-8:-1]
    stage_stats = []
    for s in stages:
        def med(rows, sid=s["id"]):
            v = [r["stage_minutes"][sid] for r in rows if sid in r["stage_minutes"]]
            return statistics.median(v) if v else 0.0
        reached = sum(1 for r in runs if s["id"] in r["stage_minutes"])
        if not reached:  # missing is not zero: no run ever reached this stage
            stage_stats.append({"id": s["id"], "base": None, "latest": None, "reached": 0})
            continue
        base = statistics.median(med(by[d]) for d in ref_days)
        stage_stats.append({"id": s["id"], "base": _r(base, 1), "latest": _r(med(by[days[-1]]), 1), "reached": reached})
    focus = max((x for x in stage_stats if x["reached"]), key=lambda x: (x["latest"] - x["base"]))
    focus_name = next(s["name"] for s in stages if s["id"] == focus["id"])

    figs = []

    def add(fid, title, unit, values, n, better, calc, headline):
        latest, ref, delta, label, mode = compare(values, n)
        worse = (delta > 0) if better == "lower" else (delta < 0)
        tol = 0.03 * max(abs(ref), 1e-9)
        title = norm.get("figure_titles", {}).get(fid, title)
        f = {"id": fid, "title": title, "unit": unit, "values": [_r(v, n) for v in values], "latest": latest,
             "ref": ref, "delta": delta, "refLabel": label, "refMode": mode,
             "status": "same" if abs(delta) <= tol else ("worse" if worse else "better"), "calc": calc,
             "latestRuns": len(by[days[-1]])}
        f["headline"] = headline(f)
        figs.append(f)
        return f

    # Only runs that reached the stage; a run that failed earlier has no time there (not zero).
    fstage = daily(lambda rows: statistics.median([r["stage_minutes"][focus["id"]] for r in rows
                                                   if focus["id"] in r["stage_minutes"]] or [0]))
    add("stage", f"{focus_name} stage time", "min", fstage, 1, "lower",
        f"median(stage_minutes.{focus['id']}) per day over runs that reached the stage; stage chosen as the largest rise vs baseline",
        lambda f: f"{focus_name} takes {f['latest']} min, against {f['ref']} min {f['refLabel']}.")
    cost = add("cost", "Cost per run", "USD", daily(lambda rows: statistics.median([runner_min(r) * rate for r in rows])), 3,
               "lower", f"median(runner minutes × ${rate}/min) per day; runner minutes = sum of the run's " + ("paid stages (" + ", ".join(sorted(paid)) + ")" if norm.get("cost_stages") else "stage minutes"),
               lambda f: f"{'A session' if 'session' in f['title'].lower() else 'A run'} costs ${f['latest']:.3f}, against ${f['ref']:.3f} {f['refLabel']}.")
    add("lead", "Commit to production", "min",
        daily(lambda rows: statistics.median([sum(r["stage_minutes"].values()) for r in rows if r["status"] == "passed"] or [0])), 1,
        "lower", "median(sum of stage minutes) per day, passed runs only",
        lambda f: f"{f['title']} takes {f['latest']} min, against {f['ref']} min {f['refLabel']}.")
    add("pass", "Runs that pass first time", "%",
        daily(lambda rows: 100 * sum(r["first_try"] for r in rows) / len(rows)), 1, "higher",
        "100 × count(first_try) / count(runs) per day",
        lambda f: f"{f['latest']}% of runs pass first time, against {f['ref']}% {f['refLabel']}.")
    add("failed", "Failed runs", "runs", daily(lambda rows: sum(r["status"] == "failed" for r in rows)), 0, "lower",
        "count(status = failed) per day",
        lambda f: f"{int(f['latest'])} runs failed on the latest day, against {int(f['ref'])} {f['refLabel']}.")

    # Money, in plain terms: extra spend per week at today's cost and today's volume.
    per_day_runs = len(by[days[-1]])
    weekly_extra = _r((cost["latest"] - cost["ref"]) * per_day_runs * 7, 2)
    cost["weeklyExtra"] = weekly_extra
    cost["runsPerDay"] = per_day_runs
    if cost["status"] == "worse":
        cost["headline"] += f" At today's volume that is about ${weekly_extra:.2f} more per week."
    elif cost["status"] == "better":
        cost["headline"] += f" At today's volume that saves about ${-weekly_extra:.2f} per week."

    log_digest = hashlib.sha256(json.dumps(
        [{**r, "date": r["date"].isoformat()} for r in runs], sort_keys=True).encode()).hexdigest()
    evidence = [f"{focus_name} median {focus['base']:.1f} min {figs[0]['refLabel']}, {focus['latest']:.1f} min on {_label(days[-1])}",
                f"Cost per run ${cost['ref']:.3f} → ${cost['latest']:.3f}"]

    # Live snapshot: queues derived from waiting runs (waiting at stage i queue for stage i+1).
    live = norm["live"]
    queue = {}
    for r in live["runs"]:
        if r["state"] == "waiting" and r["stage"] + 1 < len(stages):
            sid = stages[r["stage"] + 1]["id"]
            queue[sid] = queue.get(sid, 0) + 1
    if queue.get(focus["id"]):
        evidence.append(f"{queue[focus['id']]} runs waiting for {focus_name}")

    # ---- Run waterfall: slowest passed run on the latest day vs baseline stage medians ----
    latest_passed = [r for r in by[days[-1]] if r["status"] == "passed"] or by[days[-1]]
    slow_run = max(latest_passed, key=runner_min)
    wf_rows = []
    for s, st in zip(stages, stage_stats):
        a = slow_run["stage_minutes"].get(s["id"])
        wf_rows.append({"id": s["id"], "name": s["name"], "actual": _r(a, 1) if a is not None else None, "base": st["base"]})
    worst = max((w for w in wf_rows if w["actual"] is not None), key=lambda w: w["actual"] - w["base"])
    tot_a = _r(sum(w["actual"] or 0 for w in wf_rows), 1)
    tot_b = _r(sum(w["base"] for w in wf_rows if w["actual"] is not None), 1)
    waterfall = {"run": slow_run["id"], "date": _label(slow_run["date"]), "rows": wf_rows, "total": tot_a, "baseTotal": tot_b,
                 "headline": f"Run {slow_run['id']} took {tot_a} min against {tot_b} min of baseline stage medians "
                             f"(+{_r(tot_a - tot_b, 1)} min). {worst['name']} alone is "
                             f"+{_r(worst['actual'] - worst['base'], 1)} min.",
                 "how": "Slowest passed run on the latest day; each bar is that run's stage time, each dashed box the stage's baseline median."}

    # ---- Volume flow: runs reaching each stage in the last 7 days, and where they stopped ----
    def funnel(window):
        rows = [r for r in runs if r["date"] in window]
        reach = [sum(1 for r in rows if s["id"] in r["stage_minutes"]) for s in stages]
        drop = [sum(1 for r in rows if r["failed_stage"] == s["id"]) for s in stages]
        return reach, drop
    win, prev = days[-7:], days[-14:-7]
    reach, drop = funnel(win)
    _, drop_prev = funnel(prev) if prev else (None, [0] * len(stages))
    jump = max(range(len(stages)), key=lambda i: drop[i] - drop_prev[i])
    reach_prev = funnel(prev)[0] if prev else [0] * len(stages)
    ids_ = [s["id"] for s in stages]
    win_runs = [{"id": r["id"], "day": _label(r["date"]),
                 "stop": ids_.index(r["failed_stage"]) if r["failed_stage"] else None}
                for r in runs if r["date"] in win]
    volume = {"window": f"{_label(win[0])} – {_label(win[-1])}", "reach": reach, "drop": drop, "dropPrev": drop_prev,
              "reachPrev": reach_prev, "runs": win_runs,
              "prevWindow": f"{_label(prev[0])} – {_label(prev[-1])}" if prev else "",
              "headline": f"{reach[0]} runs started; {reach[-1]} reached {stages[-1]['name']}. "
                          + (f"Most new failures are at {stages[jump]['name']}: {drop[jump]} this week against {drop_prev[jump]} the week before."
                             if prev and drop[jump] > drop_prev[jump] else "Failures per stage are not higher than the week before."),
              "how": "reach = runs with time at the stage; drop = runs whose failed_stage is that stage; last 7 days of the log vs the 7 before."}

    # ---- Heat grid: stage × day, time vs baseline (colour) and failures (dot) ----
    grid = []
    for s, st in zip(stages, stage_stats):
        cells = []
        for d in days:
            v = [r["stage_minutes"][s["id"]] for r in by[d] if s["id"] in r["stage_minutes"]]
            med = statistics.median(v) if v else None
            ratio = _r(med / st["base"], 2) if med is not None and st["base"] > 0 else None
            fails = sum(1 for r in by[d] if r["failed_stage"] == s["id"])
            cells.append({"ratio": ratio, "median": _r(med, 1) if med is not None else None, "runs": len(v), "fails": fails})
        grid.append({"id": s["id"], "name": s["name"], "cells": cells})
    first_slow = next((i for i, c in enumerate(next(g for g in grid if g["id"] == focus["id"])["cells"])
                       if c["ratio"] and c["ratio"] >= 1.5), None)
    fcells = next(g for g in grid if g["id"] == focus["id"])["cells"]
    since = [c["ratio"] for c in fcells[first_slow:] if c["ratio"]] if first_slow is not None else []
    others_max = max((c["ratio"] or 0) for g in grid if g["id"] != focus["id"] for c in g["cells"][first_slow or 0:])
    heat = {"rows": grid, "changeDay": first_slow,
            "headline": (f"{focus_name} has taken {min(since)}–{max(since)}× its baseline time every day since "
                         f"{_label(days[first_slow])}; no other stage went above {others_max}×.")
                        if first_slow is not None else "No stage is running 1.5× its baseline.",
            "how": "Colour = that day's stage median ÷ baseline median (under 1.25× normal, 1.25–2× slow, 2× or more very slow). Number = failed runs at the stage that day."}

    return {
        "waterfall": waterfall, "volume": volume, "heat": heat,
        "pipeline": norm["pipeline"], "stages": [{**s, **{k: v for k, v in st.items() if k != "id"}}
                                                 for s, st in zip(stages, stage_stats)],
        "stageState": live["stage_state"], "queue": queue, "runs": live["runs"],
        "days": [_label(d) for d in days], "figures": figs, "focus": focus["id"],
        "failStages": sorted({r["failed_stage"] for r in runs if r.get("failed_stage")}),
        "source": {"rows": len(runs), "period": f"{days[0].isoformat()} – {days[-1].isoformat()}, daily",
                   "sha256": log_digest, "rate": rate, "rateNote": norm["rate_note"],
                   "baseline": figs[0]["refLabel"], "mode": figs[0]["refMode"]},
        "agent": norm["agent"], "derivedEvidence": evidence,
    }


# ---------------- rendering ----------------
CSS = r"""
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--mc-surface); color: var(--mc-ink); font: 14px/1.5 var(--mc-font); }
.top { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 18px; padding: 12px 20px; background: var(--mc-panel); border-bottom: 1px solid var(--mc-border); }
.brand { font-weight: 700; font-size: 16px; }
.brand small { display: block; font-weight: 500; font-size: 12px; color: var(--mc-muted); }
.spacer { flex: 1; }
.pill { font-size: 12px; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--mc-atRisk); color: var(--mc-atRisk); }
button { font: inherit; cursor: pointer; padding: 6px 12px; border-radius: var(--mc-radius); border: 1px solid var(--mc-border); background: var(--mc-raised); color: var(--mc-ink); }
button:focus-visible, a:focus-visible, summary:focus-visible, [tabindex]:focus-visible { outline: 2px solid var(--mc-accent); outline-offset: 2px; }
main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; padding: 16px 20px 28px; align-items: start; }
.card { background: var(--mc-panel); border: 1px solid var(--mc-border); border-radius: calc(var(--mc-radius) + 2px); padding: 16px 18px; }
h1 { font-size: 20px; margin: 0 0 2px; }
.q { color: var(--mc-muted); margin: 0 0 12px; }
.vizwrap { overflow-x: auto; }
.views { display: flex; flex-wrap: wrap; gap: 6px; }
.views a { text-decoration: none; color: var(--mc-ink); padding: 6px 12px; border: 1px solid var(--mc-border); border-radius: var(--mc-radius); background: var(--mc-raised); font-size: 13px; white-space: nowrap; }
.views a[aria-current="page"] { border-color: var(--mc-accent); color: var(--mc-accent); background: color-mix(in srgb, var(--mc-accent) 12%, var(--mc-panel)); font-weight: 600; }
[data-view-panel][hidden] { display: none !important; }
.subviews { display: flex; flex-wrap: wrap; gap: 4px; margin: 0 0 12px; }
.subviews a { text-decoration: none; color: var(--mc-muted); font-size: 12.5px; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--mc-border); white-space: nowrap; }
.subviews a[aria-current="true"] { color: var(--mc-ink); border-color: var(--mc-accent); font-weight: 600; background: color-mix(in srgb, var(--mc-accent) 10%, var(--mc-panel)); }
.how { font-size: 12.5px; color: var(--mc-muted); margin: 10px 0 0; }
.vhead { font-size: 15px; font-weight: 600; margin: 0 0 10px; }
.swipe { display: none; margin: 4px 0 0; font-size: 12.5px; color: var(--mc-muted); }
.swipe.on { display: block; }
svg text { font-family: var(--mc-font); }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12.5px; color: var(--mc-muted); margin-top: 10px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: -1px; }
.detail { margin-top: 12px; padding: 10px 12px; border-radius: var(--mc-radius); background: var(--mc-surface); border: 1px solid var(--mc-border); font-size: 13px; min-height: 44px; }
aside h2 { font-size: 13px; margin: 0 0 8px; color: var(--mc-muted); font-weight: 600; }
.beats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin-bottom: 14px; }
.beats span { font-size: 11.5px; text-align: center; padding: 5px 0; border-radius: 4px; background: var(--mc-surface); color: var(--mc-muted); border: 1px solid var(--mc-border); }
.beats span.done { color: var(--mc-stable); border-color: color-mix(in srgb, var(--mc-stable) 40%, var(--mc-border)); }
.beats span.now { color: var(--mc-human); border-color: var(--mc-human); font-weight: 700; }
.finding { font-size: 13.5px; margin: 0 0 12px; }
.ev { margin: 0 0 14px; padding-left: 18px; font-size: 12.5px; color: var(--mc-muted); }
.gate { border: 1px solid var(--mc-human); border-radius: var(--mc-radius); padding: 12px; background: color-mix(in srgb, var(--mc-human) 7%, var(--mc-panel)); }
.gate .lbl { font-weight: 700; color: var(--mc-human); font-size: 13px; margin-bottom: 6px; }
.gate p { margin: 0 0 10px; font-size: 13.5px; }
.gate .row { display: flex; gap: 8px; }
.approve { background: var(--mc-stable); color: var(--mc-onStable); border-color: var(--mc-stable); font-weight: 600; }
.reject { color: var(--mc-critical); border-color: var(--mc-critical); background: transparent; font-weight: 600; }
.outcome { margin-top: 10px; font-size: 13px; font-weight: 600; color: var(--mc-accent); }
.mono { font-family: var(--mc-mono); }
.insights { grid-column: 1 / -1; }
.ins-grid { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 18px; }
.rail { position: sticky; top: 12px; align-self: start; display: flex; flex-direction: column; gap: 6px; }
.rail a { white-space: nowrap; text-decoration: none; color: var(--mc-muted); padding: 8px 10px; border-left: 3px solid var(--mc-border); font-size: 13px; }
.rail a[aria-current="true"] { border-left-color: var(--mc-accent); color: var(--mc-ink); font-weight: 600; }
.figs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: start; }
.fig { cursor: pointer; transition: border-color .2s, box-shadow .2s; }
.fig:hover { border-color: var(--mc-accent); }
.fig.on { border-color: var(--mc-accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--mc-accent) 35%, transparent); }
.pc-pulse { animation: pc-pulse 1.5s ease-out; }
svg .pc-target > circle:not([r="22"]) { stroke: var(--mc-accent) !important; stroke-width: 6 !important; filter: drop-shadow(0 0 5px var(--mc-accent)); }
svg circle.pc-target { stroke: var(--mc-accent) !important; stroke-width: 3 !important; filter: drop-shadow(0 0 5px var(--mc-accent)); }
svg .pc-pulse { animation: pc-pulse-svg 1.5s ease-out; transform-box: fill-box; transform-origin: center; }
@keyframes pc-pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--mc-accent) 60%, transparent); } 70% { box-shadow: 0 0 0 12px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
@keyframes pc-pulse-svg { 0%, 100% { filter: none; transform: scale(1); } 30% { filter: drop-shadow(0 0 6px var(--mc-accent)) drop-shadow(0 0 12px var(--mc-accent)); transform: scale(1.18); } }
@media (prefers-reduced-motion: reduce) { .pc-pulse { outline: 2px solid var(--mc-accent); outline-offset: 3px; } }
.fig { border: 1px solid var(--mc-border); border-radius: var(--mc-radius); padding: 14px; background: var(--mc-surface); scroll-margin-top: 12px; }
.fig h3 { margin: 0 0 4px; font-size: 13px; color: var(--mc-muted); font-weight: 600; }
.fig .head { font-size: 15px; font-weight: 600; margin: 0 0 8px; }
.fig .num { font-family: var(--mc-mono); font-size: 26px; font-weight: 700; }
.fig .delta { font-size: 13px; font-weight: 600; margin-left: 8px; }
.fig .delta.worse { color: var(--mc-critical); } .fig .delta.better { color: var(--mc-stable); } .fig .delta.same { color: var(--mc-muted); }
.fig .ref { font-size: 11.5px; color: var(--mc-muted); }
.fig details { margin-top: 8px; font-size: 12.5px; }
.fig summary { cursor: pointer; color: var(--mc-accent); font-weight: 600; }
.fig dl { display: grid; grid-template-columns: auto 1fr; gap: 3px 10px; margin: 8px 0 0; }
.fig dt { color: var(--mc-muted); } .fig dd { margin: 0; font-family: var(--mc-mono); overflow-wrap: anywhere; }
@media (max-width: 900px) {
  main { grid-template-columns: minmax(0, 1fr); padding: 12px; } .top { padding: 10px 12px; }
  .ins-grid { grid-template-columns: minmax(0, 1fr); } .rail { position: static; flex-direction: row; overflow-x: auto; }
  .figs { grid-template-columns: minmax(0, 1fr); }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
"""

JS = r"""
const D = JSON.parse(document.getElementById('pc-data').textContent);
const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs, parent, text) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text !== undefined) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
const COL = {ok: 'stable', slow: 'atRisk', failed: 'critical', running: 'system', waiting: 'atRisk', done: 'stable'};
const fill = k => `fill:var(--mc-${k})`, stroke = k => `stroke:var(--mc-${k})`;
const detail = document.getElementById('detail');
const say = t => { detail.textContent = t; pulse(detail); };
// Feedback on every press: a short glow on what was pressed (and what it points to), a tiny
// vibration on Android. Reduced motion gets a steady outline instead of the animation.
const stationEls = [];
function pulse(node) {
  if (!node) return;
  node.classList.remove('pc-pulse'); void node.getBoundingClientRect(); node.classList.add('pc-pulse');
  clearTimeout(node.__pt); node.__pt = setTimeout(() => node.classList.remove('pc-pulse'), 1600);
}
function buzz() { try { navigator.vibrate && navigator.vibrate(12); } catch (e) {} }
const root = document.documentElement, tb = document.getElementById('theme');
const syncTheme = () => { tb.textContent = root.dataset.theme === 'dark' ? 'Light' : 'Dark'; };
tb.onclick = () => { root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark'; syncTheme(); };
syncTheme();
document.querySelectorAll('[data-gate]').forEach(b => b.onclick = () => {
  const ok = b.dataset.gate === 'approve';
  document.getElementById('outcome').textContent = ok ? 'Approved. Action queued (simulated in this page).' : 'Rejected. Nothing changed; the agent re-checks on the next run.';
  document.querySelectorAll('.beats span').forEach((s, i) => { s.className = (ok ? i < 7 : i < 4) ? 'done' : ''; });
  document.querySelectorAll('[data-gate]').forEach(x => x.disabled = true);
});
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- flow line ----------
const box = document.getElementById('viz');
let svg, dots = [], geo;
function drawFlow() {
  box.innerHTML = '';
  const W = Math.max(760, box.clientWidth), H = 300, padX = 60, y = 150, n = D.stages.length, step = (W - 2 * padX) / (n - 1);
  geo = {W, padX, y, step};
  const X = i => padX + i * step;
  svg = el('svg', {width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `${D.pipeline} pipeline flow`}, box);
  el('line', {x1: X(0), y1: y, x2: X(n - 1), y2: y, style: stroke('border') + ';stroke-width:6;stroke-linecap:round'}, svg);
  D.stages.forEach((s, i) => {
    const st = D.stageState[s.id] || 'ok', col = COL[st];
    if (i < n - 1 && st === 'ok') el('line', {x1: X(i), y1: y, x2: X(i + 1), y2: y, style: stroke('stable') + ';stroke-width:6;stroke-opacity:.35'}, svg);
    const g = el('g', {tabindex: 0, role: 'button', 'aria-label': s.name, style: 'cursor:pointer'}, svg);
    if (st !== 'ok') el('circle', {cx: X(i), cy: y, r: 22, style: fill(col) + ';opacity:.18'}, g);
    el('circle', {cx: X(i), cy: y, r: 13, style: fill('panel') + ';' + stroke(col) + ';stroke-width:4'}, g);
    if (st === 'failed') el('text', {x: X(i), y: y + 5, 'text-anchor': 'middle', style: fill('critical') + ';font-weight:800;font-size:14px'}, g, '!');
    el('text', {x: X(i), y: y + 44, 'text-anchor': 'middle', style: fill('ink') + ';font-size:13px;font-weight:600'}, g, s.name);
    const none = s.latest === null || s.base === null;
    const slow = !none && s.latest > s.base * 1.5 + 0.5;
    el('text', {x: X(i), y: y + 62, 'text-anchor': 'middle', style: fill(none ? 'muted' : slow ? 'atRisk' : 'ink') + ';font-size:12.5px;font-weight:' + (slow ? 700 : 500)}, g, none ? 'no run yet' : `${s.latest.toFixed(1)} min`);
    el('text', {x: X(i), y: y + 78, 'text-anchor': 'middle', style: fill('muted') + ';font-size:11.5px'}, g, none ? 'never reached' : `was ${s.base.toFixed(1)}`);
    stationEls[i] = g;
    const q = D.queue[s.id];
    if (q) {
      const hot = q > 3;
      el('rect', {x: X(i) - 34, y: y - 82, width: 68, height: 24, rx: 12, style: fill(hot ? 'atRisk' : 'raised') + (hot ? ';fill-opacity:.16' : '') + ';' + stroke(hot ? 'atRisk' : 'border')}, g);
      el('text', {x: X(i), y: y - 65, 'text-anchor': 'middle', style: fill(hot ? 'atRisk' : 'muted') + ';font-size:12px;font-weight:600'}, g, `${q} waiting`);
    }
    const act = () => { pulse(g); say(none ? `${s.name}: no run has reached this stage yet. ${q || 0} waiting.` : `${s.name}: ${st === 'ok' ? 'healthy' : st}. Median ${s.latest.toFixed(1)} min today, ${s.base.toFixed(1)} min ${D.source.baseline}. ${q || 0} waiting.`); };
    g.onclick = act; g.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act(); } };
  });
  if (D.agent) {
    const ax = X(D.stages.findIndex(s => s.id === D.agent.stage)), ay = 46;
    el('line', {x1: ax, y1: ay + 16, x2: ax, y2: y - (D.queue[D.agent.stage] ? 86 : 26), style: stroke('human') + ';stroke-width:1.5;stroke-dasharray:4 4'}, svg);
    const hex = [0, 1, 2, 3, 4, 5].map(k => { const a = Math.PI / 3 * k + Math.PI / 6; return `${ax + 15 * Math.cos(a)},${ay + 15 * Math.sin(a)}`; }).join(' ');
    el('polygon', {points: hex, style: fill('panel') + ';' + stroke('human') + ';stroke-width:2'}, svg);
    const right = ax + 200 < W;
    el('text', {x: right ? ax + 24 : ax - 24, y: ay - 2, 'text-anchor': right ? 'start' : 'end', style: fill('human') + ';font-size:12.5px;font-weight:700'}, svg, D.agent.badge || 'Agent: fix drafted');
    el('text', {x: right ? ax + 24 : ax - 24, y: ay + 14, 'text-anchor': right ? 'start' : 'end', style: fill('muted') + ';font-size:12px'}, svg, D.agent.badge_sub || 'waiting for your approval');
  }
  dots = D.runs.map((r, k) => {
    const c = el('circle', {r: r.state === 'failed' ? 8 : 7, tabindex: 0, 'aria-label': `Run ${r.id}`, style: fill(COL[r.state]) + ';' + stroke('panel') + ';stroke-width:2;cursor:pointer'}, svg);
    const act = () => { pulse(c); say(`Run ${r.id}${r.msg ? ' · “' + r.msg + '”' : ''} · ${r.state} at ${D.stages[r.stage].name}`); };
    c.onclick = act; c.onkeydown = e => { if (e.key === 'Enter') act(); };
    return {r, c, k};
  });
  place(0);
  document.getElementById('swipe').classList.toggle('on', box.scrollWidth > box.clientWidth + 4);
}
function place(t) {
  const {padX, y, step} = geo, waitIdx = {};
  dots.forEach(({r, c, k}) => {
    let x = padX + r.stage * step, yy = y;
    if (r.state === 'waiting') {
      const j = (waitIdx[r.stage] = (waitIdx[r.stage] || 0) + 1);
      x = padX + r.stage * step + step - 30 - (j - 1) * 16; yy = y - 26;
    } else if (r.state === 'running') {
      x = padX + (r.stage + ((r.p + t * 0.02 * (1 + (k % 3) * 0.3)) % 1) * 0.85) * step;
    }
    c.setAttribute('cx', x); c.setAttribute('cy', yy);
  });
}
drawFlow();
const t0 = performance.now();
let animT = 0;
function loop(now) { if (window.__driven) return; animT = (now - t0) / 1000; place(animT); requestAnimationFrame(loop); }
if (!reduce) requestAnimationFrame(loop);
say('Tap a station or a run dot for details.');

// ---------- insight cards ----------
const money = v => '$' + v.toFixed(3);
// Round axis top that fits small values too (0.3 min used to sit flat on a 0-10 axis).
function niceMax(v) { if (!(v > 0)) return 1; const mag = Math.pow(10, Math.floor(Math.log10(v))); return [1, 2, 2.5, 5, 10].map(k => k * mag).find(x => x >= v - 1e-12); }
// At most ~5 round ticks whatever the range (an outlier once produced thousands of 10-min ticks).
function niceTicks(mx) {
  const raw = mx / 4, mag = Math.pow(10, Math.floor(Math.log10(raw || 1))), step = [1, 2, 5, 10].map(k => k * mag).find(s => s >= raw) || raw;
  const out = []; for (let v = 0; v <= mx + 1e-9; v += step) out.push(+v.toFixed(6)); return out;
}
const fmt = (f, v) => f.unit === 'USD' ? money(v) : f.unit === '%' ? v.toFixed(1) + '%' : f.unit === 'runs' ? String(Math.round(v)) : v.toFixed(1) + ' min';
const host = document.getElementById('figs');
D.figures.forEach(f => {
  const art = document.createElement('article');
  art.className = 'fig'; art.id = 'fig-' + f.id;
  const arrow = f.delta > 0 ? '▲ +' : f.delta < 0 ? '▼ −' : '';
  const dtxt = f.unit === 'USD' ? money(Math.abs(f.delta)) : f.unit === '%' ? Math.abs(f.delta).toFixed(1) + ' pts' : f.unit === 'runs' ? Math.abs(f.delta) + ' runs' : Math.abs(f.delta).toFixed(1) + ' min';
  art.innerHTML = `<h3></h3><p class="head"></p>
    <div><span class="num"></span> <span class="delta ${f.status}">${arrow}${dtxt} · ${f.status === 'same' ? 'about the same' : f.status}</span></div>
    <div class="chart"></div>
    <div class="ref"><span style="letter-spacing:2px">- - -</span> baseline: ${fmt(f, f.ref)} ${f.refLabel}</div>
    <details><summary>Explain this figure</summary><dl></dl></details>`;
  art.querySelector('h3').textContent = f.title;
  art.querySelector('.head').textContent = f.headline;
  art.querySelector('.num').textContent = fmt(f, f.latest);
  const rows = [['Source', `Run log, ${D.source.rows} runs`], ['Period', D.source.period], ['Calculation', f.calc],
    ['Latest', `${fmt(f, f.latest)} (${f.latestRuns} runs on ${D.days[D.days.length - 1]})`],
    ['Baseline', `${fmt(f, f.ref)} ${f.refLabel}` + (f.refMode === 'fixed' ? ' — fixed, so a slow week cannot become the new normal' : ' — rolling')]];
  if (f.id === 'cost') rows.push(['Rate', `$${D.source.rate} ${D.source.rateNote}`], ['Per week', `${f.weeklyExtra >= 0 ? '+' : '−'}$${Math.abs(f.weeklyExtra).toFixed(2)} = cost difference × ${f.runsPerDay} runs/day (latest day) × 7`]);
  rows.push(['Daily values', f.values.join(', ')], ['Log digest', 'sha256 ' + D.source.sha256.slice(0, 16) + '…']);
  const dl = art.querySelector('dl');
  rows.forEach(([k, v]) => { const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = k; dd.textContent = v; dl.append(dt, dd); });
  host.appendChild(art);
  art.tabIndex = 0; art.setAttribute('role', 'button'); art.setAttribute('aria-label', f.title + ': show where this is on the flow line');
  const focusFig = (ev) => {
    if (ev && ev.target.closest('details')) return;  // Explain stays a normal disclosure
    buzz(); pulse(art);
    document.querySelectorAll('.fig.on').forEach(x => x !== art && x.classList.remove('on')); art.classList.add('on');
    const fi = D.stages.findIndex(s => s.id === D.focus);
    const failedDots = (typeof dots !== 'undefined' ? dots : []).filter(d => d.r.state === 'failed').map(d => d.c);
    const targets = f.id === 'stage' ? [stationEls[fi]] : f.id === 'failed' ? (failedDots.length ? failedDots : stationEls.filter((g, i) => (D.failStages || []).includes(D.stages[i].id) || (D.stageState[D.stages[i].id] || 'ok') === 'failed')) : stationEls;
    document.querySelectorAll('.pc-target').forEach(x => x.classList.remove('pc-target'));
    targets.forEach(t => { if (t) { t.classList.add('pc-target'); pulse(t); } });
    const line = document.getElementById('flow-h');
    if (line && f.id !== 'cost') line.closest('section').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest'});
    const failNames = D.stages.filter(s => (D.failStages || []).includes(s.id)).map(s => s.name).join(', ');
    say(f.headline + (f.id === 'failed' && !failedDots.length ? (failNames ? ` None is on the line now; past failures happened at ${failNames} (highlighted).` : ' No failed run is on the line right now.') : ''));
  };
  art.addEventListener('click', focusFig);
  art.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { if (e.target === art) { e.preventDefault(); focusFig(e); } } });
  const cbox = art.querySelector('.chart');
  cbox.setAttribute('role', 'img');
  cbox.setAttribute('aria-label', `${f.title} per day, ${D.days[0]} to ${D.days[D.days.length - 1]}; latest ${fmt(f, f.latest)}, baseline ${fmt(f, f.ref)}`);
  const draw = () => {
    cbox.innerHTML = '';
    const W = Math.max(240, cbox.clientWidth), H = 124, l = 46, r = 22, t = 16, b = 22, vals = f.values;
    const isInt = vals.every(Number.isInteger);
    const top = Math.max(...vals, f.ref);
    const mx = f.unit === '%' ? 100 : f.unit === 'USD' ? niceMax(top * 1.15) : isInt ? Math.max(2, Math.ceil(top * 1.1)) : niceMax(top * 1.1);
    const ticks = f.unit === '%' ? [0, 50, 100] : f.unit === 'USD' ? [0, mx / 2, mx] : isInt && mx <= 6 ? Array.from({length: Math.floor(mx / 2) + 1}, (_, i) => i * 2) : isInt ? [0, Math.round(mx / 2), mx] : niceTicks(mx);
    const lo = f.unit === '%' ? Math.max(0, Math.floor((Math.min(...vals, f.ref) - 5) / 10) * 10) : 0;
    const tk = f.unit === '%' ? [lo, Math.round((lo + 100) / 2), 100] : ticks;
    const X = i => l + i * (W - l - r) / (vals.length - 1), Y = v => t + (1 - (v - lo) / (mx - lo)) * (H - t - b);
    const s = el('svg', {width: W, height: H, viewBox: `0 0 ${W} ${H}`}, cbox);
    tk.forEach(v => { el('line', {x1: l, x2: W - r, y1: Y(v), y2: Y(v), style: stroke('grid')}, s);
      el('text', {x: l - 6, y: Y(v) + 4, 'text-anchor': 'end', style: fill('muted') + ';font-size:11px'}, s, f.unit === 'USD' ? '$' + v.toFixed(2) : v); });
    el('text', {x: l, y: t - 5, style: fill('muted') + ';font-size:10.5px'}, s, f.unit === 'USD' ? 'USD per run' : f.unit === '%' ? '% of runs' : f.unit === 'runs' ? 'runs per day' : 'minutes');
    [0, vals.length - 1].forEach(i => el('text', {x: X(i), y: H - 6, 'text-anchor': i ? 'end' : 'start', style: fill('muted') + ';font-size:11px'}, s, D.days[i]));
    el('line', {x1: l, x2: W - r, y1: Y(f.ref), y2: Y(f.ref), style: stroke('muted') + ';stroke-dasharray:5 4;stroke-width:1.5'}, s);
    const bad = f.status === 'worse';
    el('polyline', {points: vals.map((v, i) => X(i) + ',' + Y(v)).join(' '), style: 'fill:none;' + stroke(bad ? 'critical' : 'accent') + ';stroke-width:2.5;stroke-linejoin:round'}, s);
    vals.forEach((v, i) => { const c = el('circle', {cx: X(i), cy: Y(v), r: i === vals.length - 1 ? 4.5 : 2.5, style: fill(bad && i === vals.length - 1 ? 'critical' : 'accent')}, s); el('title', {}, c, `${D.days[i]}: ${fmt(f, v)}`); });
  };
  draw(); addEventListener('resize', draw);
});
const links = [...document.querySelectorAll('.rail a')];
const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) links.forEach(a => a.setAttribute('aria-current', a.hash === '#' + e.target.id ? 'true' : 'false')); }), {rootMargin: '-30% 0px -60% 0px'});
document.querySelectorAll('.fig').forEach(f => io.observe(f));
addEventListener('resize', drawFlow);


// ---------- other views ----------
const txt = (id, t) => { document.getElementById(id).textContent = t; };
function drawWaterfall() {
  const w = D.waterfall, host = document.getElementById('wf-viz');
  txt('wf-head', w.headline); txt('wf-how', w.how);
  host.innerHTML = '';
  const rows = w.rows, n = rows.length, Wd = Math.max(760, host.clientWidth), rowH = 34, top = 30, left = 150, right = 96, H = top + n * rowH + 34;
  const maxT = Math.ceil(Math.max(w.total, w.baseTotal) / 10) * 10;
  const X = m => left + (m / maxT) * (Wd - left - right);
  const g = el('svg', {width: Wd, height: H, viewBox: `0 0 ${Wd} ${H}`, role: 'img', 'aria-label': `Run ${w.run} stage times against baseline`}, host);
  for (let m = 0; m <= maxT; m += 10) {
    el('line', {x1: X(m), y1: top - 6, x2: X(m), y2: top + n * rowH, style: stroke('grid')}, g);
    el('text', {x: X(m), y: top + n * rowH + 18, 'text-anchor': 'middle', style: fill('muted') + ';font-size:12px'}, g, m + ' min');
  }
  el('text', {x: left, y: 16, style: fill('ink') + ';font-size:13px;font-weight:600'}, g, `Run ${w.run} · ${w.date} · ${w.total} min · baseline ${w.baseTotal} min`);
  let a = 0, b = 0;
  rows.forEach((r, i) => {
    const yy = top + i * rowH;
    el('text', {x: left - 12, y: yy + 21, 'text-anchor': 'end', style: fill('ink') + ';font-size:13px'}, g, r.name);
    if (r.actual === null) { el('text', {x: X(a) + 6, y: yy + 21, style: fill('muted') + ';font-size:12px'}, g, 'not reached'); return; }
    const d = r.actual - r.base, col = d > 5 ? 'critical' : d > 1 ? 'atRisk' : 'stable';
    // Baseline box starts where this run's stage starts, so each pair compares directly.
    el('rect', {x: X(a), y: yy + 5, width: Math.max(3, X(a + r.base) - X(a)), height: 24, rx: 4, style: 'fill:none;' + stroke('muted') + ';stroke-width:1.5;stroke-dasharray:4 3'}, g);
    const bar = el('rect', {x: X(a), y: yy + 10, width: Math.max(4, X(a + r.actual) - X(a)), height: 14, rx: 3, tabindex: 0, style: fill(col) + ';cursor:pointer'}, g);
    el('title', {}, bar, `${r.name}: ${r.actual} min, baseline ${r.base} min`);
    if (Math.abs(d) >= 0.5) el('text', {x: X(a + Math.max(r.actual, r.base)) + 8, y: yy + 22, style: fill(col) + ';font-size:12.5px;font-weight:700'}, g, (d > 0 ? '+' : '−') + Math.abs(d).toFixed(1) + ' min');
    a += r.actual; b += r.base;
  });
}
function volBands() {
  const v = D.volume, host = document.getElementById('vol-viz'), st = D.stages, n = st.length;
  txt('vol-head', v.headline); txt('vol-how', 'Flow bands: width = runs reaching each stage; red = runs that failed there. Good for the overall shape, weak when losses are small. ' + v.how + ' Window: ' + v.window + '.');
  host.innerHTML = '';
  const Wd = Math.max(900, host.clientWidth), H = 340, padX = 46, topY = 52, maxH = 170, colW = 14;
  const k = maxH / v.reach[0], step = (Wd - 2 * padX - colW) / (n - 1), X = i => padX + i * step;
  const g = el('svg', {width: Wd, height: H, viewBox: `0 0 ${Wd} ${H}`, role: 'img', 'aria-label': `Runs reaching each stage, ${v.window}`}, host);
  for (let i = 0; i < n; i++) {
    const h = v.reach[i] * k;
    if (i < n - 1) {
      const h2 = v.reach[i + 1] * k, x1 = X(i) + colW, x2 = X(i + 1), mx = (x1 + x2) / 2;
      el('path', {d: `M${x1},${topY} L${x2},${topY} L${x2},${topY + h2} L${x1},${topY + h2} Z`, style: fill('stable') + ';fill-opacity:.4'}, g);
      if (v.drop[i] > 0) {
        const dh = Math.max(6, v.drop[i] * k), y0 = topY + h - dh, yb = topY + maxH + 46;
        const p = el('path', {d: `M${x1},${y0} C${x1 + 30},${y0} ${x1 + 20},${yb} ${x1 + 56},${yb} L${x1 + 56},${yb + dh} C${x1 + 10},${yb + dh} ${x1 + 10},${topY + h} ${x1},${topY + h} Z`, tabindex: 0, style: fill('critical') + ';fill-opacity:.75;cursor:pointer'}, g);
        el('title', {}, p, `${v.drop[i]} runs failed at ${st[i].name} (previous week: ${v.dropPrev[i]})`);
        el('text', {x: x1 + 62, y: yb + 12, style: fill('critical') + ';font-size:13px;font-weight:700'}, g, `${v.drop[i]} failed here`);
        el('text', {x: x1 + 62, y: yb + 28, style: fill('muted') + ';font-size:11.5px'}, g, `week before: ${v.dropPrev[i]}`);
      }
    } else if (v.drop[i] > 0) {
      el('text', {x: X(i) + colW / 2, y: topY + h + 18, 'text-anchor': 'middle', style: fill('critical') + ';font-size:12px;font-weight:700'}, g, '−' + v.drop[i]);
    }
    el('rect', {x: X(i), y: topY, width: colW, height: h, rx: 3, style: fill('accent')}, g);
    el('text', {x: X(i) + colW / 2, y: topY - 26, 'text-anchor': 'middle', style: fill('ink') + ';font-size:12.5px;font-weight:600'}, g, st[i].name);
    el('text', {x: X(i) + colW / 2, y: topY - 10, 'text-anchor': 'middle', style: fill('muted') + ';font-size:12px'}, g, v.reach[i]);
  }
}

const volSay = t => { document.getElementById('vol-detail').textContent = t; };
const VR = () => { const v = D.volume, n = D.stages.length, rate = (d, r) => r ? 100 * d / r : 0;
  return {v, n, now: D.stages.map((_, i) => rate(v.drop[i], v.reach[i])), prev: D.stages.map((_, i) => rate(v.dropPrev[i], v.reachPrev[i]))}; };
const twoLine = (s, x, y, name) => { const t = el('text', {x, y, 'text-anchor': 'middle', style: fill('ink') + ';font-size:12px'}, s); name.split(' ').forEach((w, k) => el('tspan', {x, dy: k ? 14 : 0}, t, w)); };

function volArrows() {
  const {v, n, now, prev} = VR(), host = document.getElementById('vol-viz'); host.innerHTML = '';
  const W = Math.max(640, host.clientWidth), rowH = 40, left = 150, right = 150, top = 36, H = top + n * rowH + 30;
  const mx = Math.ceil(Math.max(...now, ...prev, 1) / 2) * 2, X = x => left + x / mx * (W - left - right);
  const s = el('svg', {width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Failure rate per stage, previous week to this week'}, host);
  el('defs', {}, s).innerHTML = '<marker id="pc-ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style="fill:context-stroke"/></marker>';
  for (let t = 0; t <= mx; t += mx / 4) { el('line', {x1: X(t), x2: X(t), y1: top - 10, y2: top + n * rowH, style: stroke('grid')}, s); el('text', {x: X(t), y: top + n * rowH + 18, 'text-anchor': 'middle', style: fill('muted') + ';font-size:12px'}, s, t.toFixed(1) + '%'); }
  el('text', {x: left, y: 16, style: fill('muted') + ';font-size:12px'}, s, `% of runs that reached the stage and failed there · ○ ${v.prevWindow} → ● ${v.window} · red = worse, blue = better`);
  let worst = 0;
  D.stages.forEach((st, i) => {
    const name = st.name, y = top + i * rowH + 14, a = prev[i], b = now[i], up = b > a + 0.05, col = up ? 'critical' : b < a - 0.05 ? 'stable' : 'muted';
    if (b - a > now[worst] - prev[worst]) worst = i;
    const g = el('g', {tabindex: 0, role: 'button', 'aria-label': name, style: 'cursor:pointer'}, s);
    el('rect', {x: 0, y: y - 16, width: W, height: rowH - 4, style: 'fill:transparent'}, g);
    el('text', {x: left - 12, y: y + 4, 'text-anchor': 'end', style: fill('ink') + ';font-size:13px'}, g, name);
    if (Math.abs(b - a) > 0.05) el('line', {x1: X(a), x2: X(b) + (up ? -11 : 11), y1: y, y2: y, 'marker-end': 'url(#pc-ah)', style: stroke(col) + ';stroke-width:2.5'}, g);
    el('circle', {cx: X(a), cy: y, r: 5, style: fill('panel') + ';' + stroke('muted') + ';stroke-width:2'}, g);
    el('circle', {cx: X(b), cy: y, r: 6, style: fill(col === 'muted' ? 'accent' : col)}, g);
    el('text', {x: W - right + 14, y: y + 4, style: fill(col === 'muted' ? 'muted' : col) + ';font-size:12.5px;font-weight:600'}, g,
      v.drop[i] || v.dropPrev[i] ? `${v.dropPrev[i]} → ${v.drop[i]} runs` : 'no failures');
    const act = () => volSay(`${name}: ${a.toFixed(1)}% → ${b.toFixed(1)}% failed there (${v.dropPrev[i]} of ${v.reachPrev[i]} → ${v.drop[i]} of ${v.reach[i]} runs).`);
    g.onclick = act; g.onkeydown = e => { if (e.key === 'Enter') act(); };
  });
  const worse = D.stages.filter((_, i) => now[i] > prev[i] + 0.05).map(x => x.name);
  txt('vol-head', !worse.length ? 'No stage fails more often than the week before.' : worse.length === 1
    ? `${worse[0]} is the only stage that got worse: ${prev[worst].toFixed(1)}% → ${now[worst].toFixed(1)}% of runs failed there.`
    : `${worse.length} stages got worse; the biggest rise is ${D.stages[worst].name}: ${prev[worst].toFixed(1)}% → ${now[worst].toFixed(1)}%.`);
  txt('vol-how', 'Change arrows (arrow plot): each stage\u2019s failure rate last week → this week. Rate = runs that failed at the stage ÷ runs that reached it. Shows change directly, even when losses are small.');
}

function volSteps() {
  const {v, n} = VR(), host = document.getElementById('vol-viz'); host.innerHTML = '';
  const W = Math.max(760, host.clientWidth), H = 360, left = 60, right = 20, top = 30, bot = 70;
  const end = v.reach[0] - v.drop.reduce((a, b) => a + b, 0);
  const lo = Math.max(0, Math.floor((end - 6) / 5) * 5), hi = v.reach[0] + 2, Y = x => top + (1 - (x - lo) / (hi - lo)) * (H - top - bot);
  const cw = (W - left - right) / (n + 1), X = i => left + i * cw, step = Math.max(1, Math.ceil((hi - lo) / 6 / 5) * 5);
  const s = el('svg', {width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Runs remaining after each stage'}, host);
  for (let t = lo; t <= hi; t += step) { el('line', {x1: left, x2: W - right, y1: Y(t), y2: Y(t), style: stroke('grid')}, s); el('text', {x: left - 8, y: Y(t) + 4, 'text-anchor': 'end', style: fill('muted') + ';font-size:12px'}, s, t); }
  if (lo > 0) el('text', {x: left, y: 16, style: fill('atRisk') + ';font-size:12px;font-weight:600'}, s, `Axis starts at ${lo}, not 0 — zoomed so small losses are visible`);
  el('rect', {x: X(0) + 8, y: Y(v.reach[0]), width: cw - 16, height: Y(lo) - Y(v.reach[0]), rx: 3, style: fill('accent')}, s);
  el('text', {x: X(0) + cw / 2, y: Y(v.reach[0]) - 6, 'text-anchor': 'middle', style: fill('ink') + ';font-size:12.5px;font-weight:700'}, s, v.reach[0]);
  twoLine(s, X(0) + cw / 2, H - bot + 18, 'Started');
  let level = v.reach[0];
  D.stages.forEach((st, i) => {
    const x = X(i + 1), dr = v.drop[i];
    el('line', {x1: X(i) + cw - 8, x2: x + 8, y1: Y(level), y2: Y(level), style: stroke('muted') + ';stroke-dasharray:3 3'}, s);
    if (dr) {
      const r = el('rect', {x: x + 8, y: Y(level), width: cw - 16, height: Math.max(3, Y(level - dr) - Y(level)), rx: 3, tabindex: 0, style: fill('critical') + ';cursor:pointer'}, s);
      const act = () => volSay(`${st.name}: ${dr} runs failed here (week before: ${v.dropPrev[i]}).`);
      r.onclick = act; r.onkeydown = e => { if (e.key === 'Enter') act(); };
      el('text', {x: x + cw / 2, y: Y(level - dr) + 16, 'text-anchor': 'middle', style: fill('critical') + ';font-size:12.5px;font-weight:700'}, s, '−' + dr);
      level -= dr;
    }
    twoLine(s, x + cw / 2, H - bot + 18, st.name);
  });
  txt('vol-head', `${v.reach[0]} runs started; ${level} finished. ${v.reach[0] - level} were lost across ${v.drop.filter(Boolean).length} stages.`);
  txt('vol-how', 'Step-down (zoomed waterfall): each red step is the runs that failed at that stage. The axis is zoomed and says so; heights are not proportional to the total.');
}

function volSurvival() {
  const {v, n} = VR(), host = document.getElementById('vol-viz'); host.innerHTML = '';
  if (!v.prevWindow) { txt('vol-head', 'Needs two weeks of runs to compare.'); return; }
  const W = Math.max(760, host.clientWidth), H = 330, left = 56, right = 170, top = 30, bot = 56;
  const after = (reach, drop) => { let lv = reach[0]; return drop.map(d => (lv -= d, 100 * lv / reach[0])); };
  const a = after(v.reachPrev, v.dropPrev), b = after(v.reach, v.drop);
  const lo = Math.floor(Math.min(...a, ...b) - 2), Y = x => top + (1 - (x - lo) / (100 - lo)) * (H - top - bot);
  const X = i => left + (i + 0.5) * (W - left - right) / n;
  const s = el('svg', {width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Share of runs still going after each stage'}, host);
  const step = Math.max(1, Math.ceil((100 - lo) / 5));
  for (let t = 100; t >= lo; t -= step) { el('line', {x1: left, x2: W - right, y1: Y(t), y2: Y(t), style: stroke('grid')}, s); el('text', {x: left - 8, y: Y(t) + 4, 'text-anchor': 'end', style: fill('muted') + ';font-size:12px'}, s, t + '%'); }
  el('text', {x: left, y: 16, style: fill('atRisk') + ';font-size:12px;font-weight:600'}, s, `Axis starts at ${lo}% — zoomed`);
  const pts = arr => arr.map((x, i) => `${X(i)},${Y(x)}`);
  el('polyline', {points: pts(a).join(' '), style: 'fill:none;' + stroke('muted') + ';stroke-width:2;stroke-dasharray:6 4'}, s);
  el('polyline', {points: pts(b).join(' '), style: 'fill:none;' + stroke('accent') + ';stroke-width:3'}, s);
  D.stages.forEach((st, i) => {
    el('circle', {cx: X(i), cy: Y(a[i]), r: 3.5, style: fill('panel') + ';' + stroke('muted') + ';stroke-width:1.5'}, s);
    const c = el('circle', {cx: X(i), cy: Y(b[i]), r: 5, tabindex: 0, style: fill('accent') + ';cursor:pointer'}, s);
    const act = () => volSay(`After ${st.name}: ${b[i].toFixed(1)}% of runs still going this week, ${a[i].toFixed(1)}% the week before.`);
    c.onclick = act; c.onkeydown = e => { if (e.key === 'Enter') act(); };
    twoLine(s, X(i), H - bot + 18, st.name);
  });
  const hiB = b[n - 1] >= a[n - 1];
  el('text', {x: W - right + 10, y: Y(b[n - 1]) + (hiB ? -6 : 16), style: fill('accent') + ';font-size:12.5px;font-weight:700'}, s, `this week ${b[n - 1].toFixed(1)}%`);
  el('text', {x: W - right + 10, y: Y(a[n - 1]) + (hiB ? 16 : -6), style: fill('muted') + ';font-size:12.5px'}, s, `week before ${a[n - 1].toFixed(1)}%`);
  txt('vol-head', `${b[n - 1].toFixed(1)}% of runs reached ${D.stages[n - 1].name} this week, against ${a[n - 1].toFixed(1)}% the week before.`);
  txt('vol-how', 'Survival line: share of runs still going after each stage; solid = this week, dashed = week before. Good for the overall trend; it does not single out one stage.');
}

function volUnits() {
  const {v} = VR(), host = document.getElementById('vol-viz'); host.innerHTML = '';
  const sz = 16, gap = 3, cols = Math.max(12, Math.floor((Math.max(320, host.clientWidth) - 20) / (sz + gap)));
  const W = cols * (sz + gap) + 20;
  const PAL = ['critical', 'concerning', 'atRisk', 'human', 'system', 'model', 'accent', 'stable'];
  const runs = [...v.runs].sort((x, y) => (x.stop ?? 99) - (y.stop ?? 99));
  const rowsN = Math.ceil(runs.length / cols);
  const used = D.stages.map((st, i) => [i, st.name]).filter(([i]) => v.drop[i]);
  const perRow = W < 560 ? 1 : 2, legendRows = Math.ceil((used.length + 1) / perRow);
  const H = rowsN * (sz + gap) + 24 + legendRows * 22;
  const s = el('svg', {width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `${runs.length} runs, coloured by where they stopped`}, host);
  runs.forEach((r, k) => {
    const x = 10 + (k % cols) * (sz + gap), y = 10 + Math.floor(k / cols) * (sz + gap);
    const c = r.stop === null ? null : PAL[r.stop % PAL.length];
    const q = el('rect', {x, y, width: sz, height: sz, rx: 3, tabindex: 0, style: (c ? fill(c) : fill('stable') + ';fill-opacity:.28') + ';cursor:pointer'}, s);
    el('title', {}, q, `${r.id} · ${r.day} · ${r.stop === null ? 'reached the last stage' : 'stopped at ' + D.stages[r.stop].name}`);
    const act = () => volSay(`Run ${r.id} (${r.day}): ${r.stop === null ? 'reached ' + D.stages[D.stages.length - 1].name : 'failed at ' + D.stages[r.stop].name}.`);
    q.onclick = act; q.onkeydown = e => { if (e.key === 'Enter') act(); };
  });
  const ly0 = rowsN * (sz + gap) + 34, colW = (W - 20) / perRow;
  [[null, `Reached ${D.stages[D.stages.length - 1].name} (${v.runs.filter(r => r.stop === null).length})`]]
    .concat(used.map(([i, nm]) => [i, `Failed at ${nm} (${v.drop[i]})`])).forEach(([i, label], k) => {
      const lx = 10 + (k % perRow) * colW, ly = ly0 + Math.floor(k / perRow) * 22, c = i === null ? null : PAL[i % PAL.length];
      el('rect', {x: lx, y: ly - 12, width: 14, height: 14, rx: 3, style: c ? fill(c) : fill('stable') + ';fill-opacity:.28'}, s);
      el('text', {x: lx + 20, y: ly, style: fill('ink') + ';font-size:12.5px'}, s, label);
    });
  const fail = v.runs.filter(r => r.stop !== null).length;
  txt('vol-head', `${v.runs.length} runs in ${v.window}: ${v.runs.length - fail} finished, ${fail} stopped. Tap any square to see the run.`);
  txt('vol-how', 'Every run is a square (unit chart), sorted by where it stopped. Honest about size and good for drilling into single runs; it does not compare weeks.');
}
const VOL = {arrows: volArrows, units: volUnits, steps: volSteps, survival: volSurvival, bands: volBands};
let volMode = 'arrows';
function drawVolume() {
  (VOL[volMode] || volArrows)();
  const vz = document.getElementById('vol-viz');
  document.getElementById('vol-swipe').classList.toggle('on', vz.scrollWidth > vz.clientWidth + 4);
  document.querySelectorAll('.subviews a').forEach(a => a.setAttribute('aria-current', a.hash === '#volume/' + volMode ? 'true' : 'false'));
}

function drawHeat() {
  const hm = D.heat, host = document.getElementById('heat-viz'), days = D.days;
  txt('heat-head', hm.headline); txt('heat-how', hm.how);
  host.innerHTML = '';
  const left = 130, top = 58, Wd = Math.max(760, host.clientWidth), cw = (Wd - left - 10) / days.length, ch = 26, H = top + hm.rows.length * (ch + 4) + 40;
  const g = el('svg', {width: Wd, height: H, viewBox: `0 0 ${Wd} ${H}`, role: 'img', 'aria-label': 'Stage time against baseline per day'}, host);
  if (hm.changeDay !== null) {
    el('rect', {x: left + hm.changeDay * cw - 2, y: top - 26, width: cw * (days.length - hm.changeDay) + 2, height: hm.rows.length * (ch + 4) + 24, rx: 6, style: 'fill:none;' + stroke('human') + ';stroke-dasharray:5 4;stroke-width:1.5'}, g);
    el('text', {x: left + hm.changeDay * cw + cw * (days.length - hm.changeDay), y: top - 34, 'text-anchor': 'end', style: fill('human') + ';font-size:12px;font-weight:700'}, g, 'change detected');
  }
  days.forEach((d, j) => el('text', {x: left + j * cw + cw / 2, y: top - 8, 'text-anchor': 'middle', style: fill('muted') + ';font-size:11px'}, g, d.replace(/^[A-Za-z]+ /, m => '') ));
  el('text', {x: left, y: 14, style: fill('muted') + ';font-size:12px'}, g, `Days ${days[0]} – ${days[days.length - 1]}`);
  const det = document.getElementById('heat-detail');
  hm.rows.forEach((row, i) => {
    const yy = top + i * (ch + 4);
    el('text', {x: left - 10, y: yy + 18, 'text-anchor': 'end', style: fill('ink') + ';font-size:12.5px'}, g, row.name);
    row.cells.forEach((c, j) => {
      const x = left + j * cw + 1;
      const col = c.ratio === null ? null : c.ratio >= 2 ? 'critical' : c.ratio >= 1.25 ? 'atRisk' : 'stable';
      const r = el('rect', {x, y: yy, width: cw - 2, height: ch, rx: 3, tabindex: 0,
        style: (col ? fill(col) + ';fill-opacity:' + (col === 'stable' ? .3 : .85) : 'fill:none;' + stroke('muted') + ';stroke-dasharray:3 3') + ';cursor:pointer'}, g);
      if (c.fails) el('text', {x: x + (cw - 2) / 2, y: yy + 17, 'text-anchor': 'middle', style: fill(col && col !== 'stable' ? 'panel' : 'ink') + ';font-size:11.5px;font-weight:700;pointer-events:none'}, g, c.fails);
      const act = () => { det.textContent = c.ratio === null ? `${row.name} · ${days[j]} · no runs reached this stage` : `${row.name} · ${days[j]} · median ${c.median} min (${c.ratio}× baseline) · ${c.runs} runs · ${c.fails} failed here`; };
      r.onclick = act; r.onkeydown = e => { if (e.key === 'Enter') act(); };
    });
  });
  const ly = top + hm.rows.length * (ch + 4) + 22;
  [['stable', .3, 'normal'], ['atRisk', .85, '1.25–2× slower'], ['critical', .85, '2× or more']].forEach(([c, o, t], i) => {
    el('rect', {x: left + i * 150, y: ly - 11, width: 14, height: 14, rx: 3, style: fill(c) + ';fill-opacity:' + o}, g);
    el('text', {x: left + i * 150 + 20, y: ly, style: fill('muted') + ';font-size:12px'}, g, t);
  });
  el('text', {x: left + 450, y: ly, style: fill('muted') + ';font-size:12px'}, g, 'number = failed runs at that stage (blank = none)');
}
const VIEWS = {flow: null, waterfall: drawWaterfall, volume: drawVolume, heat: drawHeat};
function route() {
  const [v, sub] = (location.hash || '#flow').slice(1).split('/');
  const view = v in VIEWS ? v : 'flow';
  if (view === 'volume' && sub in VOL) volMode = sub;
  document.querySelectorAll('[data-view-panel]').forEach(p => { p.hidden = p.dataset.viewPanel !== view; });
  document.querySelectorAll('.views a').forEach(a => a.setAttribute('aria-current', a.hash === '#' + view ? 'page' : 'false'));
  if (VIEWS[view]) VIEWS[view](); else drawFlow();
  [['wf-viz', 'wf-swipe'], ['heat-viz', 'heat-swipe']].forEach(([a, b]) => { const x = document.getElementById(a); document.getElementById(b).classList.toggle('on', x.scrollWidth > x.clientWidth + 4); });
}
addEventListener('hashchange', route);
addEventListener('resize', () => { const v = (location.hash || '#flow').slice(1).split('/')[0]; if (VIEWS[v]) VIEWS[v](); });
route();

// Deterministic showcase hooks: scroll from the flow line through each finding.
let shown = 0;
window.__ready = true;
window.__advance = ms => { window.__driven = true; reduceT(ms); };
function reduceT(ms) {
  animT += ms / 1000; place(animT);
  const idx = Math.floor(animT / 2.5);
  if (idx !== shown) { shown = idx; const t = idx === 0 ? document.body : document.querySelectorAll('.fig')[idx - 1]; if (t) t.scrollIntoView({block: 'center'}); }
  window.__isDone = idx > D.figures.length;
}
window.__done = () => !!window.__isDone;
"""


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def render_html(norm: dict, style_name: str | None = None, theme: str | None = None) -> str:
    data = derive(norm)
    st = styles.build_style(style_name or norm["style"])
    theme = theme or st["default_theme"]
    a = norm["agent"]
    beats = "".join(f'<span class="{"done" if i < 3 else "now" if i == 3 else ""}">{b}</span>' for i, b in enumerate(BEATS))
    agent_html = ""
    if a:
        ev = "".join(f"<li>{_e(x)}</li>" for x in data["derivedEvidence"] + a["evidence"])
        agent_html = f"""<aside class="card" aria-label="Agent">
    <h2>Agent loop</h2><div class="beats">{beats}</div>
    <h2>What the agent noticed</h2><p class="finding">{_e(a['finding'])}</p><ul class="ev">{ev}</ul>
    <div class="gate"><div class="lbl">Your approval needed</div><p>{_e(a['action'])}</p>
      <div class="row"><button type="button" class="approve" data-gate="approve">Approve</button>
      <button type="button" class="reject" data-gate="reject">Reject</button></div>
      <div class="outcome" id="outcome" aria-live="polite"></div></div></aside>"""
    rail = "".join(f'<a href="#fig-{f["id"]}">{_e(f["title"])}</a>' for f in data["figures"])
    legend = "".join(f'<span><i style="background:var(--mc-{c})"></i>{t}</span>' for c, t in
                     [("stable", "Healthy / finished"), ("system", "Running"), ("atRisk", "Waiting or slow"),
                      ("critical", "Failed"), ("human", "Agent checkpoint")])
    pill = f'<span class="pill">{_e(norm["data_label"])}</span>' if norm["data_label"] else ""
    payload = json.dumps(data, default=str).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="{theme}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(norm['pipeline'])} — {_e(norm['title'])}</title>
<style>/* style: {_e(st['name'])} ({_e(st['source'])}) */
{styles.style_css(st)}{CSS}</style></head>
<body>
<header class="top">
  <div class="brand">{_e(norm['title'])}<small>{_e(norm['pipeline'])} · {_e(norm['subtitle'])}</small></div>
  <nav class="views" aria-label="Views"><a href="#flow">Flow line</a><a href="#waterfall">Run waterfall</a><a href="#volume">Volume flow</a><a href="#heat">Heat grid</a></nav>
  <div class="spacer"></div>{pill}
  <button id="theme" type="button" aria-label="Toggle theme">Theme</button>
</header>
<main>
  <section class="card" aria-labelledby="flow-h" data-view-panel="flow">
    <h1 id="flow-h">Flow line</h1><p class="q">Where is work stuck right now?</p>
    <div class="vizwrap" id="viz"></div><p class="swipe" id="swipe">Swipe sideways to see every stage →</p>
    <div class="legend">{legend}</div>
    <div class="detail" id="detail" aria-live="polite"></div>
  </section>
  <section class="card" data-view-panel="waterfall" hidden aria-labelledby="wf-h">
    <h1 id="wf-h">Run waterfall</h1><p class="q">Why was this run slow?</p>
    <p class="vhead" id="wf-head"></p><div class="vizwrap" id="wf-viz"></div><p class="swipe" id="wf-swipe">Swipe sideways to see the whole chart →</p><p class="how" id="wf-how"></p>
  </section>
  <section class="card" data-view-panel="volume" hidden aria-labelledby="vol-h">
    <h1 id="vol-h">Volume flow</h1><p class="q">Where do runs stop?</p>
    <nav class="subviews" aria-label="Volume chart type"><a href="#volume/arrows">Change arrows</a><a href="#volume/units">Every run</a><a href="#volume/steps">Step-down</a><a href="#volume/survival">Survival line</a><a href="#volume/bands">Flow bands</a></nav>
    <p class="vhead" id="vol-head"></p><div class="vizwrap" id="vol-viz"></div><p class="swipe" id="vol-swipe">Swipe sideways to see the whole chart →</p>
    <div class="detail" id="vol-detail" aria-live="polite">Tap a mark for details.</div><p class="how" id="vol-how"></p>
  </section>
  <section class="card" data-view-panel="heat" hidden aria-labelledby="heat-h">
    <h1 id="heat-h">Heat grid</h1><p class="q">Which stage changed, and when?</p>
    <p class="vhead" id="heat-head"></p><div class="vizwrap" id="heat-viz"></div><p class="swipe" id="heat-swipe">Swipe sideways to see the whole chart →</p><p class="how" id="heat-how"></p>
    <div class="detail" id="heat-detail" aria-live="polite">Tap a cell for details.</div>
  </section>
  {agent_html}
  <section class="card insights" aria-labelledby="ins-h" data-view-panel="flow">
    <h1 id="ins-h">What changed</h1>
    <p class="q">Every figure is calculated from the same run log and compared with a baseline. Open “Explain this figure” to see how.</p>
    <div class="ins-grid"><nav class="rail" aria-label="Findings">{rail}</nav><div class="figs" id="figs"></div></div>
  </section>
</main>
<script id="pc-data" type="application/json">{payload}</script>
<script>{JS}</script>
</body></html>"""


def run(action: str, source: str | Path, output: str | Path | None = None, *,
        style_name: str | None = None, theme: str | None = None, video_output: str | Path | None = None,
        log=print) -> dict:
    if action not in ("validate", "render"):
        raise ValueError("choose validate or render")
    src = Path(source).expanduser().resolve()
    raw = src.read_bytes()
    norm = validate_spec(json.loads(raw))
    data = derive(norm)
    summary = {"ok": True, "input": str(src), "pipeline": norm["pipeline"], "stages": len(norm["stages"]),
               "runs": len(norm["runs"]), "days": len(norm["days"]), "baseline": data["source"]["baseline"],
               "figures": {f["id"]: {"latest": f["latest"], "baseline": f["ref"], "status": f["status"]} for f in data["figures"]}}
    if action == "validate":
        return summary
    if output is None:
        raise ValueError("render requires --output")
    if theme not in (None, "dark", "light"):
        raise ValueError("--theme must be dark or light")
    target = Path(output).expanduser().resolve()
    if target.suffix.lower() != ".html":
        raise ValueError("output must be .html")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Output exists; select a new path: {target}")
    out = render_html(norm, style_name, theme).encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as f:
        f.write(out)
    summary.update({"output": str(target), "style": style_name or norm["style"],
                    "input_sha256": hashlib.sha256(raw).hexdigest(), "output_sha256": hashlib.sha256(out).hexdigest()})
    if video_output:
        from creator_tools import showcase
        summary["video"] = showcase.record(target, video_output, log=log)
    return summary
