<div align="center">

<img src="assets/hero.svg" width="840" alt="skill-doctor — diagnose your Claude Code skill library; cut the per-turn token tax">

### Diagnose your Claude Code skill library — and cut the per-turn token tax.

[![tests](https://img.shields.io/github/actions/workflow/status/ssamba1/skill-doctor/ci.yml?branch=main&style=flat-square&label=tests&labelColor=0F172A&color=22c55e)](https://github.com/ssamba1/skill-doctor/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/badge/coverage-91%25-22c55e?style=flat-square&labelColor=0F172A)](#quality)
[![release](https://img.shields.io/github/v/release/ssamba1/skill-doctor?style=flat-square&labelColor=0F172A&color=22c55e)](https://github.com/ssamba1/skill-doctor/releases)
[![license](https://img.shields.io/github/license/ssamba1/skill-doctor?style=flat-square&labelColor=0F172A&color=38bdf8)](LICENSE)
[![dependencies](https://img.shields.io/badge/dependencies-none-22c55e?style=flat-square&labelColor=0F172A)](#)

[Demo](#demo) · [Why](#why-skill-doctor) · [Quickstart](#quickstart) · [Proof](#proven-on-real-data) · [Compare](#how-it-compares) · [FAQ](#faq)

</div>

> Every auto-invocable skill injects its description into **every single request** — fired or not.
> **skill-doctor** finds the skills silently taxing your context (on a real machine, 89 skills ≈
> **6,832 tokens/turn**), proves which never fire from your own transcripts, and writes **reversible**
> fixes that cut the tax — measured at **~92%**. Local-only, zero dependencies.

## Demo

<div align="center">
<img src="assets/demo-anim.svg" width="820" alt="animated demo of a skill-doctor run">
</div>

## Why skill-doctor

- You've installed skill packs — and every description loads **every turn**, used or not.
- Claude Code shows cost only **per-plugin**; your standalone skills, collisions, and stale entries are a blind spot.
- Past the `skillListingBudgetFraction` (~2k tokens) Claude Code **silently drops** descriptions — so skills you think are loaded may not be.
- Its fixes are **reversible and evidence-backed** (real before/after from your logs), not guesses.

**When _not_ to use it**

- You have only a handful of skills — the tax is negligible; don't bother.
- You want to *create* a skill — use `skill-creator`. skill-doctor audits what you've already installed.
- You need org-wide fleet governance — that's [roadmap](#roadmap), not shipped.

## Quickstart

```bash
git clone https://github.com/ssamba1/skill-doctor && cd skill-doctor
python scripts/run.py --live --out-dir ./out          # diagnose → ./out/report.md
python scripts/apply.py --from-actions ./out/actions.json --write   # treat (reversible)
```

Disabled skills still run with `/name` — they just stop loading on every turn. `--revert --write` undoes everything.

<details>
<summary>Install as a skill (auto-triggers on "audit my skills")</summary>

```bash
/plugin marketplace add ssamba1/skill-doctor
```
</details>

## What it finds

| check | what it surfaces |
|---|---|
| 🩺 **Context tax** | exact tokens each skill injects per turn (live `skill_listing`) — total, A–F grades, worst offenders |
| 📉 **Budget check** | whether you're over `skillListingBudgetFraction` (~2k) where descriptions get silently dropped |
| 💀 **Dead weight** | skills that never fire, mined from transcripts, with a confidence line (days of history) |
| ✂️ **Compression** | skills you *keep* but whose descriptions are bloated — trim to minimal routing-correct form |
| ⚔️ **Collisions & dupes** | descriptions overlapping enough to ambiguously co-trigger; near-identical redundant skills |
| 🕰️ **Staleness** | deprecated model identifiers left in skill bodies |
| 🔌 **MCP audit** | configured-but-never-used MCP servers (another always-on drain) |

## Proven on real data

Predicted ~4,581 tokens of savings on an 89-skill machine. After applying the fixes, the **actual
`skill_listing` payload measured from the session logs** dropped — the mechanism, not an estimate:

| | skills loaded | injected chars | ~tokens / turn |
|---|---|---|---|
| **before** | 89 | 27,329 | ~6,832 |
| **after** | **49** | **7,978** | **~1,994** |

**Measured reduction: ~4,838 tokens every turn** — verifiable in your own `~/.claude/projects/*.jsonl`.

Bloat hurts quality too: a 202-skill library drops agent accuracy up to **21%**
([arXiv 2605.24050](https://arxiv.org/abs/2605.24050)); ~48% of descriptions compress with ~86%
retention ([arXiv 2603.29919](https://arxiv.org/abs/2603.29919)). Fewer, sharper skills route better.

## How it compares

| | **skill-doctor** | `/plugin` (built-in) | static inspectors | doing nothing |
|---|:---:|:---:|:---:|:---:|
| Per-**skill** cost (incl. standalone) | ✅ | per-plugin only | ❌ | ❌ |
| Never-fired, from real transcripts | ✅ | per-plugin telemetry | ❌ | ❌ |
| Trigger collisions / duplicates | ✅ | ❌ | some | ❌ |
| Description compression | ✅ | ❌ | ❌ | ❌ |
| Unused MCP servers | ✅ | ❌ | ❌ | ❌ |
| Reversible one-command fixes | ✅ | manual | ❌ | ❌ |

## How it works

<div align="center">
<img src="assets/flow.svg" width="820" alt="skill-doctor pipeline: discover, analyze, report, treat">
</div>

Scripts emit deterministic JSON facts; the one judgment call (confirming a collision, rewriting a
description) is made by the model from the shortlist. `paths`-scoped skills are excluded from the
always-on tax; attribution-only fires count as "used"; token figures are offline estimates while
**percentages are tokenizer-independent** (`--exact` for precise counts). Internals it relies on:
[`references/mechanics.md`](references/mechanics.md).

## Tools

| script | purpose |
|---|---|
| `run.py` | run the whole pipeline → `report.md` + `actions.json` |
| `scan.py` | inventory + per-skill cost + grades + budget + staleness |
| `usage.py` | per-skill firing history from transcripts |
| `collide.py` | trigger-collision + duplicate shortlist |
| `compress.py` | flag verbose descriptions to slim |
| `apply.py` | apply/revert `disable-model-invocation`; auto-rewrite descriptions (guarded) |
| `mcpusage.py` | flag configured-but-unused MCP servers |
| `context.py` | unified always-on budget (skills + CLAUDE.md + rules), ranked |
| `monitor.py` | record per-session usage durably (SessionEnd hook); `--summary` |
| `lint.py` | score a candidate skill before adding it (cost + collision + routing) |
| `evalgate.py` | generate trigger probes to confirm a change didn't break routing |

## FAQ

**Is it safe? Will it delete my skills?** No deletion. `apply.py` only edits the frontmatter of your
own personal/project `SKILL.md` files (never plugin/bundled), writes a `.bak`, replaces atomically,
and reverts byte-exact. "Disabling" just stops *automatic* loading — the skill still runs with `/name`.

**Does it send my data anywhere?** No. Everything runs locally over `~/.claude`. The only network
call is opt-in `--exact`, which sends skill *descriptions* (not transcripts, not code) to Anthropic's
count_tokens API — off by default.

**Cross-platform?** Windows, macOS, Linux; Python 3.11+. No dependencies.

**How accurate are the numbers?** Offline estimates by default; **percentages and the before/after
listing measurement are tokenizer-independent**. Use `--exact` for precise absolute counts.

## Quality

```bash
python -m pytest tests/ -q                            # 86 hermetic tests
SKILL_DOCTOR_DOGFOOD=1 python -m pytest tests/ -q     # + 4 real-machine checks
```

Stdlib-only, **zero dependencies**, **91% coverage** (CI-gated). CI on Linux + Windows × Python
3.11/3.12. Unit + CLI-smoke + property/fuzz tests; independently break-tested against malformed input.

## Roadmap

[`roadmap`](https://github.com/ssamba1/skill-doctor/issues?q=label%3Aroadmap) issues — continuous-usage
dashboard, enterprise governance, ML skill recommender.

## License

MIT · contributions welcome ([CONTRIBUTING.md](CONTRIBUTING.md))
