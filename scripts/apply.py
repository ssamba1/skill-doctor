#!/usr/bin/env python3
"""apply.py — guarded, reversible application of skill-doctor recommendations.

Only edits user-editable SKILL.md frontmatter (personal/project). It adds
`disable-model-invocation: true` to a skill's frontmatter so its description is
no longer injected (context cost -> 0) while the skill stays manually invocable.

Safety:
  * dry-run by default; requires --write to modify files
  * writes a .bak before any change; --revert restores from .bak
  * refuses paths outside the editable skill roots (won't touch plugin/bundled)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlib  # noqa: E402

FLAG = "disable-model-invocation: true"


def _editable_roots(cwd):
    return [r for r, _ in sdlib.default_roots(cwd)]


def _find_skill_md(name: str, cwd: str | None) -> Path | None:
    for root in _editable_roots(cwd):
        p = root / name / "SKILL.md"
        if p.exists():
            return p
    return None


def add_disable_flag(text: str) -> tuple[str, bool]:
    """Return (new_text, changed). Adds disable-model-invocation:true into the
    frontmatter block, creating one if absent. Idempotent and newline-preserving."""
    fm = sdlib.parse_frontmatter(text)
    if sdlib.as_bool(fm.get("disable-model-invocation"), False):
        return text, False  # already disabled

    nl = "\r\n" if "\r\n" in text else "\n"
    if text.startswith("---"):
        # Insert flag right after the opening fence (first line is the fence).
        lines = text.split(nl)
        lines.insert(1, FLAG)
        return nl.join(lines), True
    # No frontmatter: create one.
    return f"---{nl}{FLAG}{nl}---{nl}{nl}{text}", True


def apply_disable(name: str, cwd: str | None, write: bool) -> dict:
    p = _find_skill_md(name, cwd)
    if p is None:
        return {"name": name, "status": "skipped", "reason": "not an editable skill"}
    raw = p.read_bytes()                              # byte-exact, no newline mangling
    text = raw.decode("utf-8", errors="replace")
    new_text, changed = add_disable_flag(text)
    if not changed:
        return {"name": name, "status": "noop", "reason": "already disabled", "path": str(p)}
    if not write:
        return {"name": name, "status": "would-disable", "path": str(p)}
    bak = p.with_suffix(".md.bak")
    bak.write_bytes(raw)                              # exact copy of the original
    tmp = p.with_suffix(".md.tmp")
    tmp.write_bytes(new_text.encode("utf-8"))
    os.replace(tmp, p)                               # atomic; .bak stays intact on failure
    return {"name": name, "status": "disabled", "path": str(p), "backup": str(bak)}


def set_description(name: str, new_text: str, cwd: str | None, write: bool,
                   must_contain: list[str] | None = None) -> dict:
    """Replace a skill's description with a shorter, routing-correct one.

    Verify gate: the new description must be non-empty, strictly shorter than the
    old one, and contain every `must_contain` trigger word (case-insensitive) —
    so compression can't silently break what makes the skill auto-fire."""
    must_contain = must_contain or []
    p = _find_skill_md(name, cwd)
    if p is None:
        return {"name": name, "status": "skipped", "reason": "not an editable skill"}
    raw = p.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    old = str(sdlib.parse_frontmatter(text).get("description") or "")
    new_text = " ".join(new_text.split())
    if not new_text:
        return {"name": name, "status": "skipped", "reason": "empty new description"}
    missing = [w for w in must_contain if w.lower() not in new_text.lower()]
    if missing:
        return {"name": name, "status": "skipped",
                "reason": f"new description drops trigger words: {missing}"}
    if len(new_text) >= len(old):
        return {"name": name, "status": "noop", "reason": "not shorter than current",
                "old_chars": len(old), "new_chars": len(new_text)}
    if not write:
        return {"name": name, "status": "would-compress",
                "old_chars": len(old), "new_chars": len(new_text), "path": str(p)}
    new_full = sdlib.set_frontmatter_field(text, "description", new_text)
    bak = p.with_suffix(".md.bak")
    bak.write_bytes(raw)
    tmp = p.with_suffix(".md.tmp")
    tmp.write_bytes(new_full.encode("utf-8"))
    os.replace(tmp, p)
    return {"name": name, "status": "compressed", "old_chars": len(old),
            "new_chars": len(new_text), "path": str(p), "backup": str(bak)}


def revert(name: str, cwd: str | None, write: bool) -> dict:
    p = _find_skill_md(name, cwd)
    if p is None:
        return {"name": name, "status": "skipped", "reason": "not an editable skill"}
    bak = p.with_suffix(".md.bak")
    if not bak.exists():
        return {"name": name, "status": "skipped", "reason": "no .bak", "path": str(p)}
    if not write:
        return {"name": name, "status": "would-revert", "path": str(p)}
    tmp = p.with_suffix(".md.tmp")
    tmp.write_bytes(bak.read_bytes())               # byte-exact restore, atomic
    os.replace(tmp, p)
    bak.unlink()
    return {"name": name, "status": "reverted", "path": str(p)}


def _names_from_args(args) -> list[str]:
    names: list[str] = []
    if args.names:
        names += [n.strip() for n in args.names.split(",") if n.strip()]
    if args.from_actions:
        data = json.loads(Path(args.from_actions).read_text(encoding="utf-8"))
        names += [c["name"] for c in data.get("disable_candidates", [])]
    # de-dup, preserve order
    seen = set()
    return [n for n in names if not (n in seen or seen.add(n))]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Apply/revert disable-model-invocation.")
    ap.add_argument("--names", default=None, help="comma-separated skill names")
    ap.add_argument("--from-actions", default=None, help="actions.json from report.py")
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--write", action="store_true", help="actually modify files (else dry-run)")
    ap.add_argument("--revert", action="store_true", help="restore from .bak instead")
    ap.add_argument("--set-description", default=None,
                    help="compress one skill's description (with --text)")
    ap.add_argument("--text", default=None, help="new description for --set-description")
    ap.add_argument("--must-contain", default=None,
                    help="comma-separated trigger words the new description must keep")
    args = ap.parse_args(argv)

    if args.set_description:
        if not args.text:
            ap.error("--set-description requires --text")
        must = [w.strip() for w in (args.must_contain or "").split(",") if w.strip()]
        res = set_description(args.set_description, args.text, args.cwd, args.write, must)
        print(json.dumps({"write": args.write, "results": [res]}, indent=2))
        if not args.write:
            print("\n(dry-run — re-run with --write to apply)", file=sys.stderr)
        return 0

    names = _names_from_args(args)
    if not names:
        ap.error("no skills given (use --names, --from-actions, or --set-description)")

    results = [
        (revert if args.revert else apply_disable)(n, args.cwd, args.write)
        for n in names
    ]
    print(json.dumps({"write": args.write, "revert": args.revert, "results": results}, indent=2))
    if not args.write:
        print("\n(dry-run — re-run with --write to apply; revert with --revert --write)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
