#!/usr/bin/env python3
"""prompt-crawler: read a prompt/SKILL.md as a set of decisions, not text.

Every sentence-level instruction is classified (rule / approval / ambiguous / sourced / info)
with a heuristic confidence, then routed:
  p >= 0.95 & checkable  -> CODE   (could be enforced deterministically, no model call)
  needs approval          -> HUMAN
  otherwise               -> MODEL  (judgment the model has to make)
Heuristic only: no LLM is called. Output: JSON for viz.html.
"""
import json, re, sys, collections, pathlib

RULE = r"\b(must|never|always|do not|don't|only|required?|mandatory|forbidden)\b"
APPROVAL = r"\b(ask|confirm|approv\w*|permission|user decides|before (?:any|you) (?:write|send|post|publish|delete)|sign[- ]off)\b"
VAGUE = r"\b(appropriate\w*|relevant|good|better|properly|reasonable|as needed|if needed|usually|often|sometimes|some|maybe|might|try to|consider|etc|nice|clean|simple|quick\w*)\b"
SOURCED = r"(`[^`]+`|https?://\S+|~/\S+|\b\w+\.(?:md|py|json|yaml|sh)\b)"
CHECKABLE = r"(`[^`]+`|\b\d+\b|https?://|\.md\b|\bexit code\b|\bflag\b|--\w+)"
EXPECTED = {"trigger": r"use when|trigger|when to", "steps": r"step|workflow|procedure|how to",
            "pitfalls": r"pitfall|gotcha|mistake|don't|never", "examples": r"example|e\.g\.",
            "verification": r"verif|check|test|prove", "output": r"output|format|deliverable|return"}

def hits(p, s): return len(re.findall(p, s, re.I))

def classify(s):
    r, a, v, src = hits(RULE, s), hits(APPROVAL, s), hits(VAGUE, s), hits(SOURCED, s)
    words = max(len(s.split()), 1)
    scores = {
        "approval": min(0.99, 0.55 + 0.25 * a) if a else 0.0,
        "rule": min(0.99, 0.6 + 0.2 * r + (0.15 if hits(CHECKABLE, s) else 0)) if r else 0.0,
        "ambiguous": min(0.95, 0.4 + 0.15 * v + (0.1 if words > 35 else 0)) if v else 0.0,
        "sourced": min(0.97, 0.7 + 0.1 * src) if src else 0.0,
    }
    kind, p = max(scores.items(), key=lambda kv: kv[1])
    if p == 0: kind, p = "info", 0.9
    if kind == "approval": route = "human"
    elif p >= 0.95 and kind in ("rule", "sourced") and hits(CHECKABLE, s): route = "code"
    else: route = "model"
    return kind, round(p, 3), route, scores

def crawl(path):
    text = pathlib.Path(path).read_text()
    text = re.sub(r"^---.*?---\s*", "", text, flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    sections, cur = collections.OrderedDict(), "preamble"
    sections[cur] = []
    for line in text.splitlines():
        m = re.match(r"^#{1,4}\s+(.*)", line)
        if m: cur = m.group(1).strip().lstrip("#").strip()[:40]; sections.setdefault(cur, []); continue
        if line.strip(): sections[cur].append(line.strip())
    nodes, log, words = [], [], collections.Counter()
    for sec, lines in sections.items():
        body = " ".join(lines)
        for s in re.split(r"(?<=[.!?])\s+|\s+-\s+|\|", body):
            s = s.strip(" -*|")
            if len(s.split()) < 4: continue
            kind, p, route, sc = classify(s)
            vague = re.findall(VAGUE, s, re.I)
            if vague and route == "code": route = "model"  # vague wording can't be enforced in code
            nodes.append({"id": len(nodes), "section": sec, "text": s[:220], "kind": kind,
                          "p": p, "route": route, "scores": sc, "vague": sorted(set(w.lower() for w in vague))})
            log.append(f"{route:5} {kind:9} p={p:.2f} :: {s[:60]}")
            words.update(w for w in re.findall(r"[a-z]{4,}", s.lower()))
    full = text.lower()
    coverage = {k: (1 if re.search(v, full) else 0) for k, v in EXPECTED.items()}
    routes = collections.Counter(n["route"] for n in nodes)
    kinds = collections.Counter(n["kind"] for n in nodes)
    amb = sum(1 for n in nodes if n["vague"]) / max(len(nodes), 1)
    # 40% expected sections present, 30% free of vague wording, 30% share that is deterministic
    # (code-enforceable or an explicit human gate) rather than left to model judgment
    det = (routes["code"] + routes["human"]) / max(len(nodes), 1)
    spec = round(40 * sum(coverage.values()) / len(coverage) + 30 * (1 - min(1, amb * 5)) + 30 * det)
    stop = set("this that with from your when then what they will have into each only does also more than".split())
    return {"file": str(path), "word_count": len(text.split()), "decisions": len(nodes),
            "routes": routes, "kinds": kinds, "vague_count": sum(1 for n in nodes if n["vague"]),
            "top_vague": collections.Counter(w for n in nodes for w in n["vague"]).most_common(8), "coverage": coverage, "spec_score": spec,
            "avg_confidence": round(sum(n["p"] for n in nodes) / max(len(nodes), 1), 3),
            "sections": [{"name": k, "n": sum(1 for n in nodes if n["section"] == k)} for k in sections],
            "nodes": nodes, "log": log,
            "word_heat": [w for w in words.most_common(60) if w[0] not in stop][:30]}

if __name__ == "__main__":
    out = crawl(sys.argv[1])
    dst = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "crawl.json")
    dst.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("file", "word_count", "decisions", "routes", "kinds", "vague_count", "top_vague",
                                          "coverage", "spec_score", "avg_confidence")}, indent=1))
