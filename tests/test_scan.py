import json

import scan as scan_mod


def _mk(home, name, desc, **fm):
    d = home / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"name: {name}", f"description: {desc}"]
    for k, v in fm.items():
        lines.append(f"{k.replace('_', '-')}: {v}")
    lines.append("---")
    lines.append(f"body for {name}")
    (d / "SKILL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_scan_inventory_and_cost(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _mk(home, "alpha", "alpha does things " * 5)
    _mk(home, "beta", "beta short")
    _mk(home, "gamma", "gamma off", **{"disable-model-invocation": "true"})

    res = scan_mod.build(cwd=str(tmp_path / "noproj"), ratio=4.0, listing=None)
    assert res["editable_skill_count"] == 3
    assert res["disabled_count"] == 1

    by = {s["name"]: s for s in res["skills"]}
    assert by["gamma"]["disabled"] is True
    assert by["gamma"]["est_tokens"] == 0          # disabled -> cost 0
    assert by["alpha"]["est_tokens"] > by["beta"]["est_tokens"]
    assert res["editable_total_est_tokens"] == sum(s["est_tokens"] for s in res["skills"])


def test_scan_staleness(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    d = home / "skills" / "oldie"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: oldie\ndescription: legacy\n---\nUses claude-instant-1 and text-davinci-003.\n",
        encoding="utf-8",
    )
    res = scan_mod.build(cwd=str(tmp_path / "noproj"), ratio=4.0, listing=None)
    s = res["skills"][0]
    assert "claude-instant-1" in s["stale"]
    assert "text-davinci-003" in s["stale"]
    assert res["stale_count"] == 1


def test_scan_with_listing_crosscheck(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _mk(home, "alpha", "alpha desc")
    _mk(home, "beta", "beta desc")
    listing = {
        "type": "skill_listing",
        "skillCount": 2,
        "names": ["alpha", "builtin-review"],     # alpha loaded; beta not; builtin not on disk
        "content": "- alpha: alpha desc from listing\n- builtin-review: review things",
    }
    res = scan_mod.build(cwd=str(tmp_path / "noproj"), ratio=4.0, listing=listing)
    assert res["loaded_count"] == 2
    assert res["loaded_not_editable"] == ["builtin-review"]
    assert res["editable_not_loaded"] == ["beta"]
    assert res["loaded_total_est_tokens"] > 0
    by = {s["name"]: s for s in res["skills"]}
    assert by["alpha"]["loaded"] is True
    assert by["beta"]["loaded"] is False


def test_scan_conditional_paths_scoped_excluded_from_tax(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _mk(home, "always", "always on skill")
    _mk(home, "scoped", "only for ts files", paths="**/*.ts")
    res = scan_mod.build(cwd=str(tmp_path / "noproj"), ratio=4.0, listing=None)
    by = {s["name"]: s for s in res["skills"]}
    assert by["scoped"]["conditional"] is True
    assert by["scoped"]["est_tokens"] == 0          # paths-scoped -> not always-on
    assert by["always"]["est_tokens"] > 0
    assert res["conditional_count"] == 1
    assert res["editable_total_est_tokens"] == by["always"]["est_tokens"]


def test_scan_age_days_computed(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _mk(home, "alpha", "alpha")
    # pretend "now" is 10 days after the file mtime
    import os
    mt = os.path.getmtime(home / "skills" / "alpha" / "SKILL.md")
    res = scan_mod.build(cwd=str(tmp_path / "noproj"), ratio=4.0, listing=None,
                         now=mt + 10 * 86400)
    assert res["skills"][0]["age_days"] == 10.0


def test_scan_exact_without_key_falls_back(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _mk(home, "alpha", "alpha desc")
    res = scan_mod.build(cwd=str(tmp_path / "noproj"), ratio=4.0, listing=None, exact=True)
    assert res["exact_tokens"] is False               # no key -> estimate
    assert res["skills"][0]["est_tokens"] > 0


def test_scan_main_writes_out(tmp_path, monkeypatch, capsys):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _mk(home, "alpha", "alpha desc")
    out = tmp_path / "scan.json"
    rc = scan_mod.main(["--cwd", str(tmp_path / "noproj"), "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["editable_skill_count"] == 1
