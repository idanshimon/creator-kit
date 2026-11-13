"""Ask agent for Mission Control pages: a loopback-only server that serves one rendered page
and a same-origin POST /ask backed by the GitHub Copilot CLI in non-interactive mode.

Grounding (all three reach the real inference boundary, see build_prompt / copilot_argv):
  1. the dashboard spec JSON (exactly what is on screen) + the item selected in the page,
  2. read-only file access to --context-dir (inside --workdir) plus files the spec cites,
  3. WorkIQ (live Microsoft 365) wired as an MCP stdio server for the Copilot session.

Read-only by construction: the Copilot session only gets view/grep/glob and the WorkIQ ask tool
(--available-tools), so it cannot run a shell, edit files or send mail. Prompts are passed as an
argv element (never a shell string). The server binds 127.0.0.1 and checks Host + Origin.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

READ_TOOLS = ["view", "grep", "glob"]
WORKIQ_TOOL = "workiq-ask_work_iq"
MAX_QUESTION = 2000
PATH_RE = re.compile(r"[\w.~-]+(?:/[\w.~ -]+)*\.(?:md|json|py|csv|html|txt|ya?ml)")
URL_RE = re.compile(r"https?://[^\s<>()\"'`\]]+[^\s<>()\"'`\].,;:!?]")

RULES = """You are the Ask agent inside Idan's account dashboard "{title}". Idan is a Microsoft HLS software SE.
Rules (follow all of them):
- Answer in plain, short English. Lead with the answer. Keep it under ~150 words unless asked for more.
- Ground every fact and cite it inline: a file path relative to the repo root (for example `{ctx_rel}/personas.md`),
  "dashboard: <item id>" for numbers shown on the dashboard, or the WorkIQ item (title + link if WorkIQ gave one).
- If the record does not say, write "not in record". Never guess or fill gaps.
- Read-only: never edit files, never send email/messages/invites, never write to MSX/CRM. You only have read tools.
- Customer data stays local: do not fetch web URLs or paste record content anywhere else.
- Sources, in order:
  1. DASHBOARD SPEC below = exactly what is on screen (items, numbers, details, evidence). It is a summary:
     for people, history, "who/why/what happened" questions, also open the hub file its evidence names
     (e.g. personas.md, meeting-notes/...) and cite that file path, not only the dashboard id.
  2. Files under `{ctx_rel}/` (start with index.md, personas.md, open-items.md, opp-history.md, meeting-notes/)
     and these files the dashboard cites: {extra}. Your working directory is `{ctx_abs}`
     (repo root: `{workdir}`); read only these locations. Cite paths relative to the repo root.
  3. The {workiq} tool for live Microsoft 365 (email, Teams, meetings, files). Use it for anything recent or
     live ("new", "today", "this week", inbox, chats, meetings). Say which question you asked it.
