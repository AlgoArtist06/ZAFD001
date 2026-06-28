"""The Seam 2 gold eval harness, run against the English subset.

The gold evaluation set is the test suite at this seam (PRD): each gold case
asserts the correct section is cited, or that a Refusal fires for an out-of-scope
or advice-seeking input. Here we load the English subset and require every case
to hold against the offline corpus.
"""
from rag.answer import LegalAssistant
from rag.eval import ENGLISH, load_gold_cases, run_gold_eval


def test_english_gold_subset_is_non_empty():
    cases = load_gold_cases(language=ENGLISH)
    assert cases
    assert all(c.language == ENGLISH for c in cases)
    # The subset must cover both a cited-section case and a Refusal case.
    assert any(c.expected_section for c in cases)
    assert any(c.expect_refusal for c in cases)


def test_gold_eval_runs_and_every_english_case_holds(corpus):
    assistant = LegalAssistant(corpus)
    report = run_gold_eval(assistant, load_gold_cases(language=ENGLISH))
    assert report.total == len(load_gold_cases(language=ENGLISH))
    assert report.failures == []
    assert report.passed == report.total


def test_gold_eval_catches_a_wrong_section(corpus):
    """A harness that cannot fail proves nothing: a case expecting the wrong
    section must be reported as a failure, not a pass."""
    from rag.eval import GoldCase

    assistant = LegalAssistant(corpus)
    bogus = GoldCase(
        id="theft-wrong-section",
        query="What is the punishment for theft of movable property?",
        expected_section="999",
        expected_act_id="bns",
    )
    report = run_gold_eval(assistant, [bogus])
    assert report.passed == 0
    assert report.failures == [bogus]
