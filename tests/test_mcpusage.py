import json

import mcpusage as mu


def _toolcall(name):
    return json.dumps({
        "type": "assistant",
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t", "name": name, "input": {}}
        ]},
    })


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


def test_build_empty(tmp_path):
    cfg = tmp_path / "none.json"   # missing
    res = mu.build([cfg], tmp_path / "nope")
    assert res["configured_count"] == 0
    assert res["never_used"] == []
