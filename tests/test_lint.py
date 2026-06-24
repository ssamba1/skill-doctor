import lint as lint_mod


def _skill(home, name, desc):
    d = home / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nbody\n", encoding="utf-8")


def test_lint_flags_collision_with_library(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _skill(home, "existing-review", "review the pull request diff for correctness bugs and issues")

    cand = tmp_path / "cand" / "SKILL.md"
    cand.parent.mkdir(parents=True)
    cand.write_text("---\nname: new-review\ndescription: review a diff for correctness bugs and issues\n---\nb\n",
                    encoding="utf-8")
    res = lint_mod.lint(cand, cwd=str(tmp_path / "noproj"), ratio=4.0)
    assert res["nearest_collision"]["name"] == "existing-review"
    assert res["nearest_collision"]["overlap"] >= 0.4
    assert any("collision" in w for w in res["warnings"])


def test_lint_flags_missing_description(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    cand = tmp_path / "cand" / "SKILL.md"
    cand.parent.mkdir(parents=True)
    cand.write_text("---\nname: bare\n---\nbody only\n", encoding="utf-8")
    res = lint_mod.lint(cand, cwd=str(tmp_path / "noproj"), ratio=4.0)
    assert res["has_description"] is False
    assert any("no routing description" in w for w in res["warnings"])


def test_lint_clean_skill(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _skill(home, "unrelated", "generate powerpoint slide decks and presentations")
    cand = tmp_path / "cand" / "SKILL.md"
    cand.parent.mkdir(parents=True)
    cand.write_text("---\nname: tidy\ndescription: short focused database migration helper\n---\nb\n",
                    encoding="utf-8")
    res = lint_mod.lint(cand, cwd=str(tmp_path / "noproj"), ratio=4.0)
    assert res["grade"] in ("A", "B")
    assert res["verdict"] in ("add", "review")