Today is {today}.
"""


class AskConfig:
    def __init__(self, page, spec, workdir, context_dirs, extra_files=(), copilot="copilot",
                 workiq="workiq", model=None, timeout=300, log_path=None, use_workiq=True):
        self.page = Path(page).expanduser().resolve()
        self.spec_path = Path(spec).expanduser().resolve()
        self.workdir = Path(workdir).expanduser().resolve()
        if not self.page.is_file():
            raise FileNotFoundError(f"page not found: {self.page}")
        if not self.spec_path.is_file():
            raise FileNotFoundError(f"spec not found: {self.spec_path}")
        if not self.workdir.is_dir():
            raise NotADirectoryError(f"workdir not found: {self.workdir}")
        self.context_dirs = [self._inside(d, want_dir=True) for d in (context_dirs or [])]
        if not self.context_dirs:
            raise ValueError("at least one --context-dir is required")
        self.spec = json.loads(self.spec_path.read_text())
        cited = set(self._inside(f) for f in extra_files)
        cited |= set(cited_files(self.spec, self.workdir, self.context_dirs))
        self.extra_files = sorted(f for f in cited if not any(_under(f, d) for d in self.context_dirs))
        self.copilot = shutil.which(copilot) or copilot
        self.workiq = (shutil.which(workiq) or workiq) if use_workiq else None
        self.model = model
        self.timeout = int(timeout)
        self.log_path = Path(log_path).expanduser().resolve() if log_path else None
        self._lock = threading.Semaphore(2)

    def _inside(self, rel, want_dir=False) -> Path:
        p = Path(rel).expanduser()
        p = (p if p.is_absolute() else self.workdir / p).resolve()
        if not _under(p, self.workdir):
            raise ValueError(f"path escapes workdir: {rel}")
        if want_dir and not p.is_dir():
            raise NotADirectoryError(f"context dir not found: {p}")
        if not want_dir and not p.is_file():
            raise FileNotFoundError(f"context file not found: {p}")
        return p

    def rel(self, p: Path) -> str:
        return str(p.relative_to(self.workdir))

    def allowed(self, p: Path) -> bool:
        p = p.resolve()
        return any(_under(p, d) for d in self.context_dirs) or p in self.extra_files

    def resolve_source(self, token: str) -> Path | None:
        """Map a path the model cited (repo- or context-relative) to an allowed file."""
        token = token.strip().strip("`'\"").lstrip("./")
        if not token or ".." in Path(token).parts:
            return None
        for base in [self.workdir, *self.context_dirs]:
            p = (base / token).resolve()
            if p.is_file() and _under(p, self.workdir) and self.allowed(p):
                return p
        return None


def _under(p: Path, root: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def cited_files(spec: dict, workdir: Path, context_dirs) -> list[Path]:
    """Files the spec cites that exist under workdir (relative to workdir or a context dir)."""
    out = set()
    for s in _strings(spec):
        for tok in PATH_RE.findall(s):
            if "..." in tok or tok.startswith("http"):
                continue
            for base in [workdir, *context_dirs]:
                p = (base / tok).resolve()
                if p.is_file() and _under(p, workdir):
                    out.add(p)
                    break
    return sorted(out)


def build_prompt(cfg: AskConfig, question: str, selected: dict | None) -> str:
    sel_txt = "none"
    if selected and isinstance(selected, dict):
        sid = str(selected.get("id", ""))[:80]
        ent = next((e for e in cfg.spec.get("entities", []) if e.get("id") == sid), None)
        if ent:
            sel_txt = json.dumps(ent, ensure_ascii=False)
    rules = RULES.format(
        title=cfg.spec.get("title", "dashboard"),
        ctx_rel=", ".join(cfg.rel(d) for d in cfg.context_dirs),
        extra=", ".join(f"`{cfg.rel(f)}`" for f in cfg.extra_files) or "none",
        ctx_abs=str(cfg.context_dirs[0]), workdir=str(cfg.workdir),
        workiq=WORKIQ_TOOL if cfg.workiq else "(WorkIQ disabled: say live M365 is not available)",
        today=_dt.date.today().isoformat(),
    )
    return (rules + "\nCURRENTLY SELECTED ITEM ON SCREEN:\n" + sel_txt
            + "\n\nDASHBOARD SPEC (JSON, what is on screen):\n" + json.dumps(cfg.spec, ensure_ascii=False)
            + "\n\nQUESTION FROM IDAN:\n" + question.strip() + "\n")


def _other_mcp_servers() -> list[str]:
    try:
        cfg = json.loads((Path.home() / ".copilot" / "mcp-config.json").read_text())
        return sorted(cfg.get("mcpServers", {}))
    except Exception:
        return []


def copilot_argv(cfg: AskConfig, prompt: str, mcp_config_path: str | None) -> list[str]:
    # Session cwd = the first context dir; path verification then only admits it, the other
    # context dirs and the folders of files the dashboard cites (--add-dir), not the whole repo.
    argv = [cfg.copilot, "-C", str(cfg.context_dirs[0]), "-p", prompt, "-s", "--output-format", "json",
            "--no-ask-user", "--disable-builtin-mcps", "--disallow-temp-dir"]
    for d in sorted({*cfg.context_dirs[1:], *(f.parent for f in cfg.extra_files)}):
        argv += ["--add-dir", str(d)]
    for name in _other_mcp_servers():
        if name != "workiq":
            argv += ["--disable-mcp-server", name]
    tools = list(READ_TOOLS)
    if cfg.workiq and mcp_config_path:
        argv += ["--additional-mcp-config", "@" + mcp_config_path]
        tools.append(WORKIQ_TOOL)
    argv += ["--available-tools", *tools]
    for t in READ_TOOLS:
        argv += ["--allow-tool", t]
    if cfg.workiq:
        argv += ["--allow-tool", "workiq"]
    if cfg.model:
        argv += ["--model", cfg.model]
    return argv


def parse_events(text: str) -> dict:
    answer, tools, results = "", [], []
    for line in text.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        t, d = o.get("type"), o.get("data") or {}
        if t == "assistant.message" and d.get("content"):
            answer = d["content"]
        elif t == "tool.execution_start":
            args = d.get("arguments")
            tools.append({"name": d.get("toolName", "?"),
                          "args": json.dumps(args, ensure_ascii=False)[:400] if args is not None else ""})
        elif t == "tool.execution_complete":
            r = d.get("result") or {}
            results.append(str(r.get("content", ""))[:20000] if isinstance(r, dict) else str(r)[:20000])
    return {"answer": answer, "tools": tools, "tool_results": results}


def sources_for(cfg: AskConfig, answer: str, tools: list[dict]) -> list[dict]:
    seen, out = set(), []
    for tok in PATH_RE.findall(answer):
        p = cfg.resolve_source(tok)
        if p and p not in seen:
            seen.add(p)
            out.append({"label": cfg.rel(p), "href": cfg.rel(p)})
    for u in URL_RE.findall(answer):
        if u not in seen:
            seen.add(u)
            out.append({"label": urlparse(u).netloc + " link", "href": u})
    for t in tools:
        if t["name"] in READ_TOOLS:
            try:
                path = json.loads(t["args"]).get("path", "")
            except Exception:
                path = ""
            p = Path(path).resolve() if path else None
            if p and p.is_file() and cfg.allowed(p) and p not in seen:
                seen.add(p)
                out.append({"label": "read " + cfg.rel(p), "href": cfg.rel(p)})
    return out[:16]


def run_ask(cfg: AskConfig, question: str, selected: dict | None, runner=subprocess.run) -> dict:
    prompt = build_prompt(cfg, question, selected)
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="mc-ask-") as tmp:
        mcp_path = None
        if cfg.workiq:
            mcp_path = os.path.join(tmp, "mcp.json")
            Path(mcp_path).write_text(json.dumps({"mcpServers": {"workiq": {
                "type": "stdio", "command": cfg.workiq, "args": ["mcp"], "tools": ["*"]}}}))
        argv = copilot_argv(cfg, prompt, mcp_path)
        try:
            proc = runner(argv, capture_output=True, text=True, timeout=cfg.timeout,
                          stdin=subprocess.DEVNULL, cwd=str(cfg.context_dirs[0]))
        except subprocess.TimeoutExpired:
            return {"error": f"Copilot did not finish in {cfg.timeout}s."}
        except FileNotFoundError:
            return {"error": f"Copilot CLI not found: {cfg.copilot}"}
    ev = parse_events(proc.stdout or "")
    if proc.returncode != 0 or not ev["answer"]:
        tail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()[-800:]
        return {"error": f"Copilot CLI exit {proc.returncode}: {tail or 'no answer'}", "tools": ev["tools"]}
    return {"answer": ev["answer"], "tools": ev["tools"],
            "sources": sources_for(cfg, ev["answer"], ev["tools"]),
            "seconds": round(time.time() - t0, 1)}


def make_handler(cfg: AskConfig, port_ref: dict, log=print):
    def write_log(rec):
        if cfg.log_path:
            cfg.log_path.parent.mkdir(parents=True, exist_ok=True)
            with cfg.log_path.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    class H(BaseHTTPRequestHandler):
        server_version = "MissionControlAsk/1"

        def log_message(self, fmt, *a):
            log("[ask] " + (fmt % a))

        def _hosts(self):
            p = port_ref["port"]
            return {f"127.0.0.1:{p}", f"localhost:{p}"}

        def _send(self, code, body: bytes, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _host_ok(self):
            if self.headers.get("Host", "") not in self._hosts():
                self._json(421, {"error": "bad Host"})
                return False
            return True

        def do_GET(self):
            if not self._host_ok():
                return
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                csp = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                return self._send(200, cfg.page.read_bytes(), "text/html; charset=utf-8",
                                  {"Content-Security-Policy": csp})
            if u.path == "/ask/health":
                return self._json(200, {"ok": True, "label": "GHCP" + (" + WorkIQ" if cfg.workiq else ""),
                                        "context": [cfg.rel(d) for d in cfg.context_dirs],
                                        "cited_files": len(cfg.extra_files)})
            if u.path == "/src":
                tok = (parse_qs(u.query).get("p") or [""])[0]
                p = cfg.resolve_source(tok)
                if not p:
                    return self._json(404, {"error": "not an allowed source file"})
                return self._send(200, p.read_bytes(), "text/plain; charset=utf-8",
                                  {"Content-Security-Policy": "sandbox"})
            self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok():
                return
            if urlparse(self.path).path != "/ask":
                return self._json(404, {"error": "not found"})
            origin = self.headers.get("Origin", "")
            if origin not in {"http://" + h for h in self._hosts()}:
                return self._json(403, {"error": "bad Origin"})
            if self.headers.get("X-MC-Ask") != "1" or "application/json" not in self.headers.get("Content-Type", ""):
                return self._json(403, {"error": "missing X-MC-Ask / JSON content type"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 20000:
                return self._json(413, {"error": "bad body size"})
            try:
                body = json.loads(self.rfile.read(n))
                question = str(body.get("question", ""))[:MAX_QUESTION]
                selected = body.get("selected") if isinstance(body.get("selected"), dict) else None
            except Exception:
                return self._json(400, {"error": "bad JSON"})
            if not question.strip():
                return self._json(400, {"error": "empty question"})
            if not cfg._lock.acquire(timeout=5):
                return self._json(429, {"error": "busy: two questions already running"})
            try:
                t0 = time.time()
                res = run_ask(cfg, question, selected)
            finally:
                cfg._lock.release()
            write_log({"ts": _dt.datetime.now().isoformat(timespec="seconds"), "question": question,
                       "selected": (selected or {}).get("id"), "tools": res.get("tools", []),
                       "ok": "answer" in res, "seconds": round(time.time() - t0, 1),
                       "answer": res.get("answer", res.get("error", ""))[:4000]})
            log(f"[ask] q={question[:80]!r} tools={[t['name'] for t in res.get('tools', [])]} ok={'answer' in res}")
            self._json(200 if "answer" in res else 502, res)

    return H


def serve(cfg: AskConfig, port: int = 0, log=print, ready=None):
    port_ref = {"port": port}
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(cfg, port_ref, log))
    port_ref["port"] = httpd.server_address[1]
    url = f"http://127.0.0.1:{port_ref['port']}/"
    log(json.dumps({"ok": True, "url": url, "page": str(cfg.page), "context": [cfg.rel(d) for d in cfg.context_dirs],
                    "cited_files": [cfg.rel(f) for f in cfg.extra_files], "workiq": bool(cfg.workiq),
                    "log": str(cfg.log_path) if cfg.log_path else None}))
    if ready:
        ready(httpd, url)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
