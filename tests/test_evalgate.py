import evalgate as evalgate_mod


def test_make_probes_from_use_when_clause():
    res = evalgate_mod.make_probes(
        "pandas-pro",
        "Performs pandas DataFrame operations. Use when working with pandas dataframes, "
        "data cleaning, or aggregation.",
        "",
    )
    assert res["name"] == "pandas-pro"
    assert res["should_fire_prompts"]
    joined = " ".join(res["should_fire_prompts"]).lower()
    assert "pandas" in joined or "dataframe" in joined
    assert any(len(k) > 4 for k in res["trigger_keywords"])


def test_make_probes_fallback_when_no_clause():
    res = evalgate_mod.make_probes("widget-maker", "Builds widgets.", "")
    assert res["should_fire_prompts"]   # always at least one probe
