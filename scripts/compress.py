#!/usr/bin/env python3
"""compress.py — find skills whose always-on description is verbose enough to
shrink, and estimate the savings.

Disabling helps *dead* skills; compression helps the skills you *keep* but whose
descriptions are bloated. Inspired by SkillReducer (arXiv 2603.29919), which found
~48% of skill descriptions are compressible with ~86% functional retention.

This stage is deterministic: it flags always-on skills whose description exceeds a
token target and estimates the potential saving if trimmed to that target. The
actual rewrite (keeping the routing-relevant trigger words) is a model step driven
from SKILL.md — compression must preserve what makes the skill auto-trigger.

Input: a scan.json (with skills[]) or live discovery.
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


def find_candidates(skills: list[dict], target_tokens: int, ratio: float) -> list[dict]:
    out = []
    for s in skills:
        if s.get("disabled") or s.get("conditional"):
            continue
        cur = s.get("est_tokens")
        if cur is None:
            text = sdlib.injected_text(s.get("name", ""), s.get("description", ""),
                                       s.get("when_to_use", ""))
            cur = sdlib.est_tokens(text, ratio)
        if cur > target_tokens:
            out.append({
                "name": s.get("name"),
                "current_tokens": cur,
                "target_tokens": target_tokens,
                "potential_savings": cur - target_tokens,
                "description": (s.get("description") or "")[:400],
            })
    out.sort(key=lambda c: c["potential_savings"], reverse=True)
    return out


def _load_skills(scan_path, cwd):
    if scan_path:
        return json.loads(Path(scan_path).read_text(encoding="utf-8")).get("skills", [])
    return sdlib.discover_skills(sdlib.default_roots(cwd))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Flag verbose skill descriptions to compress.")
    ap.add_argument("--scan", default=None)
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--target-tokens", type=int, default=sdlib.COMPRESS_TARGET_TOKENS)
    ap.add_argument("--ratio", type=float, default=sdlib.DEFAULT_CHARS_PER_TOKEN)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    skills = _load_skills(args.scan, args.cwd)
    cands = find_candidates(skills, args.target_tokens, args.ratio)
    result = {
        "generated": "compress",
        "target_tokens": args.target_tokens,
        "candidate_count": len(cands),
        "potential_savings": sum(c["potential_savings"] for c in cands),
        "candidates": cands,
    }
    out = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({len(cands)} compressible, "
              f"~{result['potential_savings']} tok potential)")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
