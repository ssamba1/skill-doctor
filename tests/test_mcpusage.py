import json

import mcpusage as mu


def _toolcall(name, ts=None):
    obj = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t", "name": name, "input": {}}
        ]},
    }
    if ts:
        obj["timestamp"] = ts
    return json.dumps(obj)


def test_server_of():
    assert mu._server_of("mcp__chrome-devtools__click") == "chrome-devtools"
    assert mu._server_of("mcp__claude_ai_Canva__help") == "claude_ai_Canva"
    assert mu._server_of("Bash") is None


def test_configured_servers(tmp_path):
    cfg = tmp_path / ".claude.json"
    cfg.write_text(json.dumps({"mcpServers": {"context7": {}, "git": {}, "time": {}}}),
                   encoding="utf-8")
    assert mu.configured_servers([cfg]) == {"context7", "git", "time"}


def test_build_flags_never_used(tmp_path):
    cfg = tmp_path / ".claude.json"
    cfg.write_text(json.dumps({"mcpServers": {"context7": {}, "git": {}, "time": {}}}),
                   encoding="utf-8")
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(
        "\n".join([
            _toolcall("mcp__context7__query-docs"),
            _toolcall("mcp__context7__resolve-library-id"),
            _toolcall("mcp__playwright__browser_click"),   # used but NOT configured
            _toolcall("Bash"),                              # not MCP
        ]) + "\n",
        encoding="utf-8",
    )
    res = mu.build([cfg], tmp_path / "projects")
    assert res["usage"]["context7"] == 2
    assert res["never_used"] == ["git", "time"]
    assert res["used_but_unconfigured"] == ["playwright"]
    assert res["configured_count"] == 3


def test_build_history_and_last_used(tmp_path):
    cfg = tmp_path / ".claude.json"
    cfg.write_text(json.dumps({"mcpServers": {"context7": {}}}), encoding="utf-8")
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(
        "\n".join([
            _toolcall("mcp__context7__query-docs", ts="2026-04-01T00:00:00.000Z"),
            _toolcall("mcp__context7__query-docs", ts="2026-05-01T00:00:00.000Z"),
        ]) + "\n",
        encoding="utf-8",
    )
    res = mu.build([cfg], tmp_path / "projects")
    assert res["last_used"]["context7"] == "2026-05-01T00:00:00.000Z"
    assert res["history_days"] is not None and res["history_days"] >= 0


def test_build_empty(tmp_path):
    cfg = tmp_path / "none.json"   # missing
    res = mu.build([cfg], tmp_path / "nope")
    assert res["configured_count"] == 0
    assert res["never_used"] == []
