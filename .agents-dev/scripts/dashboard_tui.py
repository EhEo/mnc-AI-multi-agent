#!/usr/bin/env python3
"""
dashboard_tui.py — 3-panel agent team dashboard. No tmux required.

Usage:
  ./dashboard_tui.py                      # current dir as project root
  ./dashboard_tui.py /path/to/project     # explicit project root
  ./dashboard_tui.py -n SESSION           # specific team/session name
  ./dashboard_tui.py --help

Requires: pip install textual
"""
import argparse
import re
import sys
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Header, RichLog, Static
except ImportError:
    print("error: textual not installed. Run: pip install textual", file=sys.stderr)
    sys.exit(1)

POLL = 1.0  # seconds


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
        return {"status": "waiting"}
    t = path.read_text(errors="replace")
    ts_m = re.search(r"ask-gemini\.sh @ (\S+)", t)
    query = _between(t, "QUERY", "RESPONSE")
    response = _between(t, "RESPONSE", "END (rc")
    done = "=== END" in t
    rc_m = re.search(r"=== END \(rc=(\d+)\)", t)
    rc = int(rc_m.group(1)) if rc_m else -1
    status = ("done" if rc == 0 else "failed") if done else ("running" if query else "waiting")
    sources = len(re.findall(r"https?://", response))
    lead = next((l for l in response.splitlines() if l.strip()), "")
    return dict(status=status, ts=ts_m.group(1) if ts_m else "",
                query=query, lead=lead, sources=sources, rc=rc)


def parse_codex(path: Path) -> dict:
    if not path.exists():
        return {"status": "waiting"}
    t = path.read_text(errors="replace")
    ts_m = re.search(r"ask-codex\.sh @ (\S+)", t)
    focus = _between(t, "FOCUS", "RESPONSE")
    # codex echoes prompt; real response follows "tokens used"
    tok = t.find("tokens used")
    end = t.find("=== END")
    response = t[tok + len("tokens used"):end].strip() if tok != -1 and end != -1 else _between(t, "RESPONSE", "END")
    done = "=== END" in t
    rc_m = re.search(r"=== END \(rc=(\d+)\)", t)
    rc = int(rc_m.group(1)) if rc_m else -1
    status = ("done" if rc == 0 else "failed") if done else ("running" if focus else "waiting")
    verdict_m = re.search(r"## Verdict\s*\n(.+)", response)
    verdict = verdict_m.group(1).strip() if verdict_m else ""
    word = verdict.split()[0] if verdict else ""
    findings = {k: len(re.findall(r"^- (?!none)", _heading_body(response, k), re.I | re.M))
                for k in ("Blocker", "Major", "Minor / Nit")}
    return dict(status=status, ts=ts_m.group(1) if ts_m else "",
                focus=focus, verdict=verdict, word=word, findings=findings, rc=rc)


# ── Widgets ───────────────────────────────────────────────────────────────────

STATUS_ICON = {"waiting": "[dim](waiting)[/]", "running": "[yellow]⏳ running…[/]",
               "done": "[green]✓ done[/]", "failed": "[red]✗ failed[/]"}
VERDICT_COLOR = {"SHIP": "green", "NEEDS-FIX": "red", "DISCUSS": "yellow"}


