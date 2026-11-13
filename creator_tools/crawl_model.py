"""Model-scored routing for prompt-crawler via Azure logprobs.

Each instruction gets one multiple-choice question; the deployment returns a
probability per letter. Routing: approval -> human; checkable rule with p>=0.95 -> code;
everything else -> model. Probabilities are the model's own, not calibrated accuracy.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from creator_tools import models

LETTERS = {"A": "rule", "B": "info", "C": "approval", "D": "ambiguous", "E": "sourced"}
PROMPT = """You are auditing one instruction from an AI agent's skill/prompt file.
Pick the ONE letter that best describes it:
A = a concrete rule that ordinary code or a linter could check deterministically
B = guidance that needs judgment by a model to apply
C = requires a human's approval or confirmation before acting
D = vague or ambiguous: two careful readers could apply it differently
E = a pointer to a specific file, command, URL or source to read
Section: {section}
Instruction: {text}
Answer with the letter only."""


def route(probs: dict, threshold: float = 0.95) -> tuple[str, str, float]:
    letter = max(probs, key=probs.get)
    p = probs[letter]
    kind = LETTERS[letter]
    if probs["C"] >= 0.5:
        return "approval", "human", probs["C"]
    if letter in ("A", "E") and p >= threshold:
        return kind, "code", p
    if p < 0.6:  # no clear answer: hand to a human instead of guessing
        return kind, "human", p
    return kind, "model", p


ESCALATE_BELOW = 0.6  # tier-1 top answer under this -> ask the strong model


def best_strong(inventory, same_account_as=None):
    """Strongest non-mini GPT-5.x chat deployment (higher version; 'sol' over plain; on ties,
    the same Azure account as tier 1 so data stays in one resource)."""
    home = same_account_as.split("/")[0] if same_account_as else None
    import re
    best = None
    for r in models.model_rows(inventory):
        d = r["deployment"].lower()
        m = re.fullmatch(r"gpt-(\d+)(?:[.-](\d+))?(-[a-z]+)?", d)
        if r["capability"] != "chat" or r["state"] != "Succeeded" or not m or (m.group(3) or "") in ("-mini", "-nano", "-chat", "-codex"):
            continue
        key = (int(m.group(1)), int(m.group(2) or 0), 1 if m.group(3) == "-sol" else 0,
               1 if r["id"].split("/")[0] == home else 0)
        if best is None or key > best[0]:
            best = (key, r["id"])
    return best[1] if best else None


def score(data: dict, inventory: dict, model_id: str | None = None, workers: int = 12, log=print,
          cascade: bool = True, strong_id: str | None = None) -> dict:
    """Cascade (HydraFusion-style): efficient model answers all; a quality gate escalates the
    undecided ones to a stronger model; anything still undecided goes to a human."""
    import time
    model_id = model_id or models.best_mini(inventory)
    strong_id = (strong_id or best_strong(inventory, model_id)) if cascade else None
    token = models.access_token(inventory["subscription"])
    nodes = data["nodes"]

    def ask(mid, n):
        t = time.time()
        probs = models.choice_probs(inventory, mid, PROMPT.format(section=n["section"], text=n["text"]),
                                    list(LETTERS), token=token)
        return probs, round((time.time() - t) * 1000)

    def apply(n, probs, tier, mid, ms):
        kind, rt, p = route(probs)
        n.update(kind=kind, route=rt, p=round(p, 3), scores={LETTERS[k]: v for k, v in probs.items()})
        n.setdefault("legs", []).append({"tier": tier, "model": mid.split("/")[-1], "top": max(probs, key=probs.get),
                                         "p": round(max(probs.values()), 3), "ms": ms})
        n["tier"] = tier

    t0 = time.time()
    for n in nodes:
        n["heuristic_route"] = n["route"]
    with ThreadPoolExecutor(workers) as ex:
        for done, (n, (probs, ms)) in enumerate(zip(nodes, ex.map(lambda n: ask(model_id, n), nodes)), 1):
            apply(n, probs, 1, model_id, ms)
            if log and done % 50 == 0:
                log(f"  tier1 {done}/{len(nodes)}")
    gated = [n for n in nodes if max(n["scores"].values()) < ESCALATE_BELOW]
    if strong_id and gated:
        log and log(f"  gate: {len(gated)} undecided -> {strong_id}")
        with ThreadPoolExecutor(workers) as ex:
            for n, (probs, ms) in zip(gated, ex.map(lambda n: ask(strong_id, n), gated)):
                apply(n, probs, 2, strong_id, ms)
    for n in nodes:
        n["escalated"] = n["tier"] == 2
        n["to_human_after_cascade"] = n["route"] == "human" and max(n["scores"].values()) < ESCALATE_BELOW
    data["cascade"] = {
        "pattern": "cascade" if strong_id else "single",
        "tier1": model_id, "tier2": strong_id, "gate": f"top answer < {ESCALATE_BELOW}",
        "tier1_calls": len(nodes), "escalated": len(gated) if strong_id else 0,
        "resolved_by_tier2": sum(1 for n in gated if strong_id and max(n["scores"].values()) >= ESCALATE_BELOW),
        "still_undecided": sum(n["to_human_after_cascade"] for n in nodes),
        "wall_seconds": round(time.time() - t0, 1)}
    from collections import Counter
    data["routes"] = Counter(n["route"] for n in nodes)
    data["kinds"] = Counter(n["kind"] for n in nodes)
    data["vague_count"] = sum(1 for n in nodes if n["kind"] == "ambiguous")
    data["top_vague"] = Counter(w for n in nodes if n["kind"] == "ambiguous" for w in n.get("vague", [])).most_common(8)
    data["avg_confidence"] = round(sum(n["p"] for n in nodes) / max(len(nodes), 1), 3)
    data["log"] = [f"{n['route']:5} {n['kind']:9} p={n['p']:.2f} :: {n['text'][:60]}" for n in nodes]
    cov = sum(data["coverage"].values()) / len(data["coverage"])
    det = (data["routes"]["code"] + data["routes"]["human"]) / max(len(nodes), 1)
    amb = data["vague_count"] / max(len(nodes), 1)
    data["spec_score"] = round(40 * cov + 30 * (1 - min(1, amb * 5)) + 30 * det)
    data["method"] = (f"Azure cascade {model_id.split('/')[-1]} -> {strong_id.split('/')[-1]}" if strong_id
                      else f"Azure {model_id.split('/')[-1]}") + " logprobs"
    data["agreement_with_heuristic"] = round(sum(n["route"] == n["heuristic_route"] for n in nodes) / max(len(nodes), 1), 3)
    return data
