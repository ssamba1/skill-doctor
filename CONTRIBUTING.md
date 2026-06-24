# Contributing

Thanks for helping improve skill-doctor.

## Principles
- **Stdlib-only.** No third-party runtime dependencies. The scripts must run with a
  plain Python 3.11+ install.
- **Deterministic core, model judgment at the edge.** Scripts emit JSON facts; any
  judgment call (confirming a collision, rewriting a description) belongs in the
  SKILL.md workflow, not the scripts.
- **Reversible + safe.** Anything that edits a user's `SKILL.md` must back up, write
  atomically, and revert byte-exact. Never touch plugin/bundled skills.

## Dev loop
```bash
python -m pytest tests/ -q                          # hermetic suite
SKILL_DOCTOR_DOGFOOD=1 python -m pytest tests/ -q   # + real-machine checks (opt-in)
python -m py_compile scripts/*.py                   # syntax
```
CI runs the hermetic suite on Linux + Windows (Python 3.11 & 3.12).

## Adding a check
1. Put deterministic logic in `scripts/<tool>.py` (and shared helpers in `sdlib.py`).
2. Add hermetic tests in `tests/` (fixtures, no real `~/.claude` dependence) and a CLI
   smoke test in `tests/test_cli.py`.
3. Wire it into `scripts/run.py` and a report section if it belongs in the one-shot audit.
4. Update `SKILL.md`, `README.md`, and `CHANGELOG.md`.

## Roadmap
See the [`roadmap`](https://github.com/ssamba1/skill-doctor/issues?q=label%3Aroadmap) issues
for the larger vision (continuous dashboard, enterprise governance, ML recommender).
