#!/usr/bin/env python3
"""
server.py — 3-agent team web dashboard server.

Usage:
  python3 server.py [project-dir] [-n SESSION] [--port PORT]
  Or: dashboard-web (global command)
"""
import argparse
import asyncio
import json
import re
import socket
import sys
import threading
import webbrowser
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, Response, StreamingResponse
    import uvicorn
except ImportError:
    print("error: pip install fastapi uvicorn", file=sys.stderr)
    sys.exit(1)

DEFAULT_PORT = 7654
POLL = 1.0
STATIC_DIR = Path(__file__).resolve().parent / "static"

# ── Log parsers ───────────────────────────────────────────────────────────────

def _between(text: str, start: str, end: str) -> str:
    m = re.search(rf"=== {re.escape(start)} ===\s*\n(.*?)(?:=== {re.escape(end)}|$)",
                  text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _heading_body(text: str, heading: str) -> str:
    m = re.search(rf"### {re.escape(heading)}.*?\n(.*?)(?:###|##|$)", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_gemini(path: Path) -> dict:
    if not path.exists():
        return {"status": "waiting", "ts": "", "query": "", "response": "", "sources": 0}
    t = path.read_text(errors="replace")
    ts_m = re.search(r"ask-gemini\.sh @ (\S+)", t)
    query = _between(t, "QUERY", "RESPONSE")
    response = _between(t, "RESPONSE", "END (rc")
    done = "=== END" in t
    rc_m = re.search(r"=== END \(rc=(\d+)\)", t)
    rc = int(rc_m.group(1)) if rc_m else -1
    status = ("done" if rc == 0 else "failed") if done else ("running" if query else "waiting")
    return dict(status=status, ts=ts_m.group(1) if ts_m else "",
                query=query, response=response,
                sources=len(re.findall(r"https?://", response)), rc=rc)


def parse_codex(path: Path) -> dict:
    if not path.exists():
        return {"status": "waiting", "ts": "", "focus": "", "verdict": "",
                "word": "", "findings": {}, "response": ""}
    t = path.read_text(errors="replace")
    ts_m = re.search(r"ask-codex\.sh @ (\S+)", t)
    focus = _between(t, "FOCUS", "RESPONSE")
    tok, end = t.find("tokens used"), t.find("=== END")
    response = (t[tok + len("tokens used"):end].strip()
                if tok != -1 and end != -1 else _between(t, "RESPONSE", "END"))
    done = "=== END" in t
    rc_m = re.search(r"=== END \(rc=(\d+)\)", t)
    rc = int(rc_m.group(1)) if rc_m else -1
    status = ("done" if rc == 0 else "failed") if done else ("running" if focus else "waiting")
    v_m = re.search(r"## Verdict\s*\n(.+)", response)
    verdict = v_m.group(1).strip() if v_m else ""
    word = verdict.split()[0] if verdict else ""
    findings = {k: len(re.findall(r"^- (?!none)", _heading_body(response, k), re.I | re.M))
                for k in ("Blocker", "Major", "Minor / Nit")}
    return dict(status=status, ts=ts_m.group(1) if ts_m else "",
                focus=focus, verdict=verdict, word=word,
                findings=findings, response=response, rc=rc)

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Agent Dashboard")
_log_dir: Path = Path(".")
_team: str = "default"


@app.get("/")
async def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text())


@app.get("/static/style.css")
async def css():
    return Response((STATIC_DIR / "style.css").read_text(), media_type="text/css")


@app.get("/static/dashboard.js")
async def js():
    return Response((STATIC_DIR / "dashboard.js").read_text(), media_type="application/javascript")


@app.get("/config")
async def config():
    return {"team": _team, "log_dir": str(_log_dir)}


@app.get("/events")
async def events():
    async def stream():
        gemini_log = _log_dir / "latest-gemini.log"
        codex_log  = _log_dir / "latest-codex.log"
        mtimes = {"gemini": 0, "codex": 0}
        seen: set = set()

        # Initial state push
        yield f"event: gemini\ndata: {json.dumps(parse_gemini(gemini_log))}\n\n"
        yield f"event: codex\ndata: {json.dumps(parse_codex(codex_log))}\n\n"

        while True:
            # Gemini
            try:
                mt = gemini_log.stat().st_mtime if gemini_log.exists() else 0
            except OSError:
                mt = 0
            if mt != mtimes["gemini"]:
                mtimes["gemini"] = mt
                yield f"event: gemini\ndata: {json.dumps(parse_gemini(gemini_log))}\n\n"

            # Codex
            try:
                mt = codex_log.stat().st_mtime if codex_log.exists() else 0
            except OSError:
                mt = 0
            if mt != mtimes["codex"]:
                mtimes["codex"] = mt
                yield f"event: codex\ndata: {json.dumps(parse_codex(codex_log))}\n\n"

            # Activity: new log files
            if _log_dir.exists():
                for f in sorted(_log_dir.glob("*.log")):
                    if f.name.startswith("latest-") or f in seen:
                        continue
                    seen.add(f)
                    agent = "gemini" if "gemini" in f.name else "codex"
                    ts = f.stem.replace("gemini-", "").replace("codex-", "")
                    yield (f"event: activity\n"
                           f"data: {json.dumps({'agent': agent, 'ts': ts})}\n\n")

            yield "event: heartbeat\ndata: {}\n\n"
            await asyncio.sleep(POLL)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache",
                 "X-Accel-Buffering": "no",
                 "Access-Control-Allow-Origin": "*"},
    )

# ── Entry point ───────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def main() -> None:
    global _log_dir, _team

    p = argparse.ArgumentParser(description="3-agent team web dashboard")
    p.add_argument("project", nargs="?", default=".", help="project root (default: cwd)")
    p.add_argument("-n", "--name", default=None, help="team/session name")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default: {DEFAULT_PORT})")
    args = p.parse_args()

    root = Path(args.project).resolve()
    agents_dev = root / ".agents-dev"
    if not agents_dev.exists():
        print(f"error: .agents-dev not found in {root}", file=sys.stderr)
        print("       Run 'harness-install' first.", file=sys.stderr)
        sys.exit(1)

    log_base = agents_dev / "log"
    if args.name:
        team = args.name.replace("/", "-")
    elif log_base.exists():
        dirs = [d for d in log_base.iterdir() if d.is_dir()]
        team = dirs[0].name if len(dirs) == 1 else root.name
    else:
        team = root.name

    _team = team
    _log_dir = log_base / team
    _log_dir.mkdir(parents=True, exist_ok=True)

    local_ip = _local_ip()
    port = args.port

    print(f"\n  ┌─────────────────────────────────────┐")
    print(f"  │   3-Agent Team Dashboard            │")
    print(f"  │   team : {team:<28} │")
    print(f"  │                                     │")
    print(f"  │   Local  : http://localhost:{port}  │")
    print(f"  │   Network: http://{local_ip}:{port:<5}       │")
    print(f"  │                                     │")
    print(f"  │   Ctrl+C to stop                    │")
    print(f"  └─────────────────────────────────────┘\n")

    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
