#!/usr/bin/env python3
"""context.py — unified per-turn context budget across ALL always-on sources.

Skills are only part of the tax. This tallies every always-on contributor —
skill descriptions, CLAUDE.md (+ @-referenced files), rules files — and ranks
them, so you can see what actually eats your context window. (MCP server
instructions live in the system prompt and aren't reliably measurable from disk;
see mcpusage.py for the per-server usage angle.)

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


def _tok(path: Path, ratio: float):
    try:
        return sdlib.est_tokens(path.read_text(encoding="utf-8", errors="replace"), ratio)
    except OSError:
        return 0


def _claude_md_chain(home: Path, cwd: Path, ratio: float) -> list[dict]:
    """CLAUDE.md files + their @-referenced includes (one level)."""
    out = []
    seen = set()
    candidates = [home / "CLAUDE.md", cwd / "CLAUDE.md", cwd / ".claude" / "CLAUDE.md"]
    for c in candidates:
        if c.exists() and c not in seen:
            seen.add(c)
            text = c.read_text(encoding="utf-8", errors="replace")
            out.append({"name": f"CLAUDE.md ({c.parent.name})", "tokens": sdlib.est_tokens(text, ratio),
                        "path": str(c)})
            for ref in re.findall(r"^@(\S+)", text, re.MULTILINE):
                rp = (c.parent / ref).resolve()
                if rp.exists() and rp not in seen:
                    seen.add(rp)
                    out.append({"name": f"@{ref}", "tokens": _tok(rp, ratio), "path": str(rp)})
    return out


def build(cwd: str | None, ratio: float, listing: dict | None) -> dict:
    home = sdlib.claude_home()
    base = Path(cwd) if cwd else Path.cwd()
    sources = []

    # Skills (live listing if available, else editable estimate)
    if listing and listing.get("content"):
        sources.append({"name": f"skills ({listing.get('skillCount','?')} loaded)",
                        "tokens": sdlib.est_tokens(listing["content"], ratio), "path": "(live skill_listing)"})
    else:
        skills = sdlib.discover_skills(sdlib.default_roots(cwd))
        tot = sum(sdlib.est_tokens(sdlib.injected_text(s["name"], s["description"], s["when_to_use"]), ratio)
                  for s in skills if not s["disabled"] and not s.get("conditional"))
        sources.append({"name": f"skills ({len(skills)} editable)", "tokens": tot, "path": "(estimated)"})

    sources += _claude_md_chain(home, base, ratio)

    rules_dir = home / "rules"
    if rules_dir.exists():
        for r in sorted(rules_dir.glob("*.md")):
            sources.append({"name": f"rules/{r.name}", "tokens": _tok(r, ratio), "path": str(r)})

    sources.sort(key=lambda s: s["tokens"], reverse=True)
    total = sum(s["tokens"] for s in sources)
    return {
        "generated": "context",
        "chars_per_token": ratio,
        "total_est_tokens": total,
        "dominant": sources[0]["name"] if sources else None,
        "sources": sources,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Unified always-on context budget.")
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--ratio", type=float, default=sdlib.DEFAULT_CHARS_PER_TOKEN)
    ap.add_argument("--live", action="store_true", help="use the live skill_listing for skills")
    ap.add_argument("--projects-dir", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    listing = None
    if args.live:
        listing = sdlib.latest_skill_listing(Path(args.projects_dir) if args.projects_dir else None)
    res = build(args.cwd, args.ratio, listing)
    out = json.dumps(res, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} (total ~{res['total_est_tokens']:,} tok, top: {res['dominant']})")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
