<div align="center">

<img src="assets/hero.svg" width="840" alt="skill-doctor — diagnose your Claude Code skill library; cut the per-turn token tax">

&nbsp;

[![tests](https://img.shields.io/github/actions/workflow/status/ssamba1/skill-doctor/ci.yml?branch=main&style=flat-square&label=tests&labelColor=0F172A&color=22c55e)](https://github.com/ssamba1/skill-doctor/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/ssamba1/skill-doctor?style=flat-square&labelColor=0F172A&color=22c55e)](https://github.com/ssamba1/skill-doctor/releases)
[![license](https://img.shields.io/github/license/ssamba1/skill-doctor?style=flat-square&labelColor=0F172A&color=38bdf8)](LICENSE)
[![python](https://img.shields.io/badge/python-3.11+-38bdf8?style=flat-square&labelColor=0F172A)](https://www.python.org)
[![dependencies](https://img.shields.io/badge/dependencies-none-22c55e?style=flat-square&labelColor=0F172A)](#)

</div>

---

Every auto-invocable skill injects its description into **every single request** — fired or not. With a big library that's a constant, invisible cost. Claude Code surfaces it only per-*plugin* and never flags trigger collisions, so your standalone skills are a blind spot.

**skill-doctor diagnoses the library you already have — and writes the prescription.**

## Diagnosis

| check | what it finds |
|---|---|
| 🩺 **Context tax** | exact tokens each skill injects per turn (from the live `skill_listing`) — total, per-skill A–F grades, worst offenders |
| 📉 **Budget check** | whether you're over Claude Code's `skillListingBudgetFraction` (~2k tokens) — past it, Claude Code silently shortens/drops descriptions |
| 💀 **Dead weight** | skills that never fire, mined from your transcripts, backed by a confidence line (days of history) |
| ✂️ **Compression** | skills you *keep* but whose descriptions are bloated — trim to minimal routing-correct form (no disabling) |
| ⚔️ **Collisions & duplicates** | descriptions that overlap enough to ambiguously co-trigger; near-identical skills where one is redundant |
| 🕰️ **Staleness** | deprecated model identifiers left in skill bodies |
| 🔌 **MCP audit** | configured-but-never-used MCP servers (another always-on drain) |

## Prescription

```bash
python scripts/run.py --live --out-dir ./skill-doctor-out   # diagnose
python scripts/apply.py --from-actions ./skill-doctor-out/actions.json --write   # treat (reversible)
```

`apply.py` writes `disable-model-invocation` to your own skills only, with byte-exact backups — `--revert --write` undoes everything. Disabled skills still run with `/name`; they just stop loading on every turn.

Or install it: `/plugin marketplace add ssamba1/skill-doctor`, then ask *"audit my skills."*

## See it run

<div align="center">
<img src="assets/skill-doctor-demo.svg" width="760" alt="terminal output of a skill-doctor run">
</div>

## Proven on real data

skill-doctor predicted ~4,581 tokens of savings on an 89-skill machine. After applying its
`disable-model-invocation` fixes, the **actual `skill_listing` payload measured from the session
logs** dropped — confirming the mechanism, not just an estimate:

| | skills loaded | injected chars | ~tokens / turn |
|---|---|---|---|
| **before** | 89 | 27,329 | ~6,832 |
| **after** | **49** | **7,978** | **~1,994** |

**Measured reduction: ~4,838 tokens every turn.** Disabling a skill genuinely removes it from the
always-on payload; the saving is verifiable in your own `~/.claude/projects/*.jsonl`.

Skill bloat isn't only a cost problem — research shows scaling to a 202-skill library drops agent
accuracy by up to **21%** ([Skill Shadowing, arXiv 2605.24050](https://arxiv.org/abs/2605.24050)),
and ~48% of skill descriptions are compressible with ~86% functional retention
([SkillReducer, arXiv 2603.29919](https://arxiv.org/abs/2603.29919)). Fewer, sharper skills route better.

<details>
<summary><b>How it works & the subtleties it gets right</b></summary>

<br>

- Scripts emit deterministic JSON facts; the one judgment call (confirming a collision) is made by the model from the shortlist.
- `paths`-scoped skills load only for matching files → excluded from the always-on tax, never proposed for disabling.
- Attribution-only fires (some slash commands) count as "used", so they're never mis-flagged as dead.
- Token figures are offline estimates (~4 chars/token); **percentages are tokenizer-independent**. Add `--exact` (with `ANTHROPIC_API_KEY`) for precise counts via the count_tokens API.
- "Never fired" is framed by how many days of transcript history back it.
- Verified Claude Code internals it relies on: [`references/mechanics.md`](references/mechanics.md).

</details>

## Tools

| script | purpose |
|---|---|
| `scan.py` | inventory + per-skill cost + staleness (`--live` / `--exact`) |
| `usage.py` | per-skill firing history from transcripts |
| `collide.py` | trigger-collision + duplicate shortlist |
| `compress.py` | flag verbose descriptions to slim (keep the skill, cut its cost) |
| `report.py` | merge into `report.md` + `actions.json` |
| `apply.py` | apply/revert `disable-model-invocation` (guarded, reversible) |
| `mcpusage.py` | flag configured-but-unused MCP servers |
| `run.py` | run the whole pipeline |

> Unlike static skill inspectors, skill-doctor is **usage- and cost-aware**: it reads your real
> transcripts and the live injected payload, so it knows what actually fires and what it actually costs.

## Quality

```bash
python -m pytest tests/ -q                            # 55 hermetic tests
SKILL_DOCTOR_DOGFOOD=1 python -m pytest tests/ -q     # + 4 real-machine checks
```

Stdlib-only Python, **zero dependencies**. CI on Linux + Windows (Python 3.11 & 3.12). Independently break-tested against malformed and adversarial inputs.

## License

MIT
