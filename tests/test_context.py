import context as context_mod


def _skill(home, name, desc):
    d = home / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nbody\n", encoding="utf-8")


def test_context_tallies_all_sources(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    (home).mkdir(parents=True)
    _skill(home, "alpha", "alpha description here")
    (home / "CLAUDE.md").write_text("global instructions " * 50, encoding="utf-8")
    (home / "rules").mkdir()
    (home / "rules" / "style.md").write_text("rule content " * 30, encoding="utf-8")

    res = context_mod.build(cwd=str(tmp_path / "noproj"), ratio=4.0, listing=None)
    names = [s["name"] for s in res["sources"]]
    assert any("skills" in n for n in names)
    assert any("CLAUDE.md" in n for n in names)
    assert any("rules/style.md" in n for n in names)
    assert res["total_est_tokens"] > 0
    # sorted descending
    toks = [s["tokens"] for s in res["sources"]]
    assert toks == sorted(toks, reverse=True)


def test_context_claude_md_follows_at_reference(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    home.mkdir(parents=True)
    (home / "RTK.md").write_text("referenced content " * 20, encoding="utf-8")
    (home / "CLAUDE.md").write_text("main\n@RTK.md\n", encoding="utf-8")
    res = context_mod.build(cwd=str(tmp_path / "noproj"), ratio=4.0, listing=None)
    assert any("@RTK.md" in s["name"] for s in res["sources"])
