"""CLI smoke tests — exercise every script's main() end-to-end on a synthetic
environment, asserting exit 0 and expected output files. Covers the argparse/IO
wiring the unit tests skip."""
import json

import pytest

import scan as scan_mod
import usage as usage_mod
import collide as collide_mod
import compress as compress_mod
import report as report_mod
import apply as apply_mod
import mcpusage as mcpusage_mod
import context as context_mod
import monitor as monitor_mod
import lint as lint_mod
import evalgate as evalgate_mod
import run as run_mod


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    # skills
    for name, desc in [("alpha", "review the pull request diff for bugs"),
                       ("beta", "review a diff for bugs and issues"),
                       ("gamma", "generate powerpoint presentations")]:
        d = home / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nbody {name}\n",
                                    encoding="utf-8")
    # transcript with a Skill fire + skill_listing
    proj = home / "projects" / "p1"
    proj.mkdir(parents=True)
    listing = {"type": "attachment", "timestamp": "2026-06-20T10:00:00Z",
               "attachment": {"type": "skill_listing", "skillCount": 3,
                              "names": ["alpha", "beta", "gamma"],
                              "content": "- alpha: review diff\n- beta: review diff\n- gamma: pptx"}}
    fire = {"type": "assistant", "sessionId": "p1", "timestamp": "2026-06-20T10:01:00Z",
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Skill", "input": {"skill": "alpha"}}]}}
    (proj / "s.jsonl").write_text(json.dumps(listing) + "\n" + json.dumps(fire) + "\n",
                                  encoding="utf-8")
    # mcp config
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"ctx7": {}, "git": {}}}),
                                       encoding="utf-8")
    # NOTE: home/.claude.json — mcpusage default looks at claude_home().parent/.claude.json too
    (tmp_path / ".claude.json").write_text(json.dumps({"mcpServers": {"ctx7": {}, "git": {}}}),
                                           encoding="utf-8")
    return home, tmp_path


def test_scan_usage_collide_compress_cli(env, tmp_path):
    out = tmp_path / "o"
    out.mkdir()
    assert scan_mod.main(["--live", "--out", str(out / "scan.json")]) == 0
    assert usage_mod.main(["--out", str(out / "usage.json")]) == 0
    assert collide_mod.main(["--scan", str(out / "scan.json"), "--min-shared", "2",
                             "--out", str(out / "collide.json")]) == 0
    assert compress_mod.main(["--scan", str(out / "scan.json"),
                              "--out", str(out / "compress.json")]) == 0
    for f in ("scan.json", "usage.json", "collide.json", "compress.json"):
        assert (out / f).exists()


def test_mcpusage_context_lint_evalgate_cli(env, tmp_path):
    home, _ = env
    out = tmp_path / "o2"
    out.mkdir()
    assert mcpusage_mod.main(["--out", str(out / "mcp.json")]) == 0
    assert context_mod.main(["--live", "--out", str(out / "ctx.json")]) == 0
    assert lint_mod.main(["--path", str(home / "skills" / "alpha" / "SKILL.md"),
                          "--out", str(out / "lint.json")]) == 0
    assert evalgate_mod.main(["--name", "alpha", "--out", str(out / "probe.json")]) == 0
    for f in ("mcp.json", "ctx.json", "lint.json", "probe.json"):
        assert (out / f).exists()


def test_report_and_apply_cli(env, tmp_path):
    home, _ = env
    out = tmp_path / "o3"
    out.mkdir()
    scan_mod.main(["--out", str(out / "scan.json")])
    usage_mod.main(["--out", str(out / "usage.json")])
    collide_mod.main(["--scan", str(out / "scan.json"), "--out", str(out / "collide.json")])
    rc = report_mod.main(["--scan", str(out / "scan.json"), "--usage", str(out / "usage.json"),
                          "--collide", str(out / "collide.json"), "--out", str(out / "r.md"),
                          "--actions-out", str(out / "a.json"), "--ignore", "beta"])
    assert rc == 0 and (out / "r.md").exists()
    # apply disable (dry-run) + set-description (dry-run)
    assert apply_mod.main(["--names", "gamma"]) == 0
    assert apply_mod.main(["--set-description", "alpha", "--text", "short review diff"]) == 0


def test_monitor_and_run_cli(env, tmp_path):
    assert monitor_mod.main(["--latest"]) == 0
    assert monitor_mod.main(["--summary"]) == 0
    rc = run_mod.main(["--live", "--out-dir", str(tmp_path / "runout")])
    assert rc == 0
    assert (tmp_path / "runout" / "report.md").exists()
