# Verified mechanics

skill-doctor's numbers all trace to these facts (Claude Code docs + firsthand
inspection on Windows). Re-verify if Claude Code internals change.

1. **Per-turn injection.** For model-invocable skills, `name` + `description`
   (+ `when_to_use`) are injected into the system prompt at session start and
   present in every request. The combined description text is capped at **1,536
   chars per skill**. The SKILL.md *body* is lazy-loaded only on invocation.
   Source: `code.claude.com/docs/en/features-overview` (Context cost table) and
   the Skills doc.

2. **The zero-cost lever.** `disable-model-invocation: true` removes a skill's
   description from context (cost → 0) while keeping it manually invocable with
   `/name`. This is the fix skill-doctor recommends and `apply.py` writes.

3. **Authoritative loaded set.** The latest transcript contains an attachment
   `{"type":"attachment","attachment":{"type":"skill_listing","content":"…",
   "skillCount":N,"names":[…],"isInitial":true}}`. `content` is the literal
   injected payload; `names` is the exact loaded set. `scan.py --live` reads it
   to report exact total tax and to cross-check the editable inventory. Undocumented
   — treated as an optimization, with frontmatter replication as the fallback.

4. **Firing schema.** A skill invocation is an assistant `tool_use` block
   `{"type":"tool_use","name":"Skill","input":{"skill":"<name>","args":"…"}}`;
   downstream records carry top-level `"attributionSkill":"<name>"`, and the tool
   result has `toolUseResult.commandName`. `usage.py` counts only the `tool_use`
   block (avoids double counting).

5. **Discovery + precedence (Windows).** Personal
   `C:\Users\<u>\.claude\skills\<name>\SKILL.md`; project
   `<proj>\.claude\skills\<name>\SKILL.md`; plugin cache
   `~\.claude\plugins\cache\<marketplace>\<plugin>\<sha>\skills\<name>\SKILL.md`.
   Precedence enterprise > personal > project > bundled; plugin skills are
   namespaced `plugin:skill`. skill-doctor only inventories the **editable**
   roots (personal + project) — the part a user can change; the authoritative
   listing covers the full loaded picture.

6. **Frontmatter fields used:** `name`, `description`, `when_to_use`,
   `disable-model-invocation`, `user-invocable`. All optional; simple scalars and
   block scalars (`|`, `>`) supported by the parser.

7. **Transcripts:** `~/.claude/projects/<project-slug>/<session-id>.jsonl`
   (slug = cwd with separators → `--`); subagents under
   `.../<session-id>/subagents/agent-<id>.jsonl`.

8. **Token counting.** No public offline Claude tokenizer. Official
   `POST /v1/messages/count_tokens` is authoritative but needs an API key. Offline
   default heuristic ≈ 4 chars/token; Opus 4.7+ tokenizer runs ~30% higher.
   Absolute token figures are estimates; **relative % savings are
   tokenizer-independent** and are the load-bearing number.

Snapshot when built (2026-06-24): 67 editable skills, 89 loaded
(~27,329 chars ≈ ~6,832 tokens/turn), 2 skills already disabled, 2,735 transcripts.
