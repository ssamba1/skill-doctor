#!/usr/bin/env python3
"""lint.py — score a skill before you add it.

A heuristic pre-add check (the deterministic core of a recommendation engine):
given a candidate SKILL.md, it reports the skill's per-turn cost + grade, whether
it has a routing description, and its collision risk against your installed
library (max description overlap with an existing skill). Helps you avoid adding
expensive, redundant, or non-routable skills.

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


def lint(skill_md: Path, cwd: str | None, ratio: float) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm = sdlib.parse_frontmatter(text)
    name = fm.get("name") or skill_md.parent.name
    desc = str(fm.get("description") or "")
    when = str(fm.get("when_to_use") or "")
    tokens = sdlib.est_tokens(sdlib.injected_text(name, desc, when), ratio)
    words = sdlib.tokenize_words(desc + " " + when)

    warnings = []
    if not desc.strip():
        warnings.append("no routing description — Claude can't auto-invoke it reliably")
    if tokens > sdlib.COMPRESS_TARGET_TOKENS:
        warnings.append(f"verbose description (~{tokens} tok > {sdlib.COMPRESS_TARGET_TOKENS} target)")

    # collision risk vs installed library
    best = {"name": None, "overlap": 0.0, "shared": []}
    for s in sdlib.discover_skills(sdlib.default_roots(cwd)):
        if s["name"] == name:
            continue
        sw = sdlib.tokenize_words((s["description"] or "") + " " + (s["when_to_use"] or ""))
        ov = sdlib.overlap_coefficient(words, sw)
        shared = words & sw
        if ov > best["overlap"] and len(shared) >= 3:
            best = {"name": s["name"], "overlap": round(ov, 3), "shared": sorted(shared)}
    if best["overlap"] >= 0.4:
        warnings.append(f"collision risk: {best['overlap']} overlap with `{best['name']}`")

    grade = sdlib.cost_grade(tokens)
    verdict = "add" if not warnings else ("review" if grade in "ABC" and best["overlap"] < 0.5 else "reconsider")
    return {
        "generated": "lint",
        "name": name,
        "est_tokens": tokens,
        "grade": grade,
        "has_description": bool(desc.strip()),
        "nearest_collision": best,
        "warnings": warnings,
        "verdict": verdict,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score a candidate skill before adding it.")
    ap.add_argument("--path", required=True, help="path to the candidate SKILL.md")
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--ratio", type=float, default=sdlib.DEFAULT_CHARS_PER_TOKEN)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    res = lint(Path(args.path), args.cwd, args.ratio)
    out = json.dumps(res, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out}: {res['name']} grade {res['grade']} verdict {res['verdict']}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
