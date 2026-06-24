import collide as collide_mod


def test_find_pairs_flags_similar_and_ignores_unrelated():
    skills = [
        {"name": "review", "description": "review the pull request diff for correctness bugs",
         "when_to_use": ""},
        {"name": "diff-review", "description": "review a diff for correctness and bugs",
         "when_to_use": ""},
        {"name": "pptx", "description": "create a powerpoint slide deck presentation",
         "when_to_use": ""},
    ]
    pairs = collide_mod.find_pairs(skills, threshold=0.3)
    names = {(p["a"], p["b"]) for p in pairs}
    assert ("review", "diff-review") in names
    # pptx should not collide with the review skills
    assert all("pptx" not in (p["a"], p["b"]) for p in pairs)


def test_threshold_controls_output():
    skills = [
        {"name": "a", "description": "alpha beta gamma delta", "when_to_use": ""},
        {"name": "b", "description": "alpha beta epsilon zeta", "when_to_use": ""},
    ]
    hi = collide_mod.find_pairs(skills, threshold=0.9, min_shared=1)
    lo = collide_mod.find_pairs(skills, threshold=0.1, min_shared=1)
    assert len(hi) == 0
    assert len(lo) == 1
    assert lo[0]["score"] > 0


def test_min_shared_words_suppresses_asymmetric_noise():
    # One short description sharing a single coincidental word with a long one
    # inflates the overlap coefficient; the min-shared gate must drop it.
    skills = [
        {"name": "short", "description": "design things", "when_to_use": ""},
        {"name": "long", "description":
            "design a comprehensive system with many components and modules and layers",
            "when_to_use": ""},
    ]
    # overlap coef would be high (1/2) on the single shared word "design"
    assert collide_mod.find_pairs(skills, threshold=0.4, min_shared=3) == []
    # lowering the gate lets it through
    assert len(collide_mod.find_pairs(skills, threshold=0.4, min_shared=1)) == 1


def test_pairs_sorted_desc():
    skills = [
        {"name": "a", "description": "one two three four", "when_to_use": ""},
        {"name": "b", "description": "one two three four", "when_to_use": ""},
        {"name": "c", "description": "one five six seven", "when_to_use": ""},
    ]
    pairs = collide_mod.find_pairs(skills, threshold=0.05, min_shared=1)
    scores = [p["score"] for p in pairs]
    assert scores == sorted(scores, reverse=True)
    assert len(pairs) >= 2