class GeminiPanel(RichLog):
    DEFAULT_CSS = "GeminiPanel { border: solid cyan; height: 1fr; padding: 0 1; }"

    def __init__(self, log_path: Path, team: str, **kw):
        super().__init__(highlight=False, markup=True, wrap=True, **kw)
        self.log_path = log_path
        self.team = team
        self._mtime = 0

    def on_mount(self) -> None:
        self.border_title = "🔍  GEMINI · researcher"
        self.set_interval(POLL, self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        try:
            mtime = self.log_path.stat().st_mtime if self.log_path.exists() else 0
        except OSError:
            mtime = 0
        if mtime == self._mtime and mtime != 0:
            return
        self._mtime = mtime
        d = parse_gemini(self.log_path)
        self.clear()
        self.write(f"[dim]team: {self.team}[/]")
        self.write(STATUS_ICON.get(d["status"], ""))
        if d.get("ts"):
            self.write(f"[dim]started: {d['ts']}[/]")
        if d.get("query"):
            self.write("")
            self.write("[bold]Query:[/]")
            for line in d["query"].splitlines()[:4]:
                self.write(f"  {line}")
        if d["status"] == "done" and d.get("lead"):
            self.write("")
            self.write("[bold]Answer (lead):[/]")
            self.write(f"  {d['lead'][:120]}")
            self.write(f"[dim]Sources cited: {d['sources']}[/]")


class CodexPanel(RichLog):
    DEFAULT_CSS = "CodexPanel { border: solid magenta; height: 1fr; padding: 0 1; }"

    def __init__(self, log_path: Path, team: str, **kw):
        super().__init__(highlight=False, markup=True, wrap=True, **kw)
        self.log_path = log_path
        self.team = team
        self._mtime = 0

    def on_mount(self) -> None:
        self.border_title = "🧐  CODEX · reviewer"
        self.set_interval(POLL, self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        try:
            mtime = self.log_path.stat().st_mtime if self.log_path.exists() else 0
        except OSError:
            mtime = 0
        if mtime == self._mtime and mtime != 0:
            return
        self._mtime = mtime
        d = parse_codex(self.log_path)
        self.clear()
        self.write(f"[dim]team: {self.team}[/]")
        self.write(STATUS_ICON.get(d["status"], ""))
        if d.get("ts"):
            self.write(f"[dim]started: {d['ts']}[/]")
        if d.get("focus"):
            self.write("")
            self.write("[bold]Focus:[/]")
            for line in d["focus"].splitlines()[:3]:
                self.write(f"  {line}")
        if d.get("verdict"):
            self.write("")
            color = VERDICT_COLOR.get(d["word"], "white")
            self.write(f"[bold {color}]Verdict: {d['verdict']}[/]")
            f = d["findings"]
            self.write(
                f"[red]{f['Blocker']} blocker[/] · "
                f"[yellow]{f['Major']} major[/] · "
                f"[dim]{f['Minor / Nit']} minor[/]"
            )


class ActivityLog(RichLog):
    DEFAULT_CSS = "ActivityLog { border: solid green; width: 1fr; padding: 0 1; }"

    def __init__(self, log_dir: Path, **kw):
        super().__init__(highlight=False, markup=True, wrap=True, **kw)
        self.log_dir = log_dir
        self._seen: set[Path] = set()

    def on_mount(self) -> None:
        self.border_title = "Claude (PM) — Activity"
        self.write("[bold green]3-agent team dashboard ready[/]")
        self.write(f"[dim]{self.log_dir}[/]")
        self.write("[dim]Run [bold]claude[/] in another terminal to start.[/]")
        self.set_interval(POLL, self._poll)

    def _poll(self) -> None:
        if not self.log_dir.exists():
            return
        for f in sorted(self.log_dir.glob("*.log")):
            if f.name.startswith("latest-") or f in self._seen:
                continue
            self._seen.add(f)
            agent = "gemini" if "gemini" in f.name else "codex"
            ts = "-".join(f.stem.split("-")[-2:]) if "-" in f.stem else f.stem
            color, icon = ("cyan", "🔍") if agent == "gemini" else ("magenta", "🧐")
            self.write(f"[{color}]{icon} {agent} call @ {ts}[/]")


# ── App ───────────────────────────────────────────────────────────────────────

class AgentDashboard(App):
    CSS = """
    Screen { layout: horizontal; }
    #right { width: 1fr; layout: vertical; }
    """
    TITLE = "3-Agent Team Dashboard"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, log_dir: Path, team: str, **kw):
        super().__init__(**kw)
        self.log_dir = log_dir
        self.team = team

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ActivityLog(self.log_dir)
            with Vertical(id="right"):
                yield GeminiPanel(self.log_dir / "latest-gemini.log", self.team)
                yield CodexPanel(self.log_dir / "latest-codex.log", self.team)
        yield Footer()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="3-agent team TUI dashboard")
    p.add_argument("project", nargs="?", default=".", help="project root (default: cwd)")
    p.add_argument("-n", "--name", default=None, help="team/session name (default: auto-detect)")
    args = p.parse_args()

    root = Path(args.project).resolve()
    agents_dev = root / ".agents-dev"
    if not agents_dev.exists():
        print(f"error: .agents-dev not found in {root}", file=sys.stderr)
        print("       Run 'harness-install' first.", file=sys.stderr)
        sys.exit(1)

    # Team name: 명시 > 로그 디렉토리 단일 > 폴더명
    log_base = agents_dev / "log"
    if args.name:
        team = args.name.replace("/", "-")
    elif log_base.exists():
        dirs = [d for d in log_base.iterdir() if d.is_dir()]
        team = dirs[0].name if len(dirs) == 1 else root.name
    else:
        team = root.name

    log_dir = log_base / team
    log_dir.mkdir(parents=True, exist_ok=True)

    AgentDashboard(log_dir=log_dir, team=team).run()


if __name__ == "__main__":
    main()
