#!/usr/bin/env python3
"""scan.py — inventory + per-skill context cost + staleness.

Discovers user-editable skills (personal + project), replicates the exact
per-turn injected text, estimates token cost, flags stale model references, and
(optionally) cross-checks against the authoritative `skill_listing` attachment
from live transcripts to report the real loaded set and exact total tax.

Output: JSON to stdout (or --out FILE).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlib  # noqa: E402


def build(cwd: str | None, ratio: float, listing: dict | None,
          now: float | None = None, exact: bool = False,
          model: str = "claude-opus-4-8") -> dict:
    import time
    now = now if now is not None else time.time()
    roots = sdlib.default_roots(cwd)
    skills = sdlib.discover_skills(roots)

    listing_map = None
    if listing and listing.get("content"):
        listing_map = sdlib.parse_listing_content(listing["content"])

    loaded_names = set(listing.get("names", [])) if listing else set()
    exact_used = False

    for s in skills:
        s["loaded"] = (s["name"] in loaded_names) if listing else None
        s["age_days"] = round((now - s.get("mtime", 0.0)) / 86400.0, 1) if s.get("mtime") else None
        always_on = not s["disabled"] and not s.get("conditional")
        # Prefer exact injected text from the live listing when available.
        injected_str = "X" * s["injected_chars"]
        if always_on and listing_map is not None and s["name"] in listing_map:
            injected_str = f"- {s['name']}: {listing_map[s['name']]}"
            s["injected_chars"] = len(injected_str)
        if not always_on:
            s["est_tokens"] = 0
        elif exact:
            tok = sdlib.count_tokens_exact(injected_str, model=model)
            if tok is None:
                s["est_tokens"] = sdlib.est_tokens(injected_str, ratio)
            else:
                s["est_tokens"] = tok
                exact_used = True
        else:
            s["est_tokens"] = sdlib.est_tokens(injected_str, ratio)

    total_tokens = sum(s["est_tokens"] for s in skills)

    result = {
        "generated": "scan",
        "chars_per_token": ratio,
        "exact_tokens": exact_used,
        "editable_skill_count": len(skills),
        "disabled_count": sum(1 for s in skills if s["disabled"]),
        "conditional_count": sum(1 for s in skills if s.get("conditional")),
        "stale_count": sum(1 for s in skills if s["stale"]),
        "editable_total_est_tokens": total_tokens,
        "skills": sorted(skills, key=lambda s: s["est_tokens"], reverse=True),
    }

    if listing:
        # Authoritative total tax from the literal injected payload.
        content = listing.get("content", "")
        result["loaded_count"] = listing.get("skillCount", len(loaded_names))
        result["loaded_injected_chars"] = len(content)
        result["loaded_total_est_tokens"] = sdlib.est_tokens(content, ratio)
        disk_names = {s["name"] for s in skills}
        result["loaded_not_editable"] = sorted(loaded_names - disk_names)  # built-in/plugin
        result["editable_not_loaded"] = sorted(
            n for n in (disk_names - loaded_names)
        )  # disabled or shadowed
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Inventory + context cost + staleness.")
    ap.add_argument("--cwd", default=None, help="project dir for project-level skills")
    ap.add_argument("--ratio", type=float, default=sdlib.DEFAULT_CHARS_PER_TOKEN,
                    help="chars per token (offline estimate)")
    ap.add_argument("--exact", action="store_true",
                    help="use count_tokens API for exact counts (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default="claude-opus-4-8", help="model for --exact counting")
    ap.add_argument("--listing", default=None,
                    help="path to a skill_listing JSON fixture (else --live or none)")
    ap.add_argument("--live", action="store_true",
                    help="auto-load the latest skill_listing from transcripts")
    ap.add_argument("--projects-dir", default=None, help="override transcripts dir")
    ap.add_argument("--out", default=None, help="write JSON here instead of stdout")
    args = ap.parse_args(argv)

    listing = None
    if args.listing:
        listing = json.loads(Path(args.listing).read_text(encoding="utf-8"))
    elif args.live:
        pd = Path(args.projects_dir) if args.projects_dir else None
        listing = sdlib.latest_skill_listing(pd)

    result = build(args.cwd, args.ratio, listing, exact=args.exact, model=args.model)
    out = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({result['editable_skill_count']} skills)")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
