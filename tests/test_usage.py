import json
from datetime import datetime, timezone

import usage as usage_mod


def _line(skill, ts):
    return json.dumps({
        "type": "assistant",
        "timestamp": ts,
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": skill}}
        ]},
    })


def test_mine_counts_and_window(tmp_path):
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    f = proj / "s.jsonl"
    lines = [
        _line("deep-research", "2026-06-20T10:00:00.000Z"),
        _line("deep-research", "2026-01-01T10:00:00.000Z"),   # outside 90d window
        _line("git-commit", "2026-06-23T10:00:00.000Z"),
        '{ this is not valid json',                            # malformed -> skipped
        json.dumps({"type": "assistant", "message": {"content": [   # not a Skill tool_use
            {"type": "text", "text": "hi"}]}}),
    ]
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")

    now = datetime(2026, 6, 24, tzinfo=timezone.utc)
    res = usage_mod.mine(tmp_path / "projects", window_days=90, now=now)
    assert res["files_scanned"] == 1
    assert res["total_fires"] == 3
    dr = res["skills"]["deep-research"]
    assert dr["count"] == 2
    assert dr["window_count"] == 1                # only the June fire is in-window
    assert dr["first"] == "2026-01-01T10:00:00.000Z"
    assert dr["last"] == "2026-06-20T10:00:00.000Z"
    assert res["skills"]["git-commit"]["count"] == 1


def test_mine_counts_attribution_only_fire(tmp_path):
    # A skill seen only via attributionSkill (no Skill tool_use block) must be
    # recorded as attributed=True so it is NOT flagged "never fired".
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    line = json.dumps({
        "type": "assistant",
        "attributionSkill": "ralph",
        "timestamp": "2026-06-24T10:00:00.000Z",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "looping"}]},
    })
    (proj / "s.jsonl").write_text(line + "\n", encoding="utf-8")
    res = usage_mod.mine(tmp_path / "projects", window_days=90)
    assert res["skills"]["ralph"]["attributed"] is True
    assert res["skills"]["ralph"]["count"] == 0          # no tool_use -> count stays 0
    assert res["total_fires"] == 0                        # attribution is not a counted fire


def test_mine_handles_mixed_timezone_offsets(tmp_path):
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    lines = [
        _line("a", "2026-06-20T10:00:00.000Z"),
        _line("a", "2026-06-20T05:00:00.000+00:00"),   # earlier instant, different suffix
    ]
    (proj / "s.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = usage_mod.mine(tmp_path / "projects", window_days=3650)
    # first must be the chronologically earlier instant despite the suffix change
    assert res["skills"]["a"]["first"] == "2026-06-20T05:00:00.000+00:00"
    assert res["skills"]["a"]["last"] == "2026-06-20T10:00:00.000Z"


def test_mine_history_span_from_content(tmp_path):
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    # two files whose FIRST lines carry session timestamps 30 days apart
    (proj / "old.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": "2026-05-01T00:00:00.000Z",
                    "message": {"content": []}}) + "\n", encoding="utf-8")
    (proj / "new.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": "2026-05-31T00:00:00.000Z",
                    "message": {"content": []}}) + "\n", encoding="utf-8")
    res = usage_mod.mine(tmp_path / "projects", window_days=3650)
    assert res["history_days"] == 30.0
    assert res["history_start"].startswith("2026-05-01")
    assert res["history_end"].startswith("2026-05-31")


def test_mine_session_fires_for_cofiring(tmp_path):
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    lines = [
        json.dumps({"type": "assistant", "sessionId": "S", "timestamp": "2026-06-20T10:00:00Z",
                    "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "a"}}]}}),
        json.dumps({"type": "assistant", "sessionId": "S", "timestamp": "2026-06-20T10:01:00Z",
                    "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "b"}}]}}),
    ]
    (proj / "s.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = usage_mod.mine(tmp_path / "projects", window_days=3650)
    assert set(res["session_fires"]["S"]) == {"a", "b"}


def test_mine_empty_dir(tmp_path):
    res = usage_mod.mine(tmp_path / "nope", window_days=90)
    assert res["total_fires"] == 0
    assert res["files_scanned"] == 0


def test_usage_main_out(tmp_path, capsys):
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(_line("alpha", "2026-06-20T10:00:00.000Z") + "\n",
                                  encoding="utf-8")
    out = tmp_path / "usage.json"
    rc = usage_mod.main(["--projects-dir", str(tmp_path / "projects"), "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["skills"]["alpha"]["count"] == 1
