from skill_factory.frontmatter import build_skill_md, has_frontmatter, split_frontmatter


def test_roundtrip():
    md = build_skill_md({"name": "x-skill", "description": "Use when X."}, "# Body\nAlways do X.")
    fm, body = split_frontmatter(md)
    assert fm["name"] == "x-skill"
    assert fm["description"] == "Use when X."
    assert "Always do X." in body


def test_no_frontmatter():
    fm, body = split_frontmatter("# Just a heading\nno frontmatter")
    assert fm == {}
    assert body.startswith("# Just a heading")
    assert not has_frontmatter("no fm here")


def test_malformed_yaml_recovers_body():
    text = "---\nname: [unclosed\n---\n\nThe body.\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert "The body." in body


def test_missing_close_delim():
    fm, _body = split_frontmatter("---\nname: x\nno closing delimiter")
    assert fm == {}
