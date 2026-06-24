import sdlib


def test_parse_frontmatter_simple():
    fm = sdlib.parse_frontmatter('---\nname: foo\ndescription: does a thing\n---\nbody here\n')
    assert fm["name"] == "foo"
    assert fm["description"] == "does a thing"
    assert fm["_body"].strip() == "body here"


def test_parse_frontmatter_quoted_and_bool():
    fm = sdlib.parse_frontmatter(
        '---\nname: "x"\ndescription: \'a: b, c\'\ndisable-model-invocation: true\n---\nx\n'
    )
    assert fm["name"] == "x"
    assert fm["description"] == "a: b, c"
    assert fm["disable-model-invocation"] is True


def test_parse_frontmatter_block_scalar():
    txt = (
        "---\n"
        "name: pa\n"
        "description: |\n"
        "  line one\n"
        "  line two\n"
        "argument-hint: \"<x>\"\n"
        "---\n"
        "body\n"
    )
    fm = sdlib.parse_frontmatter(txt)
    assert "line one" in fm["description"]
    assert "line two" in fm["description"]
    assert fm["argument-hint"] == "<x>"


def test_parse_frontmatter_implicit_multiline_plain_scalar():
    # YAML implicit multi-line plain scalar (empty value + indented continuation),
    # the style Anthropic's own skills use. Must fold, not drop.
    txt = (
        "---\n"
        "name: uv\n"
        "description:\n"
        "  Guide for using uv. Use this when working with Python projects,\n"
        "  scripts, packages, or tools.\n"
        "---\n"
        "body\n"
    )
    fm = sdlib.parse_frontmatter(txt)
    assert fm["description"].startswith("Guide for using uv")
    assert "packages, or tools." in fm["description"]
    assert "\n" not in fm["description"]          # folded with spaces


def test_parse_frontmatter_nested_mapping_does_not_pollute():
    txt = (
        "---\n"
        "name: x\n"
        "description: d\n"
        "metadata:\n"
        "  author: vercel\n"
        "  version: '1.0.0'\n"
        "---\n"
        "body\n"
    )
    fm = sdlib.parse_frontmatter(txt)
    assert fm["description"] == "d"
    assert fm["name"] == "x"               # nested keys consumed, not promoted
    assert "author" not in fm


def test_parse_frontmatter_crlf_and_no_trailing_newline():
    crlf = "---\r\nname: x\r\ndescription: hi\r\n---\r\nbody\r\n"
    fm = sdlib.parse_frontmatter(crlf)
    assert fm["description"] == "hi"
    eof = "---\nname: y\ndescription: bye\n---"   # no trailing newline
    fm2 = sdlib.parse_frontmatter(eof)
    assert fm2["description"] == "bye"


def test_parse_frontmatter_no_frontmatter():
    fm = sdlib.parse_frontmatter("just a body, no fence")
    assert fm["_body"] == "just a body, no fence"
    assert "description" not in fm


def test_injected_text_caps_at_1536():
    long_desc = "z" * 5000
    out = sdlib.injected_text("big", long_desc)
    # prefix "- big: " + 1536 capped chars
    assert out.startswith("- big: ")
    assert len(out) == len("- big: ") + sdlib.LISTING_CAP_CHARS


def test_injected_text_appends_when_to_use():
    out = sdlib.injected_text("s", "desc", "use when X")
    assert "desc use when X" in out


def test_est_tokens():
    assert sdlib.est_tokens("", ) == 0
    assert sdlib.est_tokens("a" * 40, 4.0) == 10


def test_as_bool():
    assert sdlib.as_bool(True) is True
    assert sdlib.as_bool("true") is True
    assert sdlib.as_bool("no") is False
    assert sdlib.as_bool(None, True) is True


def test_stale_findings():
    assert sdlib.stale_findings("use claude-instant-1 here") == ["claude-instant-1"]
    assert sdlib.stale_findings("text-davinci-003 and gpt-4-32k") == sorted(
        ["text-davinci-003", "gpt-4-32k"]
    )
    assert sdlib.stale_findings("claude-opus-4-8 is fine") == []


def test_jaccard_and_tokenize():
    a = sdlib.tokenize_words("review the pull request diff for bugs")
    b = sdlib.tokenize_words("review a diff for bugs and issues")
    assert sdlib.jaccard(a, b) > 0.3
    c = sdlib.tokenize_words("generate a powerpoint presentation deck")
    assert sdlib.jaccard(a, c) < 0.2
    assert sdlib.jaccard(set(), a) == 0.0


def test_count_tokens_exact_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert sdlib.count_tokens_exact("some text", api_key=None) is None
    assert sdlib.count_tokens_exact("", api_key="sk-whatever") is None  # empty text


def test_parse_listing_content():
    content = "- alpha: does alpha\n- beta: does beta\n  continued\n- gamma: g"
    m = sdlib.parse_listing_content(content)
    assert m["alpha"] == "does alpha"
    assert "continued" in m["beta"]
    assert m["gamma"] == "g"
