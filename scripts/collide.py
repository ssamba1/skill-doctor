#!/usr/bin/env python3
"""collide.py — shortlist skills whose descriptions overlap enough to cause
ambiguous auto-invocation (trigger collisions).

Deterministic stage only: pairwise Jaccard similarity over description word-sets.
The output is a *candidate* list; the final true/false ambiguity call is made by
the model in SKILL.md (it reads the shortlist + full descriptions). This keeps a
clean, testable boundary between mechanical facts and judgment.

Input: a scan.json (with `skills[]`) or live discovery.
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


def find_pairs(skills: list[dict], threshold: float, min_shared: int = 3) -> list[dict]:
    """Flag pairs whose description word-sets overlap >= threshold AND share at
    least `min_shared` meaningful words.

    Primary metric is the overlap coefficient (subset-aware); Jaccard is reported
    as a secondary signal. The min-shared-words gate suppresses false positives
    where one description is short, which inflates the overlap coefficient on a
    single coincidental word (e.g. grill-me <> ui-ux-pro-max at jaccard 0.02).
    """
    enriched = []
    for s in skills:
        # Disabled / paths-scoped skills don't auto-trigger, so they can't cause
        # trigger collisions — exclude them to avoid false positives.
        if s.get("disabled") or s.get("conditional"):
            continue
        text = (s.get("description") or "") + " " + (s.get("when_to_use") or "")
        enriched.append((s.get("name"), s.get("description") or "", sdlib.tokenize_words(text)))

    pairs = []
    n = len(enriched)
    for i in range(n):
        na, da, wa = enriched[i]
        for j in range(i + 1, n):
            nb, db, wb = enriched[j]
            shared = wa & wb
            if len(shared) < min_shared:
                continue
            score = sdlib.overlap_coefficient(wa, wb)
            if score >= threshold:
                pairs.append({
                    "a": na, "b": nb,
                    "score": round(score, 3),
                    "jaccard": round(sdlib.jaccard(wa, wb), 3),
                    "shared": sorted(shared),
                    "a_desc": da[:200], "b_desc": db[:200],
                })
    pairs.sort(key=lambda p: p["score"], reverse=True)
    return pairs


def _load_skills(scan_path: str | None, cwd: str | None) -> list[dict]:
    if scan_path:
        data = json.loads(Path(scan_path).read_text(encoding="utf-8"))
        return data.get("skills", [])
    return sdlib.discover_skills(sdlib.default_roots(cwd))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Detect trigger-collision candidates.")
    ap.add_argument("--scan", default=None, help="scan.json to read skills from")
    ap.add_argument("--cwd", default=None, help="discover live if no --scan")
    ap.add_argument("--threshold", type=float, default=0.40,
                    help="min overlap coefficient to flag (default 0.40)")
    ap.add_argument("--min-shared", type=int, default=3,
                    help="min shared meaningful words (default 3)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    skills = _load_skills(args.scan, args.cwd)
    considered = [s for s in skills if not s.get("disabled") and not s.get("conditional")]
    pairs = find_pairs(skills, args.threshold, args.min_shared)
    result = {
        "generated": "collide",
        "threshold": args.threshold,
        "skills_considered": len(considered),
        "candidate_pairs": len(pairs),
        "pairs": pairs,
    }
    out = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({len(pairs)} candidate pairs)")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
