<div align="center">

# 🩺 skill-doctor

**Audit your *installed* Claude Code skill library — and cut the invisible per-turn token tax.**

[![tests](https://github.com/ssamba1/skill-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/ssamba1/skill-doctor/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/ssamba1/skill-doctor?color=2da44e)](https://github.com/ssamba1/skill-doctor/releases)
[![license](https://img.shields.io/github/license/ssamba1/skill-doctor?color=blue)](LICENSE)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![dependencies](https://img.shields.io/badge/dependencies-none-success)

<img src="assets/skill-doctor-demo.svg" width="820" alt="skill-doctor sample run">

</div>

> Every auto-invocable skill injects its description into **every single request** — fired or not.
> With a big library that's a constant, invisible cost. Claude Code shows it only per-*plugin* and
> never flags trigger collisions, so your standalone skills are a blind spot. skill-doctor closes it.

## What it does

- **Measures the tax** — exact tokens injected per turn, per skill (from the live `skill_listing`); total + worst offenders.
- **Finds dead weight** — mines your transcripts for which skills actually fire; flags never-fired auto-invoking skills, backed by a confidence line (days of history observed).
- **Finds collisions & duplicates** — descriptions that overlap enough to ambiguously co-trigger, and near-identical skills where one is redundant.
- **Flags staleness** — deprecated model identifiers in skill bodies.
- **Audits MCP** — flags configured-but-never-used MCP servers (another always-on drain).
- **Fixes it** — emits the exact, **reversible** `disable-model-invocation` edits with projected savings.

**Stdlib-only Python. No dependencies.**

## Quick start

```bash
python scripts/run.py --live --out-dir ./skill-doctor-out
# read ./skill-doctor-out/report.md, then (reversible):
python scripts/apply.py --from-actions ./skill-doctor-out/actions.json --write
```

Or install as a skill: `/plugin marketplace add ssamba1/skill-doctor`, then ask *"audit my skills."*

## What it found on a real 89-skill machine

- ~**6,832 tokens** injected **every turn** (89 loaded skills, ~27k chars).
- **61 of 67** editable skills had never fired in 75 days → disabling them saves **~4,581 tokens/turn (~92%)** with zero loss (still `/`-invocable).
- 4 trigger-collision pairs · **10 of 12** MCP servers never used.

## Sample report (text)

```
## Context tax (per turn)
- Loaded skills: 89   ·   Total injected: ~6,832 tokens every turn
- Editable always-on tax: ~4,977 tokens/turn   ·   Already disabled: 2

## Disable candidates — never fired, still auto-invoking
Confidence: ~75.7 days of history (36 invocations observed).
Disabling 61 skills cuts ~4,581 tokens/turn (92%) — still /-invocable.

## Trigger collisions: 4   ## Duplicates: 0   ## Stale: 0
## MCP servers: 10 of 12 configured never used

SUMMARY: ~6,832 tok/turn | 61 never-fired (save ~4,581 tok, 92%) | 4 collisions | 10 unused MCP | history 75.7d
```

<details>
<summary><b>How it works & real-world subtleties</b></summary>

- The scripts emit deterministic JSON facts; the one judgment call (confirming a collision) is made by the model from the shortlist.
- `paths`-scoped skills load only for matching files → excluded from the always-on tax, never proposed for disabling.
- Attribution-only fires (some slash commands) count as "used", so they're never mis-flagged as dead.
- Token figures are offline estimates (~4 chars/token); **percentages are tokenizer-independent**. Set `ANTHROPIC_API_KEY` and add `--exact` for precise counts via the count_tokens API.
- "Never fired" is framed by how many days of transcript history back it — more history, stronger recommendation.
- Verified Claude Code internals it relies on are documented in [`references/mechanics.md`](references/mechanics.md).

</details>

## Tools

| script | purpose |
|---|---|
| `scan.py` | inventory + per-skill cost + staleness (`--live` / `--exact`) |
| `usage.py` | per-skill firing history from transcripts |
| `collide.py` | trigger-collision + duplicate shortlist |
| `report.py` | merge into `report.md` + `actions.json` |
| `apply.py` | apply/revert `disable-model-invocation` (guarded, reversible) |
| `mcpusage.py` | flag configured-but-unused MCP servers |
| `run.py` | run the whole pipeline |

## Tests

```bash
python -m pytest tests/ -q          # 55 hermetic tests
SKILL_DOCTOR_DOGFOOD=1 python -m pytest tests/ -q   # + 4 real-machine checks
```

CI runs the hermetic suite on Linux + Windows (Python 3.11 & 3.12).

## Safety

`apply.py` edits only your own user/project `SKILL.md` frontmatter (never plugin/bundled skills),
writes a `.bak`, replaces atomically, and reverts byte-exact (`--revert --write`). Disabling a skill
only stops *automatic* invocation — you can still run it with `/name`.

## License

MIT
