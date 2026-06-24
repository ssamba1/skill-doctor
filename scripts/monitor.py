#!/usr/bin/env python3
"""monitor.py — continuous skill-usage tracking.

Designed to run from a Claude Code SessionEnd hook. It records the skills that
fired in a session to ~/.claude/analytics/skill-usage.jsonl, so usage history
accumulates durably (survives transcript rotation) instead of being re-mined
each time. `--summary` aggregates the log.

Hook config (settings.json):
  "hooks": { "SessionEnd": [ { "hooks": [
    { "type": "command", "command": "python \"<SKILL_DIR>/scripts/monitor.py\" --latest" }
  ] } ] }

Output: a status line (record mode) or JSON (summary mode).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlib  # noqa: E402


def _analytics_path() -> Path:
    return sdlib.claude_home() / "analytics" / "skill-usage.jsonl"


def _newest_transcript(projects_dir: Path):
    files = [p for p in projects_dir.rglob("*.jsonl")] if projects_dir.exists() else []
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def record_session(jsonl: Path) -> dict:
    """Extract per-skill fire counts from one transcript and append a record."""
    fires: dict[str, int] = {}
    session_id = jsonl.stem
    ended = ""
    try:
        with jsonl.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"timestamp"' in line:
                    try:
                        ts = json.loads(line).get("timestamp", "")
                        if ts > ended:
                            ended = ts
                    except (json.JSONDecodeError, ValueError):
                        pass
                if '"Skill"' not in line or '"tool_use"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                session_id = obj.get("sessionId") or session_id
                c = (obj.get("message") or {}).get("content")
                if isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill":
                            sk = (b.get("input") or {}).get("skill")
                            if sk:
                                fires[sk] = fires.get(sk, 0) + 1
    except OSError:
        return {"status": "error", "reason": "unreadable", "path": str(jsonl)}

    path = _analytics_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Dedupe: skip if this session already recorded.
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                if json.loads(line).get("session") == session_id:
                    return {"status": "skipped", "reason": "already recorded", "session": session_id}
            except (json.JSONDecodeError, ValueError):
                continue
    rec = {"session": session_id, "ended": ended, "fires": fires}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return {"status": "recorded", "session": session_id, "distinct_skills": len(fires),
            "total_fires": sum(fires.values())}


def summary() -> dict:
    path = _analytics_path()
    agg: dict[str, dict] = {}
    sessions = 0
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            sessions += 1
            for sk, n in (rec.get("fires") or {}).items():
                r = agg.setdefault(sk, {"count": 0, "sessions": 0, "last": None})
                r["count"] += n
                r["sessions"] += 1
                if rec.get("ended") and (r["last"] is None or rec["ended"] > r["last"]):
                    r["last"] = rec["ended"]
    return {"generated": "monitor-summary", "sessions_recorded": sessions,
            "distinct_skills": len(agg), "skills": agg}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Record/summarize durable skill usage.")
    ap.add_argument("--latest", action="store_true", help="record the newest transcript")
    ap.add_argument("--session", default=None, help="record a specific transcript path")
    ap.add_argument("--summary", action="store_true", help="print aggregated analytics")
    ap.add_argument("--projects-dir", default=None)
    args = ap.parse_args(argv)

    if args.summary:
        print(json.dumps(summary(), indent=2))
        return 0
    if args.session:
        print(json.dumps(record_session(Path(args.session))))
        return 0
    if args.latest:
        pd = Path(args.projects_dir) if args.projects_dir else (sdlib.claude_home() / "projects")
        t = _newest_transcript(pd)
        if t is None:
            print(json.dumps({"status": "skipped", "reason": "no transcript found"}))
            return 0
        print(json.dumps(record_session(t)))
        return 0
    ap.error("use --latest, --session PATH, or --summary")


if __name__ == "__main__":
    raise SystemExit(main())
