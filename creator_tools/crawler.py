"""Prompt-crawler adapter: crawl a prompt/SKILL.md, write a standalone viewer, optionally record it.

Heuristic (keyword) classification only; no model call. Confidence values are
rule-of-thumb scores, not calibrated probabilities. Viewer loads d3 from jsDelivr.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "integrations" / "prompt-crawler"


def _crawl_module():
    spec = importlib.util.spec_from_file_location("prompt_crawl", PKG / "crawl.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_viewer(data: dict) -> str:
    html = (PKG / "viz.html").read_text()
    anchor = "<script>\nconst COL"
    if anchor not in html:
        raise RuntimeError("viz.html injection anchor missing")
    return html.replace(anchor, "<script>\nconst DATA=" + json.dumps(data) + ";\nconst COL", 1)


def run(source, out_dir, *, video=False, speed=3.0, fps=30, log=print, scorer="heuristic",
        inventory=None, model_id=None, cascade=True, strong_id=None):
    src = Path(source).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(src)
    out = Path(out_dir).expanduser().resolve()
    if out.exists():
        raise FileExistsError("Output exists; select a new path")
    out.mkdir(parents=True)
    data = _crawl_module().crawl(src)
    data["method"] = "keyword heuristic, no model call"
    if scorer == "azure":
        from creator_tools import crawl_model
        data = crawl_model.score(data, inventory, model_id, log=log, cascade=cascade, strong_id=strong_id)
    (out / "crawl.json").write_text(json.dumps(data, indent=1))
    viewer = out / "viewer.html"
    viewer.write_text(build_viewer(data))
    result = {k: data[k] for k in ("decisions", "routes", "vague_count", "spec_score", "avg_confidence")}
    result.update(source=str(src), json=str(out / "crawl.json"), viewer=str(viewer), method=data["method"])
    if "cascade" in data:
        result["cascade"] = data["cascade"]
    if "agreement_with_heuristic" in data:
        result["agreement_with_heuristic"] = data["agreement_with_heuristic"]
    if video:
        from creator_tools import showcase
        rec = showcase.record(f"{viewer}?render=1&speed={speed}", out / "crawl.mp4", fps=fps, log=log)
        rec["poster"] = showcase.poster(out / "crawl.mp4", out / "poster.png")
        result["video"] = rec
    return result
