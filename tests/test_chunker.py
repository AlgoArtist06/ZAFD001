"""Seam 1 structural tests: adaptive hierarchical chunking."""
from ingestion.chunker import chunk_act, estimate_tokens
from ingestion.parser import parse_act

SMALL_AND_LARGE = """\
ACT_ID: bns
ACT: Bharatiya Nyaya Sanhita
YEAR: 2023
TYPE: criminal
SOURCE_URL: https://www.indiacode.nic.in/bns
RETRIEVAL_DATE: 2026-06-28
===
Section 319. Cheating by personation.
A person is said to cheat by personation if he cheats by pretending to be some
other person.

Section 318. Cheating.
(1) {a}
(2) {b}
(3) {c}
""".replace("{a}", " word" * 200).replace("{b}", " word" * 200).replace(
    "{c}", " word" * 200
)


def _chunk(threshold=512):
    return chunk_act(parse_act(SMALL_AND_LARGE), token_threshold=threshold)


def test_small_section_is_stored_whole():
    chunks = _chunk()
    whole = [c for c in chunks if c.section_number == "319"]
    assert len(whole) == 1
    assert whole[0].parent_section_id is None
    assert "pretending to be some" in whole[0].text


def test_large_section_is_split_into_per_sub_section_children():
    chunks = _chunk()
    children = [c for c in chunks if c.section_number == "318"]
    assert len(children) == 3
    assert all(c.is_child() for c in children)
    assert [c.sub_section for c in children] == ["1", "2", "3"]


def test_every_child_points_at_its_parent_section_id():
    chunks = _chunk()
    children = [c for c in chunks if c.section_number == "318"]
    assert all(c.parent_section_id == "bns-318" for c in children)


def test_child_provenance_records_the_sub_section_text_verbatim():
    chunks = _chunk()
    first = next(c for c in _chunk() if c.sub_section == "1")
    assert first.provenance.sub_section == "1"
    assert first.provenance.verbatim_text == first.text
    assert first.provenance.is_complete()


def test_amendment_history_is_captured_on_every_chunk():
    chunks = _chunk()
    assert all(c.amendment_history.is_captured() for c in chunks)


def test_token_threshold_governs_the_split():
    # With a huge threshold even the big section stays whole.
    chunks = chunk_act(parse_act(SMALL_AND_LARGE), token_threshold=100000)
    big = [c for c in chunks if c.section_number == "318"]
    assert len(big) == 1
    assert big[0].parent_section_id is None


def test_estimate_tokens_grows_with_text():
    assert estimate_tokens("one two three") < estimate_tokens("one two three four five")
