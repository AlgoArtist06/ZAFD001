"""The Seam 2 gold eval harness, run against the English subset.

The gold evaluation set is the test suite at this seam (PRD): each gold case
asserts the correct section is cited, or that a Refusal fires for an out-of-scope
or advice-seeking input. Here we load the English subset and require every case
to hold against the offline corpus.
"""
from tests.doubles import offline_assistant
from rag.services.eval import (
    ENGLISH,
    SUPPORTED_LANGUAGES,
    load_gold_cases,
    run_final_eval,
    run_gold_eval,
)


def test_english_gold_subset_is_non_empty():
    cases = load_gold_cases(language=ENGLISH)
    assert cases
    assert all(c.language == ENGLISH for c in cases)
    # The subset must cover both a cited-section case and a Refusal case.
    assert any(c.expected_section for c in cases)
    assert any(c.expect_refusal for c in cases)


def test_gold_eval_runs_and_every_english_case_holds(corpus):
    assistant = offline_assistant(corpus)
    report = run_gold_eval(assistant, load_gold_cases(language=ENGLISH))
    assert report.total == len(load_gold_cases(language=ENGLISH))
    assert report.failures == []
    assert report.passed == report.total


def test_old_ipc_number_gold_case_resolves_to_current_bns(corpus):
    """An old-IPC-number query is a gold case: it must cite the current BNS
    section, proving the IPC-to-BNS normalisation holds end to end."""
    cases = [c for c in load_gold_cases(language=ENGLISH) if "ipc" in c.query.lower()]
    assert cases, "expected a gold case covering an old IPC number"
    report = run_gold_eval(offline_assistant(corpus), cases)
    assert report.failures == []


def test_final_eval_covers_every_supported_language(corpus):
    """The final eval pass runs a non-empty gold subset for each of the four
    Supported Languages, not just English."""
    report = run_final_eval(offline_assistant(corpus))
    assert set(report.by_language) == set(SUPPORTED_LANGUAGES)
    assert set(SUPPORTED_LANGUAGES) == {"en", "hi", "ta", "gu"}
    for language in SUPPORTED_LANGUAGES:
        assert report.by_language[language].report.total > 0


def test_final_eval_meets_the_accuracy_bar_for_each_language(corpus):
    """Every Supported Language's subset must clear the accuracy bar, and the
    final pass as a whole passes only when all of them do."""
    report = run_final_eval(offline_assistant(corpus))
    for language in SUPPORTED_LANGUAGES:
        result = report.by_language[language]
        assert result.meets_bar, (
            f"{language} accuracy {result.accuracy} below bar {result.bar}: "
            f"{[c.id for c in result.report.failures]}"
        )
    assert report.passed


def test_final_eval_fails_when_a_language_misses_the_bar(corpus):
    """A pass that cannot fail proves nothing: an impossible bar of 100% with a
    deliberately wrong expectation must make that language miss the bar and the
    whole pass fail."""
    from rag.services.eval import GoldCase

    bogus = [
        GoldCase(
            id="ta-wrong-section",
            query="திருட்டுக்கான தண்டனை என்ன?",
            language="ta",
            expected_section="999",
            expected_act_id="bns",
        )
    ]
    report = run_final_eval(offline_assistant(corpus), cases_by_language={"ta": bogus}, bar=1.0)
    assert not report.by_language["ta"].meets_bar
    assert not report.passed


def test_gold_eval_catches_a_wrong_section(corpus):
    """A harness that cannot fail proves nothing: a case expecting the wrong
    section must be reported as a failure, not a pass."""
    from rag.services.eval import GoldCase

    assistant = offline_assistant(corpus)
    bogus = GoldCase(
        id="theft-wrong-section",
        query="What is the punishment for theft of movable property?",
        expected_section="999",
        expected_act_id="bns",
    )
    report = run_gold_eval(assistant, [bogus])
    assert report.passed == 0
    assert report.failures == [bogus]
