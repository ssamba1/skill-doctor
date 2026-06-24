import compress as compress_mod


def test_find_candidates_flags_verbose_keeps_short_skips_disabled():
    skills = [
        {"name": "big", "description": "d", "when_to_use": "", "est_tokens": 300,
         "disabled": False, "conditional": False},
        {"name": "small", "description": "d", "when_to_use": "", "est_tokens": 20,
         "disabled": False, "conditional": False},
        {"name": "off", "description": "d", "when_to_use": "", "est_tokens": 0,
         "disabled": True, "conditional": False},
        {"name": "scoped", "description": "d", "when_to_use": "", "est_tokens": 400,
         "disabled": False, "conditional": True},
    ]
    cands = compress_mod.find_candidates(skills, target_tokens=75, ratio=4.0)
    names = [c["name"] for c in cands]
    assert names == ["big"]                      # small under target; off/scoped excluded
    assert cands[0]["potential_savings"] == 225  # 300 - 75


def test_find_candidates_computes_tokens_when_missing():
    skills = [{"name": "x", "description": "z" * 1200, "when_to_use": ""}]
    cands = compress_mod.find_candidates(skills, target_tokens=75, ratio=4.0)
    assert cands and cands[0]["current_tokens"] > 75
