#!/usr/bin/env python3
"""evalgate.py — generate trigger probes to validate a skill still routes.

The deterministic half of an eval gate: from a skill's description it derives
short prompts that SHOULD make Claude auto-invoke it (and the trigger keywords to
look for). Run the probes in a fresh session before/after a disable or compress
change and confirm the skill still fires — proving the change didn't break
routing. (Executing the probes needs a Claude session; this generates them.)

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


def make_probes(name: str, description: str, when: str) -> dict:
    text = (description + " " + when).strip()
    # "Use when X" / "triggers on X" clauses → direct probes
    clauses = re.findall(r"(?:use when|triggers?(?: on| when)?|when the user|use this when)\s+(.+?)(?:[.;]|$)",
                         text, re.IGNORECASE)
    probes = []
    for c in clauses[:4]:
        c = c.strip().rstrip(".")
        if len(c) > 8:
            probes.append(f"I need to {c}." if not c.lower().startswith(("i ", "you ")) else c)
    # keyword fallback
    kws = [w for w in sdlib.tokenize_words(text) if len(w) > 4]
    if len(probes) < 2 and kws:
        probes.append("Help me with " + ", ".join(kws[:4]) + ".")
    return {
        "name": name,
        "trigger_keywords": sorted(set(kws))[:12],
        "should_fire_prompts": probes or [f"Help me with {name.replace('-', ' ')}."],
        "how_to_run": "In a fresh Claude Code session, send each prompt and confirm the "
                      f"'{name}' skill is invoked. Compare before/after your change.",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate routing probes for a skill.")
    ap.add_argument("--name", default=None, help="installed skill name")
    ap.add_argument("--path", default=None, help="path to a SKILL.md")
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if args.path:
        fm = sdlib.parse_frontmatter(Path(args.path).read_text(encoding="utf-8", errors="replace"))
        name = fm.get("name") or Path(args.path).parent.name
        desc, when = str(fm.get("description") or ""), str(fm.get("when_to_use") or "")
    elif args.name:
        match = next((s for s in sdlib.discover_skills(sdlib.default_roots(args.cwd))
                      if s["name"] == args.name), None)
        if not match:
            print(json.dumps({"error": f"skill not found: {args.name}"}))
            return 1
        name, desc, when = match["name"], match["description"], match["when_to_use"]
    else:
        ap.error("use --name or --path")

    res = make_probes(name, desc, when)
    out = json.dumps(res, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({len(res['should_fire_prompts'])} probes)")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
