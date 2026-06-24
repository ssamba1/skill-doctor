import json

import apply as apply_mod
import sdlib


def _mk(home, name, body="body\n", fm=("name: {n}", "description: d")):
    d = home / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    front = "\n".join(line.format(n=name) for line in fm)
    (d / "SKILL.md").write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")
    return d / "SKILL.md"


def test_add_disable_flag_inserts_and_idempotent():
    text = "---\nname: x\ndescription: d\n---\nbody\n"
    new, changed = apply_mod.add_disable_flag(text)
    assert changed is True
    assert sdlib.as_bool(sdlib.parse_frontmatter(new).get("disable-model-invocation")) is True
    # idempotent
    new2, changed2 = apply_mod.add_disable_flag(new)
    assert changed2 is False
    assert new2 == new


def test_add_disable_flag_no_frontmatter():
    new, changed = apply_mod.add_disable_flag("just body\n")
    assert changed is True
    assert new.startswith("---\n")
    assert sdlib.as_bool(sdlib.parse_frontmatter(new).get("disable-model-invocation")) is True


def test_apply_dryrun_then_write_then_revert(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    p = _mk(home, "alpha")
    original = p.read_text(encoding="utf-8")

    dry = apply_mod.apply_disable("alpha", cwd=str(tmp_path / "noproj"), write=False)
    assert dry["status"] == "would-disable"
    assert p.read_text(encoding="utf-8") == original          # untouched

    res = apply_mod.apply_disable("alpha", cwd=str(tmp_path / "noproj"), write=True)
    assert res["status"] == "disabled"
    assert sdlib.as_bool(
        sdlib.parse_frontmatter(p.read_text(encoding="utf-8")).get("disable-model-invocation")
    ) is True
    assert (home / "skills" / "alpha" / "SKILL.md.bak").exists()

    rev = apply_mod.revert("alpha", cwd=str(tmp_path / "noproj"), write=True)
    assert rev["status"] == "reverted"
    assert p.read_text(encoding="utf-8") == original          # fully restored
    assert not (home / "skills" / "alpha" / "SKILL.md.bak").exists()


def test_apply_crlf_file_byte_exact_roundtrip(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    d = home / "skills" / "crlf"
    d.mkdir(parents=True)
    p = d / "SKILL.md"
    original = b"---\r\nname: crlf\r\ndescription: d\r\n---\r\nbody line\r\n"
    p.write_bytes(original)

    apply_mod.apply_disable("crlf", cwd=str(tmp_path / "noproj"), write=True)
    after = p.read_bytes()
    assert b"disable-model-invocation: true" in after
    assert after.count(b"\n") == after.count(b"\r\n")    # no lone LF -> CRLF preserved
    assert (d / "SKILL.md.bak").read_bytes() == original                       # backup byte-exact

    apply_mod.revert("crlf", cwd=str(tmp_path / "noproj"), write=True)
    assert p.read_bytes() == original                                          # exact restore


def test_set_description_verify_gate_and_success(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    d = home / "skills" / "verbose"
    d.mkdir(parents=True)
    p = d / "SKILL.md"
    orig = ("---\nname: verbose\ndescription: A very long winded description that talks about "
            "pandas dataframes and data analysis at great length and length.\n---\nbody\n")
    p.write_bytes(orig.encode())
    cwd = str(tmp_path / "noproj")

    # gate: drops required trigger word -> skipped
    r = apply_mod.set_description("verbose", "totally unrelated text", cwd, True,
                                  must_contain=["pandas"])
    assert r["status"] == "skipped" and "trigger words" in r["reason"]
    assert p.read_bytes() == orig.encode()        # untouched

    # gate: not shorter -> noop
    r = apply_mod.set_description("verbose", "x" * 500, cwd, True, must_contain=[])
    assert r["status"] == "noop"

    # success: shorter + keeps trigger word
    new = "pandas dataframe analysis."
    r = apply_mod.set_description("verbose", new, cwd, True, must_contain=["pandas"])
    assert r["status"] == "compressed"
    assert sdlib.parse_frontmatter(p.read_text(encoding="utf-8"))["description"] == new
    assert (d / "SKILL.md.bak").exists()

    # revert restores byte-exact
    apply_mod.revert("verbose", cwd, True)
    assert p.read_bytes() == orig.encode()


def test_set_description_dryrun(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _mk(home, "s", body="b\n", fm=("name: {n}", "description: a long enough description here"))
    r = apply_mod.set_description("s", "short", str(tmp_path / "noproj"), False)
    assert r["status"] == "would-compress"


def test_apply_refuses_unknown_skill(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    res = apply_mod.apply_disable("ghost", cwd=str(tmp_path / "noproj"), write=True)
    assert res["status"] == "skipped"


def test_apply_from_actions(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    _mk(home, "alpha")
    actions = tmp_path / "actions.json"
    actions.write_text(json.dumps({"disable_candidates": [{"name": "alpha"}]}), encoding="utf-8")
    rc = apply_mod.main(["--from-actions", str(actions), "--cwd", str(tmp_path / "noproj")])
    assert rc == 0  # dry-run by default, no exception
