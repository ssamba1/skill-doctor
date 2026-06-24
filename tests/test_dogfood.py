"""Integration test against the real Claude Code install on this machine.

Opt-in: set SKILL_DOCTOR_DOGFOOD=1 to run (and requires a real Claude skills
dir). Off by default so a plain `pytest` is hermetic and green on any machine,
including contributors who happen to have ~/.claude/skills. Assertions use
thresholds, not exact values, so they tolerate library/transcript drift.
"""
import os

import pytest

import sdlib
import scan as scan_mod
import usage as usage_mod
import collide as collide_mod
import report as report_mod

HOME = sdlib.claude_home()
SKILLS = HOME / "skills"
PROJECTS = HOME / "projects"

_OPT_IN = os.environ.get("SKILL_DOCTOR_DOGFOOD") == "1"

pytestmark = pytest.mark.skipif(
    not (_OPT_IN and SKILLS.exists()),
    reason="dogfood is opt-in: set SKILL_DOCTOR_DOGFOOD=1 (needs a real Claude skills dir)",
)


def test_scan_finds_real_library():
    listing = sdlib.latest_skill_listing(PROJECTS)
    res = scan_mod.build(cwd=None, ratio=4.0, listing=listing)
    assert res["editable_skill_count"] >= 30        # this machine has ~67
    # disabled skills (grill-me, handoff) must report zero cost
    by = {s["name"]: s for s in res["skills"]}
    for s in res["skills"]:
        if s["disabled"]:
            assert s["est_tokens"] == 0
    if "grill-me" in by:
        assert by["grill-me"]["disabled"] is True
    if listing:
        assert res["loaded_total_est_tokens"] > 1000     # 89 skills ~ thousands of tokens


def test_usage_detects_real_fires():
    res = usage_mod.mine(PROJECTS, window_days=3650)
    assert res["files_scanned"] > 0
    assert res["total_fires"] >= 1
    assert res["distinct_skills_fired"] >= 1
    assert res["history_days"] is None or res["history_days"] >= 0


def test_collide_finds_candidates_on_real_library():
    skills = sdlib.discover_skills(sdlib.default_roots(None))
    pairs = collide_mod.find_pairs(skills, threshold=0.40)
    assert len(pairs) >= 1                            # 67 skills -> overlaps exist


def test_full_report_builds_on_real_data():
    listing = sdlib.latest_skill_listing(PROJECTS)
    scan = scan_mod.build(cwd=None, ratio=4.0, listing=listing)
    usage = usage_mod.mine(PROJECTS, window_days=3650)
    coll = {"threshold": 0.3,
            "pairs": collide_mod.find_pairs(scan["skills"], 0.30)}
    md, actions = report_mod.build(scan, usage, coll)
    assert "skill-doctor report" in md
    assert isinstance(actions["projected_token_savings"], int)
    assert actions["projected_token_savings"] >= 0
