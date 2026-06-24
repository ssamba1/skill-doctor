#!/usr/bin/env python3
"""report.py — merge scan + usage + collide into a markdown report and a
machine-readable actions.json.

Headline: total per-turn skill tax. Then: never-fired auto-invokable skills
(disable candidates) with projected savings, top cost skills, collision
candidates, and staleness. Savings are reported both as estimated tokens and as
a tokenizer-independent percentage.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlib  # noqa: E402


def _fires_for(usage: dict, name: str) -> dict:
    return (usage.get("skills") or {}).get(
        name, {"count": 0, "window_count": 0, "last": None, "attributed": False}
    )


def _ever_fired(f: dict) -> bool:
    return f.get("count", 0) > 0 or bool(f.get("attributed"))


def build(scan: dict, usage: dict, collide: dict,
          grace_days: float = 0.0, dup_threshold: float = 0.6,
          mcp: dict | None = None) -> tuple[str, dict]:
    skills = scan.get("skills", [])
    total = scan.get("editable_total_est_tokens", 0) or 0
    loaded_total = scan.get("loaded_total_est_tokens")

    # Disable candidates: always-on (not disabled, not paths-scoped), loaded (or
    # unknown), auto-invokable, never fired, and not too recently added/modified.
    candidates = []
    too_new = []
    for s in skills:
        if s["disabled"] or s.get("conditional") or not s.get("user_invocable", True):
            continue
        if s.get("loaded") is False:
            continue
        f = _fires_for(usage, s["name"])
        if _ever_fired(f):
            continue
        entry = {"name": s["name"], "level": s["level"],
                 "est_tokens": s["est_tokens"], "path": s["path"],
                 "age_days": s.get("age_days")}
        age = s.get("age_days")
        if age is not None and age < grace_days:
            too_new.append(entry)        # insufficient history to call it dead
        else:
            candidates.append(entry)
    candidates.sort(key=lambda c: c["est_tokens"], reverse=True)
    too_new.sort(key=lambda c: c["est_tokens"], reverse=True)
    savings = sum(c["est_tokens"] for c in candidates)
    pct = round(100.0 * savings / total, 1) if total else 0.0

    # Split overlap pairs into likely-duplicates (high Jaccard) vs collisions.
    dups, collisions = [], []
    for p in collide.get("pairs", []):
        (dups if p.get("jaccard", 0) >= dup_threshold else collisions).append(p)

    actions = {
        "disable_candidates": candidates,
        "too_new_to_judge": too_new,
        "projected_token_savings": savings,
        "projected_pct_savings": pct,
        "duplicate_pairs": dups,
        "collision_pairs": collisions,
        "stale": [
            {"name": s["name"], "stale": s["stale"], "path": s["path"]}
            for s in skills if s["stale"]
        ],
        "conditional_skills": [s["name"] for s in skills if s.get("conditional")],
        "unused_mcp_servers": (mcp or {}).get("never_used", []),
    }

    # ---- markdown ----
    L = []
    L.append("# skill-doctor report\n")
    L.append("## Context tax (per turn)\n")
    if loaded_total is not None:
        L.append(f"- **Loaded skills:** {scan.get('loaded_count')} "
                 f"(authoritative, from live skill_listing)")
        L.append(f"- **Total injected:** ~{loaded_total:,} tokens **every turn** "
                 f"(~{scan.get('loaded_injected_chars', 0):,} chars)")
    L.append(f"- **Editable skills found:** {scan.get('editable_skill_count')} "
             f"(personal + project)")
    basis = "exact (count_tokens API)" if scan.get("exact_tokens") else \
            f"estimate @ {scan.get('chars_per_token')} chars/token"
    L.append(f"- **Editable always-on tax:** ~{total:,} tokens/turn ({basis})")
    L.append(f"- **Already disabled (cost 0):** {scan.get('disabled_count')}")
    if scan.get("conditional_count"):
        L.append(f"- **Conditional (paths-scoped, not always-on):** "
                 f"{scan.get('conditional_count')}")
    L.append("")

    hist = usage.get("history_days")
    L.append("## Disable candidates — never fired, still auto-invoking\n")
    if hist is not None:
        L.append(f"_Confidence: based on **~{hist:g} days** of transcript history "
                 f"({usage.get('total_fires', 0)} total skill invocations observed)._\n")
    if candidates:
        L.append(f"Setting `disable-model-invocation: true` on these "
                 f"**{len(candidates)}** skills cuts **~{savings:,} tokens/turn "
                 f"({pct}% of editable tax)** with zero loss "
                 f"(you can still invoke them with `/name`). The `age` column flags "
                 f"recently added skills — judge those with more care.\n")
        L.append("| skill | level | est tokens/turn | age (days) |")
        L.append("|---|---|---|---|")
        for c in candidates[:40]:
            L.append(f"| `{c['name']}` | {c['level']} | {c['est_tokens']} | "
                     f"{c.get('age_days') if c.get('age_days') is not None else '—'} |")
        L.append("")
    else:
        L.append("_None — every auto-invokable editable skill has fired at least once._\n")

    if too_new:
        L.append("## Recently added/modified — too new to judge\n")
        L.append(f"{len(too_new)} never-fired skills are < {grace_days:g} days old "
                 f"(or recently edited); excluded from disable advice until they have "
                 f"usage history.\n")
        L.append("| skill | age (days) | est tokens/turn |")
        L.append("|---|---|---|")
        for c in too_new[:20]:
            L.append(f"| `{c['name']}` | {c.get('age_days')} | {c['est_tokens']} |")
        L.append("")

    L.append("## Top cost skills\n")
    L.append("| skill | est tokens/turn | fired (window) | last fired |")
    L.append("|---|---|---|---|")
    for s in skills[:15]:
        f = _fires_for(usage, s["name"])
        L.append(f"| `{s['name']}` | {s['est_tokens']} | "
                 f"{f.get('count', 0)} ({f.get('window_count', 0)}) | "
                 f"{f.get('last') or '—'} |")
    L.append("")

    if dups:
        L.append("## Likely duplicates\n")
        L.append(f"{len(dups)} pairs share most of their description vocabulary "
                 f"(Jaccard ≥ {dup_threshold}). One of each is probably redundant — "
                 f"consider removing or merging.\n")
        L.append("| a | b | jaccard | shared words |")
        L.append("|---|---|---|---|")
        for p in dups[:25]:
            L.append(f"| `{p['a']}` | `{p['b']}` | {p.get('jaccard')} | "
                     f"{', '.join(p.get('shared', [])[:8])} |")
        L.append("")

    L.append("## Trigger-collision candidates\n")
    if collisions:
        L.append(f"{len(collisions)} description pairs overlap enough to risk "
                 f"ambiguous auto-invocation. Review and sharpen the weaker "
                 f"description (or disable the redundant skill).\n")
        L.append("| a | b | overlap | shared words |")
        L.append("|---|---|---|---|")
        for p in collisions[:25]:
            L.append(f"| `{p['a']}` | `{p['b']}` | {p.get('score')} | "
                     f"{', '.join(p.get('shared', [])[:8])} |")
        L.append("")
    else:
        L.append("_No high-overlap pairs._\n")

    L.append("## Staleness\n")
    if actions["stale"]:
        L.append("| skill | stale references |")
        L.append("|---|---|")
        for st in actions["stale"]:
            L.append(f"| `{st['name']}` | {', '.join(st['stale'])} |")
        L.append("")
    else:
        L.append("_No deprecated model identifiers found._\n")

    if mcp is not None:
        L.append("## MCP servers — configured but never used\n")
        never = mcp.get("never_used", [])
        hd = mcp.get("history_days")
        conf = f" (over ~{hd:g}d of history)" if hd else ""
        if never:
            L.append(f"{len(never)} of {mcp.get('configured_count', 0)} configured MCP "
                     f"servers have **no recorded tool calls**{conf}. Each still adds "
                     f"always-on weight (server instructions). Consider removing unused "
                     f"ones from `~/.claude.json`:\n")
            L.append("| server | status |")
            L.append("|---|---|")
            for s in never:
                L.append(f"| `{s}` | never used |")
            L.append("")
        else:
            L.append(f"_All {mcp.get('configured_count', 0)} configured servers have "
                     f"been used._\n")

    L.append("---")
    L.append("_Token figures are offline estimates; percentages are "
             "tokenizer-independent. Run with `--exact` (count_tokens API) for "
             "precise absolute counts._")
    return "\n".join(L) + "\n", actions


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Merge scan+usage+collide into a report.")
    ap.add_argument("--scan", required=True)
    ap.add_argument("--usage", required=True)
    ap.add_argument("--collide", required=True)
    ap.add_argument("--out", default=None, help="markdown output path")
    ap.add_argument("--actions-out", default=None, help="actions.json output path")
    ap.add_argument("--grace-days", type=float, default=0.0,
                    help="exclude never-fired skills modified within N days "
                         "(default 0 = off; mtime is unreliable on synced machines)")
    ap.add_argument("--dup-threshold", type=float, default=0.6,
                    help="Jaccard at/above which a pair is a likely duplicate")
    ap.add_argument("--mcp", default=None, help="optional mcpusage.json to include an MCP section")
    args = ap.parse_args(argv)

    md, actions = build(_read(args.scan), _read(args.usage), _read(args.collide),
                        grace_days=args.grace_days, dup_threshold=args.dup_threshold,
                        mcp=_read(args.mcp) if args.mcp else None)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    if args.actions_out:
        Path(args.actions_out).write_text(json.dumps(actions, indent=2), encoding="utf-8")
        print(f"wrote {args.actions_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
