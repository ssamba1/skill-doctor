# Changelog

## v0.5.2
- **Fix:** an empty block scalar (`key: |` with no indented body) followed by another
  key could swallow that key during frontmatter parsing — found by property/fuzz testing.
- Property/fuzz tests for the frontmatter parser and field-setter (the most-exposed code).
- CLI smoke tests for every entrypoint; coverage 77% → 91%.

## v0.5.1
- Body-cost analysis: flag heavy skill bodies (on-invoke cost) in the report.

## v0.5.0
- `context.py` — unified always-on context budget (skills + CLAUDE.md + rules).
- `monitor.py` — durable per-session usage log for a SessionEnd hook (`--summary`).
- `lint.py` — score a candidate skill before adding (cost + collision + routing).
- `evalgate.py` — generate trigger probes to confirm a change didn't break routing.
- Report flags skills missing a routing description.

## v0.4.0
- Auto-rewrite compression: `apply.py --set-description` with a verify gate (must stay
  shorter and keep trigger words). Safe frontmatter field-setter; byte-exact revert.

## v0.3.0
- Compression mode (`compress.py`), skill-listing budget check, A–F cost grades,
  `--ignore` allowlist, MCP section in the report.
- README: empirical before/after proof + academic citations.

## v0.2.0
- MCP usage audit (`mcpusage.py`); one-line run summary.

## v0.1.0
- Initial: inventory + per-turn cost, transcript firing history, collisions,
  duplicates, staleness, reversible `disable-model-invocation` fixes.
