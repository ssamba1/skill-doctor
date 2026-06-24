#!/usr/bin/env python3
"""usage.py — mine Claude Code transcripts for per-skill firing history.

Streams every `*.jsonl` under the projects dir (line-prefiltered, memory-safe),
detects skill invocations via the verified schema:
  assistant content block {"type":"tool_use","name":"Skill","input":{"skill":<name>}}
and the top-level `attributionSkill` field, then aggregates per-skill fire
counts, first/last timestamps, and a recency window.

Output: JSON to stdout (or --out FILE).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlib  # noqa: E402


def _ts_to_dt(ts: str):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_line(line: str):
    """Return (fires, attributed) for one JSONL line.

    fires: list of (skill_name, timestamp) from genuine Skill *tool_use* blocks
           (one per invocation — the accurate count).
    attributed: skill name from a top-level `attributionSkill` field, or None.
           Used only as an "ever fired" signal so a skill invoked via a path that
           leaves attribution but no tool_use block (e.g. some slash commands) is
           NOT wrongly flagged as never-fired.
    """
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return [], None, None
    ts = obj.get("timestamp", "")
    sid = obj.get("sessionId")
    fires = []
    msg = obj.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        for c in content:
            if (
                isinstance(c, dict)
                and c.get("type") == "tool_use"
                and c.get("name") == "Skill"
            ):
                skill = (c.get("input") or {}).get("skill")
                if skill:
                    fires.append((skill, ts))
    attr = obj.get("attributionSkill")
    return fires, (attr if isinstance(attr, str) else None), sid


def mine(projects_dir: Path, window_days: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    agg: dict[str, dict] = {}
    files_scanned = 0
    total_fires = 0

    def _rec(skill):
        return agg.setdefault(skill, {
            "count": 0, "window_count": 0, "first": None, "last": None,
            "attributed": False, "_firstdt": None, "_lastdt": None,
        })

    hist_min = None   # earliest/latest session timestamp (from content, sync-proof)
    hist_max = None
    sess_fires: dict[str, set] = {}   # session id -> set of skills that fired (for co-firing)

    files = list(projects_dir.rglob("*.jsonl")) if projects_dir.exists() else []
    for f in files:
        files_scanned += 1
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                first_line = True
                for line in fh:
                    if first_line:
                        first_line = False
                        if '"timestamp"' in line:
                            try:
                                fdt = _ts_to_dt(json.loads(line).get("timestamp", ""))
                                if fdt is not None:
                                    hist_min = fdt if hist_min is None else min(hist_min, fdt)
                                    hist_max = fdt if hist_max is None else max(hist_max, fdt)
                            except (json.JSONDecodeError, ValueError):
                                pass
                    has_fire = '"name"' in line and '"Skill"' in line and '"tool_use"' in line
                    has_attr = '"attributionSkill"' in line
                    if not has_fire and not has_attr:
                        continue
                    fires, attr, sid = _parse_line(line)
                    sid = sid or f.stem
                    if attr:
                        _rec(attr)["attributed"] = True
                    for skill, ts in fires:
                        total_fires += 1
                        sess_fires.setdefault(sid, set()).add(skill)
                        rec = _rec(skill)
                        rec["count"] += 1
                        dt = _ts_to_dt(ts)
                        if dt is not None:
                            if dt >= cutoff:
                                rec["window_count"] += 1
                            if rec["_firstdt"] is None or dt < rec["_firstdt"]:
                                rec["_firstdt"], rec["first"] = dt, ts
                            if rec["_lastdt"] is None or dt > rec["_lastdt"]:
                                rec["_lastdt"], rec["last"] = dt, ts
        except OSError:
            continue

    for rec in agg.values():            # drop internal dt helpers before output
        rec.pop("_firstdt", None)
        rec.pop("_lastdt", None)

    history_days = round((hist_max - hist_min).total_seconds() / 86400.0, 1) \
        if hist_min and hist_max else None

    return {
        "generated": "usage",
        "projects_dir": str(projects_dir),
        "files_scanned": files_scanned,
        "window_days": window_days,
        "history_days": history_days,                 # observation span (confidence)
        "history_start": hist_min.isoformat() if hist_min else None,
        "history_end": hist_max.isoformat() if hist_max else None,
        "total_fires": total_fires,
        "distinct_skills_fired": sum(1 for r in agg.values() if r["count"] > 0),
        "distinct_skills_seen": len(agg),
        "session_fires": {s: sorted(v) for s, v in sess_fires.items()},  # co-firing evidence
        "skills": agg,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Per-skill firing history from transcripts.")
    ap.add_argument("--projects-dir", default=None, help="default: <claude home>/projects")
    ap.add_argument("--days", type=int, default=90, help="recency window (days)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    pd = Path(args.projects_dir) if args.projects_dir else (sdlib.claude_home() / "projects")
    result = mine(pd, args.days)
    out = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({result['total_fires']} fires across "
              f"{result['files_scanned']} files)")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
