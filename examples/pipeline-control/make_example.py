"""Generate the synthetic example run log for creator.py pipeline-control.

Deterministic (seed 4812). Story: a new runner image on 2026-11-04 makes the
Integration test database start cold, so Integration and cost per run jump.
Run: python3.13 examples/pipeline-control/make_example.py
"""
import datetime as dt
import json
import random
from pathlib import Path

STAGES = [("commit", "Commit", 0.5), ("build", "Build", 4), ("unit", "Unit tests", 6), ("integ", "Integration", 7),
          ("scan", "Security scan", 3), ("staging", "Staging deploy", 4), ("canary", "Canary 5%", 5), ("prod", "Production", 2)]
rng = random.Random(4812)
start = dt.date(2026, 10, 24)
runs, n = [], 4300
for d in range(14):
    day = start + dt.timedelta(days=d)
    for k in range(26 + (d * 7) % 9):
        n += 1
        mins, status, failed = {}, "passed", None
        fail_at = None
        roll = rng.random()
        if roll < 0.035: fail_at = "unit"
        elif roll < 0.06: fail_at = "integ"
        elif roll < (0.072 if d < 7 else 0.085): fail_at = "scan"
        for sid, _, base in STAGES:
            v = max(0.1, rng.gauss(base, base * 0.12))
            if sid == "integ" and day >= dt.date(2026, 11, 4):
                v += rng.gauss(15.5, 2.0)
            mins[sid] = round(v, 2)
            if sid == fail_at:
                status, failed = "failed", sid
                break
        retried = status == "passed" and rng.random() < 0.06
        runs.append({"id": f"#{n}", "date": day.isoformat(), "status": status, "failed_stage": failed,
                     "first_try": status == "passed" and not retried, "stage_minutes": mins})

spec = {
    "schema_version": 1,
    "title": "Pipeline Control",
    "pipeline": "checkout-service",
    "subtitle": "CI/CD",
    "data_label": "Synthetic data",
    "style": "claude",
    "runner_rate_usd_per_min": 0.008,
    "rate_note": "per runner minute (assumed GitHub-hosted Linux list price; replace with your rate)",
    "stages": [{"id": s, "name": nm} for s, nm, _ in STAGES],
    "baseline": {"until": "2026-11-03", "label": "the new runner image"},
    "runs": runs,
    "live": {
        "stage_state": {"integ": "slow", "scan": "failed"},
        "runs": [
            {"id": "#4821", "stage": "build", "progress": 0.55, "state": "running", "message": "fix: retry header parsing"},
            {"id": "#4820", "stage": "unit", "progress": 0.30, "state": "running", "message": "feat: saved carts"},
            {"id": "#4819", "stage": "unit", "state": "waiting", "message": "chore: bump eslint"},
            {"id": "#4818", "stage": "unit", "state": "waiting", "message": "feat: gift cards"},
            {"id": "#4817", "stage": "unit", "state": "waiting", "message": "fix: tax rounding"},
            {"id": "#4816", "stage": "unit", "state": "waiting", "message": "refactor: cart service"},
            {"id": "#4814", "stage": "unit", "state": "waiting", "message": "docs: api examples"},
            {"id": "#4813", "stage": "unit", "state": "waiting", "message": "fix: currency format"},
            {"id": "#4815", "stage": "integ", "progress": 0.55, "state": "running", "message": "feat: promo codes"},
            {"id": "#4812", "stage": "scan", "state": "failed", "message": "chore: update lodash"},
            {"id": "#4811", "stage": "staging", "progress": 0.60, "state": "running", "message": "feat: wishlist"},
            {"id": "#4810", "stage": "canary", "progress": 0.35, "state": "running", "message": "fix: null session"},
            {"id": "#4809", "stage": "prod", "state": "done", "message": "feat: address book"},
        ],
    },
    "agent": {
        "stage": "scan",
        "finding": "Run #4812 is blocked at Security scan: lodash 4.17.20 has a known prototype-pollution advisory. Integration has been slow since the new runner image, so runs queue behind it.",
        "action": "Open a PR pinning lodash to 4.17.21 and re-run #4812. Pre-warm the test database on the new runner image.",
        "evidence": ["Scan report: 1 high finding in lodash 4.17.20"],
    },
}
out = Path(__file__).with_name("checkout-service.pipeline.json")
out.write_text(json.dumps(spec, indent=1) + "\n")
print(out, len(runs), "runs")
