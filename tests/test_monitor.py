import json

import monitor as monitor_mod


def _transcript(path, session_id, skills_ts):
    lines = []
    for sk, ts in skills_ts:
        lines.append(json.dumps({
            "type": "assistant", "sessionId": session_id, "timestamp": ts,
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Skill", "input": {"skill": sk}}]},
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_record_and_summary_and_dedupe(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    (home / "projects").mkdir(parents=True)
    t = home / "projects" / "sess1.jsonl"
    _transcript(t, "sess1", [("deep-research", "2026-06-20T10:00:00Z"),
                             ("deep-research", "2026-06-20T11:00:00Z"),
                             ("git-commit", "2026-06-20T12:00:00Z")])

    r = monitor_mod.record_session(t)
    assert r["status"] == "recorded"
    assert r["total_fires"] == 3
    assert (home / "analytics" / "skill-usage.jsonl").exists()

    # dedupe: same session not recorded twice
    r2 = monitor_mod.record_session(t)
    assert r2["status"] == "skipped"

    s = monitor_mod.summary()
    assert s["sessions_recorded"] == 1
    assert s["skills"]["deep-research"]["count"] == 2
    # "last" = the session's end timestamp (max ts in the session)
    assert s["skills"]["deep-research"]["last"] == "2026-06-20T12:00:00Z"
    assert s["skills"]["git-commit"]["count"] == 1


def test_summary_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude"))
    s = monitor_mod.summary()
    assert s["sessions_recorded"] == 0
    assert s["skills"] == {}
