"""Parse and rewrite tests for headline_rewrite.py -- no model, no network.

The fixture is a trimmed copy of a real Qodo review comment: a Critical band with a
live bug and a resolved rule violation, then a Warning band nested inside a collapsed
<details>, with a finding whose title contains identifiers. Those four shapes are
where a naive regex rewrite breaks the comment.
"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "qodo_review_comment.md"

_spec = importlib.util.spec_from_file_location(
    "headline_rewrite", ROOT / ".qodo" / "ci" / "headline_rewrite.py")
hr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hr)

BODY = FIXTURE.read_text()

HEADLINES = {
    "A retry that quietly fails leaves reviewers with no advisory at all",
    "A missing permission stops the advisory from ever reaching the review",
    "A failed lookup is reported as an empty result and hides real outages",
}


def parsed():
    return hr.parse_findings(BODY)


def translations():
    """Deterministic stand-ins for the model pass, keyed the way the engine keys them."""
    f = parsed()
    hl = dict(zip([x["id"] for x in f], sorted(HEADLINES)))
    sw = {x["id"]: "Reviewers act on a stale picture of the change. It happens whenever "
                   "the review is refreshed after the first pass." for x in f}
    return hl, sw


def test_parses_every_finding():
    f = parsed()
    assert [x["num"] for x in f] == [1, 2, 3]
    assert f[0]["title"] == "Reapply failure ignored"
    assert f[1]["title"] == "Missing issues write permission"
    # Identifier markup in a title is stripped for the model, not for the comment.
    assert f[2]["title"] == "gh_json() silently drops errors"
    assert "<b><i>" in f[2]["title_html"]


def test_reads_category_severity_and_resolved_state():
    f = parsed()
    assert [x["level"] for x in f] == ["Critical", "Critical", "Warning"]
    assert f[0]["category"] == "🐞 Bug"
    assert f[1]["category"] == "📘 Rule violation"
    assert f[2]["category"] == "📜 Skill insight"
    assert [x["resolved"] for x in f] == [False, True, False]


def test_description_is_prose_without_markup():
    d = parsed()[0]["description"]
    assert d.startswith("When the findings comment is overwritten")
    assert "<b>" not in d and ">" not in d
    assert all(x["description"] for x in parsed())


def test_ids_are_stable_across_renumbering():
    before = {x["title"]: x["id"] for x in parsed()}
    shifted = BODY.replace("<summary>  3.", "<summary>  9.")
    after = {x["title"]: x["id"] for x in hr.parse_findings(shifted)}
    assert before == after


def test_rewrite_replaces_the_lead_line_and_keeps_the_tags():
    hl, sw = translations()
    new, done = hr.rewrite_body(BODY, hl, sw)
    assert done == 3
    for headline in HEADLINES:
        assert "<summary>  " in new and headline in new
    assert "Reapply failure ignored" not in new.split("What this means")[0]
    # Tags, and only the tags, survive on the summary line.
    assert "<code>🐞 Bug</code> <code>☼ Reliability</code> <code>⭐ New</code>" in new
    assert "<code>✓ Resolved</code>" in new


def test_rewrite_demotes_rather_than_deletes_the_engine_wording():
    hl, sw = translations()
    new, _ = hr.rewrite_body(BODY, hl, sw)
    assert "<code>Qodo&#x27;s title: Reapply failure ignored</code>" in new or \
           "<code>Qodo's title: Reapply failure ignored</code>" in new
    assert "Qodo's title: gh_json() silently drops errors" in new
    # Every engine block is still there, untouched.
    for block in ("><summary>Description</summary>", "><summary>Code</summary>"):
        assert new.count(block) == BODY.count(block)
    assert "apply_to_review(...)" in new
    assert new.count("What this means") == 3


def test_resolved_findings_stay_struck_through():
    hl, sw = translations()
    new, _ = hr.rewrite_body(BODY, hl, sw)
    line = [ln for ln in new.split("\n") if ln.startswith("<summary>  2.")][0]
    assert line.count("<s>") == 1 and line.count("</s>") == 1
    assert "<s>" not in [ln for ln in new.split("\n")
                         if ln.startswith("<summary>  1.")][0]


def test_details_nesting_is_preserved():
    hl, sw = translations()
    new, _ = hr.rewrite_body(BODY, hl, sw)
    # The inserted blocks are balanced, so the collapsed Warning band still closes.
    assert new.count("<details") - new.count("</details>") == 0


def test_a_second_pass_is_a_fixed_point():
    hl, sw = translations()
    new, _ = hr.rewrite_body(BODY, hl, sw)
    assert new.count(hr.MARKER) == 1
    again, done = hr.rewrite_body(new, hl, sw)
    assert again == new
    assert done == 0
    assert again.count("What this means") == 3


def test_a_missing_headline_leaves_that_finding_exactly_as_qodo_wrote_it():
    hl, sw = translations()
    first = parsed()[0]["id"]
    hl.pop(first)
    new, done = hr.rewrite_body(BODY, hl, sw)
    assert done == 2
    assert "<summary>  1.  Reapply failure ignored <code>🐞 Bug</code>" in new
    assert new.count("What this means") == 2


def test_no_headlines_at_all_is_a_no_op_apart_from_the_marker():
    new, done = hr.rewrite_body(BODY, {}, {})
    assert done == 0
    assert new.replace("\n" + hr.MARKER + "\n", "").rstrip() == BODY.rstrip()
