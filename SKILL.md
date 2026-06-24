---
name: skill-doctor
description: >
  Audit your INSTALLED Claude Code skill library for waste. Measures the per-turn
  token tax of every skill's always-on description, mines transcripts to find
  skills that never fire, detects trigger collisions between skills, flags stale
  model references, and emits the exact disable-model-invocation edits to cut the
  tax. Use when Claude Code feels bloated or slow, when you've installed many
  skills/plugins, to reduce context cost, prune unused skills, find duplicate or
  conflicting skills, or audit your ~/.claude/skills library.
---

# skill-doctor

Every auto-invocable skill injects its name + description into **every single
request**, whether it ever fires or not. With a large library that is a constant,
invisible token tax. Claude Code surfaces this only per-*plugin* (`/plugin`) and
never flags trigger collisions — so standalone skills are a blind spot.
skill-doctor closes it: measure the tax, find dead weight, find collisions, and
produce concrete, reversible fixes.

All logic is in `scripts/` (Python stdlib only — no dependencies). The scripts
emit deterministic JSON facts; the one judgment call (confirming collisions) is
yours, made from the shortlist.

## When to use
- "audit my skills", "why is my context so big", "prune unused skills"
- after installing a skill pack / many plugins
- to find duplicate or conflicting skills

## Workflow

**Path setup (required).** Skills run from the user's working directory, not from
the skill folder — so invoke the scripts by their absolute path. Set `SKILL_DIR`
to this skill's base directory (the harness states it as
"Base directory for this skill: <path>" when the skill loads; otherwise it's the
directory you read this SKILL.md from, e.g. `~/.claude/skills/skill-doctor`). The
`--out-dir` is relative to the user's cwd, which is what you want.

```bash
SKILL_DIR="<absolute dir of this SKILL.md>"
python "$SKILL_DIR/scripts/run.py" --live --out-dir ./skill-doctor-out
```

`--live` pulls the authoritative loaded set + exact injected payload from the most
recent transcript. Outputs: `scan.json`, `usage.json`, `collide.json`,
`report.md`, `actions.json`. A one-line SUMMARY prints to stdout.

Then:

1. **Read `report.md`** and present the headline (tokens/turn), the disable
   candidates with projected savings, the collision shortlist, and staleness.
2. **Judge collisions.** Open `collide.json`. For each candidate pair, read both
   full descriptions and decide if they would genuinely both auto-trigger on the
   same request. Keep only the real ones; recommend merging or sharpening the
   loser's description.
3. **Propose fixes**, then on the user's OK apply them (reversible):

```bash
# dry-run first (default), then --write
python "$SKILL_DIR/scripts/apply.py" --from-actions ./skill-doctor-out/actions.json --write
# undo anything:
python "$SKILL_DIR/scripts/apply.py" --names skill-a,skill-b --revert --write
```

`apply.py` only edits user/project `SKILL.md` frontmatter (never plugin/bundled
skills), writes a `.bak`, and is fully reversible.

Optionally also flag unused MCP servers:

```bash
python "$SKILL_DIR/scripts/mcpusage.py"
```

## Individual tools
All invoked as `python "$SKILL_DIR/scripts/<tool>.py" --help`:
- `scan.py` — inventory + per-skill cost + staleness (`--live` / `--listing FILE` / `--exact`)
- `usage.py` — per-skill firing history from transcripts (`--days N`)
- `collide.py` — trigger-collision shortlist (`--threshold`, overlap-coefficient)
- `compress.py` — flag verbose descriptions to slim (keep the skill, cut its cost)
- `report.py` — merge into `report.md` + `actions.json` (`--ignore a,b` to allowlist skills)
- `apply.py` — apply/revert `disable-model-invocation` (guarded)
- `mcpusage.py` — flag configured-but-never-used MCP servers (`~/.claude.json` + transcripts)

The report also flags **budget** (over Claude Code's `skillListingBudgetFraction`, descriptions get
silently dropped) and lists **compress candidates** — skills to keep but whose descriptions are
verbose. To compress one: draft a shorter **routing-correct** description (keep the trigger
words/phrases that make Claude auto-invoke it; cut prose/examples), then apply it with the verify
gate — it refuses the change unless the new text is shorter and still contains those trigger words:

```bash
python "$SKILL_DIR/scripts/apply.py" --set-description pandas-pro \
  --text "Pandas DataFrame ops: cleaning, aggregation, merging, time series." \
  --must-contain "pandas,dataframe" --write
# revert like any change:
python "$SKILL_DIR/scripts/apply.py" --names pandas-pro --revert --write
```

## Notes
- Token figures are offline estimates (~4 chars/token); **percentages are
  tokenizer-independent**. For exact absolute counts, set `ANTHROPIC_API_KEY` and
  add `--exact` (uses the count_tokens API; falls back to the estimate if no key).
- The report states a **confidence** line — how many days of transcript history
  back the "never fired" calls. More history = stronger recommendation.
- **paths-scoped** skills (frontmatter `paths:`) load only for matching files, so
  they are excluded from the always-on tax and never proposed for disabling.
- **Likely duplicates** (near-identical descriptions) are reported separately from
  trigger collisions — one of a duplicate pair is usually removable.
- `--grace-days N` (default 0/off) excludes never-fired skills modified within N
  days. Off by default because file mtime is unreliable on synced machines.
- Disabling a skill (`disable-model-invocation: true`) only stops *automatic*
  invocation — you can still run it manually with `/name`.
- The verified mechanics this skill relies on are documented in
  `references/mechanics.md`.
