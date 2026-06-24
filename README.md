# skill-doctor

[![tests](https://github.com/ssamba1/skill-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/ssamba1/skill-doctor/actions/workflows/ci.yml)

A Claude Code skill that audits your **installed** skill library and cuts the
invisible per-turn token tax.

Every auto-invocable skill injects its description into **every request**, fired
or not. With a big library that is a constant cost. Claude Code shows this only
per-*plugin* and never flags trigger collisions. skill-doctor:

- **Measures the tax** — exact tokens injected per turn, per skill (from the live
  `skill_listing`), total + worst offenders.
- **Finds dead weight** — mines your transcripts for which skills actually fire;
  flags never-fired auto-invoking skills.
- **Finds collisions** — skills whose descriptions overlap enough to ambiguously
  co-trigger (overlap-coefficient shortlist + model judgment).
- **Flags staleness** — deprecated model identifiers in skill bodies.
- **Flags duplicates** — near-identical skills where one is redundant.
- **Fixes it** — emits the exact, reversible `disable-model-invocation` edits with
  projected savings, backed by a confidence line (days of history observed).

Handles real-world subtleties: `paths`-scoped skills are conditional (excluded from
the always-on tax), attribution-only fires count as "used", token counts can be
made exact via the count_tokens API (`--exact`), and recommendations are framed by
how much transcript history backs them.

Stdlib-only Python. No dependencies.

## Quick start

```bash
python scripts/run.py --live --out-dir ./skill-doctor-out
# read ./skill-doctor-out/report.md, then:
python scripts/apply.py --from-actions ./skill-doctor-out/actions.json --write   # reversible
```

## What it found on a real 89-skill machine
- ~6,832 tokens injected **every turn** (89 loaded skills, ~27k chars).
- 61 of 67 editable skills had never fired → disabling them saves
  ~4,581 tokens/turn (~92% of the editable tax) with zero loss (still
  invocable with `/name`).
- 6 trigger-collision candidates (e.g. `subagent-driven-development` ↔
  `using-git-worktrees`).

## Sample output

```
## Context tax (per turn)
- Loaded skills: 89 (authoritative, from live skill_listing)
- Total injected: ~6,832 tokens every turn (~27,329 chars)
- Editable always-on tax: ~4,977 tokens/turn

## Disable candidates — never fired, still auto-invoking
Confidence: based on ~75.7 days of transcript history (36 invocations observed).
Disabling these 61 skills cuts ~4,581 tokens/turn (92% of editable tax) — still /-invocable.
| skill        | est tokens/turn | age (days) |
| claude-api   | 270             | 0.5        |
| xlsx         | 237             | 0.5        |
| agent-browser| 236             | 0.5        |
...

## Trigger-collision candidates
| a                          | b                    | overlap | shared words            |
| subagent-driven-development| using-git-worktrees  | 0.67    | executing, implementation, plans |

## MCP servers — configured but never used
10 of 12 configured MCP servers have no recorded tool calls (over ~75.7d). e.g. chrome-devtools, playwright, motherduck …

SUMMARY: ~6,832 tokens/turn | 61 never-fired (save ~4,581 tok, 92%) | 4 collision pairs | 10 unused MCP servers | history 75.7d
```

## Layout
```
scripts/  scan.py usage.py collide.py report.py apply.py run.py mcpusage.py sdlib.py
tests/    pytest suite (hermetic units + a real-machine dogfood)
references/mechanics.md   the verified Claude Code internals it relies on
```

Bonus: `python scripts/mcpusage.py` flags MCP servers you configured but never
use (another always-on context drain).

## Tests
```bash
python -m pytest tests/ -q
```

## How it works / safety
- Token figures are offline estimates (~4 chars/token); **percentages are
  tokenizer-independent**. Set `ANTHROPIC_API_KEY` for exact counts.
- `apply.py` edits only user/project `SKILL.md` frontmatter (never plugin/bundled
  skills), writes a `.bak`, and is fully reversible (`--revert --write`).
- Mechanics it depends on are documented in `references/mechanics.md`.

## License
MIT
