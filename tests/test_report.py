import report as report_mod


def _scan():
    return {
        "chars_per_token": 4.0,
        "editable_skill_count": 3,
        "disabled_count": 0,
        "editable_total_est_tokens": 100,
        "loaded_count": 3,
        "loaded_injected_chars": 400,
        "loaded_total_est_tokens": 100,
        "skills": [
            {"name": "neverfired", "level": "personal", "est_tokens": 60, "disabled": False,
             "user_invocable": True, "loaded": True, "path": "/x/neverfired/SKILL.md",
             "description": "d", "when_to_use": "", "stale": []},
            {"name": "used", "level": "personal", "est_tokens": 30, "disabled": False,
             "user_invocable": True, "loaded": True, "path": "/x/used/SKILL.md",
             "description": "d", "when_to_use": "", "stale": ["claude-instant-1"]},
            {"name": "off", "level": "personal", "est_tokens": 0, "disabled": True,
             "user_invocable": True, "loaded": False, "path": "/x/off/SKILL.md",
             "description": "d", "when_to_use": "", "stale": []},
        ],
    }


def _usage():
    return {"skills": {"used": {"count": 5, "window_count": 2, "last": "2026-06-20T00:00:00Z"}}}


def _collide():
    return {"threshold": 0.3, "pairs": [{"a": "neverfired", "b": "used", "score": 0.5}]}


def test_report_identifies_disable_candidate_and_savings():
    md, actions = report_mod.build(_scan(), _usage(), _collide())
    cand = actions["disable_candidates"]
    assert [c["name"] for c in cand] == ["neverfired"]      # used has fired; off already disabled
    assert actions["projected_token_savings"] == 60
    assert actions["projected_pct_savings"] == 60.0
    assert "neverfired" in md
    assert "~60 tokens/turn" in md


def test_report_includes_collisions_and_staleness():
    md, actions = report_mod.build(_scan(), _usage(), _collide())
    assert any(p["a"] == "neverfired" for p in actions["collision_pairs"])
    assert "neverfired" in md and "used" in md
    assert any("claude-instant-1" in s["stale"] for s in actions["stale"])
    assert "claude-instant-1" in md


def test_report_excludes_attribution_only_fired_skill():
    # 'neverfired' has no tool_use count but was attributed -> must NOT be a candidate.
    usage = {"skills": {"neverfired": {"count": 0, "attributed": True},
                        "used": {"count": 5}}}
    md, actions = report_mod.build(_scan(), usage, {"pairs": []})
    assert [c["name"] for c in actions["disable_candidates"]] == []
    assert actions["projected_token_savings"] == 0


def test_report_too_new_excluded_from_candidates():
    scan = _scan()
    scan["skills"][0]["age_days"] = 2.0          # neverfired added 2 days ago
    md, actions = report_mod.build(scan, _usage(), _collide(), grace_days=7.0)
    assert [c["name"] for c in actions["disable_candidates"]] == []
    assert [c["name"] for c in actions["too_new_to_judge"]] == ["neverfired"]
    assert actions["projected_token_savings"] == 0
    assert "too new to judge" in md.lower()


def test_report_conditional_skill_not_a_candidate():
    scan = _scan()
    scan["skills"][0]["conditional"] = True       # neverfired is paths-scoped
    md, actions = report_mod.build(scan, _usage(), _collide())
    assert [c["name"] for c in actions["disable_candidates"]] == []
    assert "neverfired" in actions["conditional_skills"]


def test_report_splits_duplicates_from_collisions():
    coll = {"threshold": 0.4, "pairs": [
        {"a": "x", "b": "y", "score": 0.9, "jaccard": 0.8, "shared": ["a", "b", "c"]},
        {"a": "p", "b": "q", "score": 0.5, "jaccard": 0.2, "shared": ["d", "e", "f"]},
    ]}
    md, actions = report_mod.build(_scan(), _usage(), coll, dup_threshold=0.6)
    assert [(p["a"], p["b"]) for p in actions["duplicate_pairs"]] == [("x", "y")]
    assert [(p["a"], p["b"]) for p in actions["collision_pairs"]] == [("p", "q")]
    assert "Likely duplicates" in md


def test_report_handles_no_candidates():
    scan = _scan()
    # mark neverfired as fired
    usage = {"skills": {"used": {"count": 1}, "neverfired": {"count": 1}}}
    md, actions = report_mod.build(scan, usage, {"pairs": []})
    assert actions["disable_candidates"] == []
    assert "None" in md
