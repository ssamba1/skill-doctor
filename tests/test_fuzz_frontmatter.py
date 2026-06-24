"""Property/fuzz tests for the frontmatter parser and field-setter — the riskiest
code (it processes arbitrary user-authored SKILL.md). Seeded RNG for determinism."""
import random
import string

import sdlib

ALPHABET = string.ascii_letters + string.digits + " .,:;-_/()[]#*@!?%+=" + "\t"


def _rand_text(rng, n):
    return "".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, n)))


def _rand_frontmatter(rng):
    keys = ["name", "description", "when_to_use", "license", "model", "argument-hint"]
    lines = []
    for k in rng.sample(keys, rng.randint(1, len(keys))):
        style = rng.randint(0, 3)
        if style == 0:
            lines.append(f"{k}: {_rand_text(rng, 60)}")
        elif style == 1:
            lines.append(f'{k}: "{_rand_text(rng, 60)}"')
        elif style == 2:  # block scalar
            lines.append(f"{k}: |")
            for _ in range(rng.randint(1, 3)):
                lines.append("  " + _rand_text(rng, 40))
        else:  # multi-line plain
            lines.append(f"{k}:")
            for _ in range(rng.randint(1, 3)):
                lines.append("  " + _rand_text(rng, 40))
    body = "\n".join(_rand_text(rng, 50) for _ in range(rng.randint(0, 4)))
    return "---\n" + "\n".join(lines) + "\n---\n" + body + "\n"


def test_parse_never_raises_on_fuzz():
    rng = random.Random(1234)
    for _ in range(400):
        text = _rand_frontmatter(rng)
        fm = sdlib.parse_frontmatter(text)          # must not raise
        assert isinstance(fm, dict)
        assert "_body" in fm


def test_set_field_roundtrip_property():
    """For safe values (no quotes/backslashes/newlines), setting then parsing
    description yields the normalized value, and other keys survive."""
    rng = random.Random(99)
    safe = string.ascii_letters + string.digits + " .,-_/()"
    for _ in range(400):
        text = _rand_frontmatter(rng)
        had_name = "name" in sdlib.parse_frontmatter(text)
        val = "".join(rng.choice(safe) for _ in range(rng.randint(1, 80))).strip() or "x"
        out = sdlib.set_frontmatter_field(text, "description", val)
        fm = sdlib.parse_frontmatter(out)
        assert fm.get("description") == " ".join(val.split())
        if had_name:
            assert "name" in fm                     # unrelated key preserved


def test_set_field_arbitrary_value_never_corrupts_parse():
    """Even with quotes/backslashes, the result must still parse and round-trip
    a description field (value may differ due to escaping, but never crash)."""
    rng = random.Random(7)
    for _ in range(200):
        text = _rand_frontmatter(rng)
        val = _rand_text(rng, 80) + rng.choice(['"', "\\", '"x\\y"', "\n"])
        out = sdlib.set_frontmatter_field(text, "description", val)
        fm = sdlib.parse_frontmatter(out)           # must not raise
        assert "description" in fm
