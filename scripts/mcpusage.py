#!/usr/bin/env python3
"""mcpusage.py — find MCP servers you configured but never use.

MCP tool *schemas* are deferred (lazy-loaded via ToolSearch), but each configured
server still contributes always-on weight (its instructions block + tool-name
availability). This mines transcripts for `mcp__<server>__<tool>` invocations,
diffs against the configured server list, and flags never-used servers as
removal candidates.

Output: JSON to stdout (or --out FILE).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlib  # noqa: E402

_TOOL_RE = re.compile(r"mcp__([A-Za-z0-9_.-]+?)__")


def configured_servers(config_paths: list[Path]) -> set[str]:
    servers: set[str] = set()
    for p in config_paths:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        servers |= set((data.get("mcpServers") or {}).keys())
    return servers


def _server_of(tool_name: str):
    m = _TOOL_RE.match(tool_name or "")
    return m.group(1) if m else None


def _ts_dt(ts: str):
    from datetime import datetime
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def mine_usage(projects_dir: Path) -> dict:
    use: dict[str, int] = {}
    last: dict[str, str] = {}
    hist_min = None
    hist_max = None
    files = list(projects_dir.rglob("*.jsonl")) if projects_dir.exists() else []
    scanned = 0
    for f in files:
        scanned += 1
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                first = True
                for line in fh:
                    if first:
                        first = False
                        if '"timestamp"' in line:
                            try:
                                d = _ts_dt(json.loads(line).get("timestamp", ""))
                                if d:
                                    hist_min = d if hist_min is None else min(hist_min, d)
                                    hist_max = d if hist_max is None else max(hist_max, d)
                            except (json.JSONDecodeError, ValueError):
                                pass
                    if "mcp__" not in line or '"tool_use"' not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    ts = obj.get("timestamp", "")
                    content = (obj.get("message") or {}).get("content")
                    if not isinstance(content, list):
                        continue
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            srv = _server_of(b.get("name", ""))
                            if srv:
                                use[srv] = use.get(srv, 0) + 1
                                if ts and (srv not in last or ts > last[srv]):
                                    last[srv] = ts
        except OSError:
            continue
    history_days = round((hist_max - hist_min).total_seconds() / 86400.0, 1) \
        if hist_min and hist_max else None
    return {"files_scanned": scanned, "usage": use, "last_used": last,
            "history_days": history_days}


def build(config_paths: list[Path], projects_dir: Path) -> dict:
    configured = configured_servers(config_paths)
    mined = mine_usage(projects_dir)
    use = mined["usage"]
    never = sorted(s for s in configured if use.get(s, 0) == 0)
    unconfigured = sorted(s for s in use if s not in configured)  # used but not in config (plugins/MCP via other means)
    return {
        "generated": "mcpusage",
        "files_scanned": mined["files_scanned"],
        "history_days": mined["history_days"],          # confidence for "never used"
        "configured_count": len(configured),
        "configured": sorted(configured),
        "usage": dict(sorted(use.items(), key=lambda kv: kv[1], reverse=True)),
        "last_used": mined["last_used"],
        "never_used": never,
        "used_but_unconfigured": unconfigured,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Flag configured-but-unused MCP servers.")
    ap.add_argument("--config", action="append", default=None,
                    help="config file(s) with mcpServers (default: ~/.claude.json + settings)")
    ap.add_argument("--projects-dir", default=None, help="default: <claude home>/projects")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if args.config:
        cfgs = [Path(c) for c in args.config]
    else:
        home = sdlib.claude_home()
        cfgs = [home.parent / ".claude.json", home / ".claude.json",
                home / "settings.json", home / "settings.local.json"]
    pd = Path(args.projects_dir) if args.projects_dir else (sdlib.claude_home() / "projects")

    result = build(cfgs, pd)
    out = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        hd = result["history_days"]
        print(f"wrote {args.out}: {len(result['never_used'])}/{result['configured_count']} "
              f"servers never used" + (f" (over ~{hd:g}d of history)" if hd else ""))
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
