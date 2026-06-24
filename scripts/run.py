#!/usr/bin/env python3
"""run.py — convenience chainer: scan -> usage -> collide -> report.

Runs the full deterministic pipeline and writes scan.json, usage.json,
collide.json, report.md, actions.json into an output dir. The model-judgment
step (confirming collisions) happens when Claude runs the skill and reads
collide.json / report.md — this chainer is for one-shot dogfooding and tests.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlib  # noqa: E402
import scan as scan_mod  # noqa: E402
import usage as usage_mod  # noqa: E402
import collide as collide_mod  # noqa: E402
import report as report_mod  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the full skill-doctor pipeline.")
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--out-dir", default="skill-doctor-out")
    ap.add_argument("--ratio", type=float, default=sdlib.DEFAULT_CHARS_PER_TOKEN)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--threshold", type=float, default=0.40)
    ap.add_argument("--grace-days", type=float, default=0.0)
    ap.add_argument("--exact", action="store_true",
                    help="exact token counts via count_tokens API (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--listing", default=None)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--projects-dir", default=None)
    args = ap.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    scan_args = ["--ratio", str(args.ratio), "--out", str(out / "scan.json")]
    if args.exact:
        scan_args += ["--exact"]
    if args.cwd:
        scan_args += ["--cwd", args.cwd]
    if args.listing:
        scan_args += ["--listing", args.listing]
    elif args.live:
        scan_args += ["--live"]
    if args.projects_dir:
        scan_args += ["--projects-dir", args.projects_dir]
    scan_mod.main(scan_args)

    usage_args = ["--days", str(args.days), "--out", str(out / "usage.json")]
    if args.projects_dir:
        usage_args += ["--projects-dir", args.projects_dir]
    usage_mod.main(usage_args)

    collide_args = ["--scan", str(out / "scan.json"),
                    "--threshold", str(args.threshold),
                    "--out", str(out / "collide.json")]
    collide_mod.main(collide_args)

    report_mod.main([
        "--scan", str(out / "scan.json"),
        "--usage", str(out / "usage.json"),
        "--collide", str(out / "collide.json"),
        "--out", str(out / "report.md"),
        "--actions-out", str(out / "actions.json"),
        "--grace-days", str(args.grace_days),
    ])

    # One-line summary to stdout.
    import json as _json
    scan = _json.loads((out / "scan.json").read_text(encoding="utf-8"))
    acts = _json.loads((out / "actions.json").read_text(encoding="utf-8"))
    usg = _json.loads((out / "usage.json").read_text(encoding="utf-8"))
    loaded = scan.get("loaded_total_est_tokens")
    hist = usg.get("history_days")
    hist_str = f"{hist:g}d" if hist is not None else "n/a"
    print(f"\nSUMMARY: ~{loaded or scan.get('editable_total_est_tokens'):,} tokens/turn"
          f" | {len(acts['disable_candidates'])} never-fired (save ~"
          f"{acts['projected_token_savings']:,} tok, {acts['projected_pct_savings']}% of editable)"
          f" | {len(acts['duplicate_pairs'])} dup + {len(acts['collision_pairs'])} collision pairs"
          f" | history {hist_str}")
    print(f"Pipeline complete -> {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
