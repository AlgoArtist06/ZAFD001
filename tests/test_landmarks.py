"""Seam 1 tests: the curated Landmark Judgment file."""
from pathlib import Path

from ingestion.landmarks import load_landmark_judgments

DATA = Path(__file__).resolve().parent.parent / "data"


def _judgments():
    return load_landmark_judgments(DATA / "landmark_judgments.json")


def test_landmark_file_is_loaded():
    assert len(_judgments()) >= 4


def test_every_judgment_carries_a_full_official_citation():
    for j in _judgments():
        assert j.case_name
        assert j.citation
        assert j.year
        assert j.court
        assert j.official_url
        assert j.has_full_citation()


def test_a_known_judgment_is_present_with_correct_citation():
    by_id = {j.id: j for j in _judgments()}
    assert by_id["ks-puttaswamy-2017"].citation == "(2017) 10 SCC 1"


def test_a_judgment_missing_a_citation_field_is_not_fully_cited():
    from ingestion.landmarks import LandmarkJudgment

    incomplete = LandmarkJudgment(
        id="x",
        case_name="X v. Y",
        citation="",
        year=2020,
        court="Supreme Court of India",
        official_url="https://main.sci.gov.in/judgments",
        domain="constitutional",
        holding="...",
    )
    assert not incomplete.has_full_citation()
