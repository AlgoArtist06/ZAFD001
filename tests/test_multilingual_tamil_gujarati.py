"""The multilingual answering layer, extended to Tamil and Gujarati.

Issue 07 widens the Hindi seam to two lower-resource Supported Languages. The
same rules hold: detect the user's language, extract intent into an English query
(legal terms preserved) so retrieval and reasoning run over the single English
Source of Truth, then answer back in the user's language. The Bilingual Legal
Glossary supplies the Tamil and Gujarati terminology; the Citation Anchor stays
verbatim English; critical terms appear in the target language with the English
term inline in brackets; and a Confirmation Step fires for ambiguous Citizen-mode
queries. Because central-act translations may be unavailable to verify these
languages, the glossary also flags any term lacking an official translation
source, and the gold eval set gets extra per-language attention.
"""
import re

from tests.doubles import offline_assistant
from rag.services.eval import load_gold_cases, run_gold_eval
from rag.domain.multilingual import (
    BilingualGlossary,
    confirmation_for,
    detect_language,
)

_TAMIL = re.compile(r"[஀-௿]")
_GUJARATI = re.compile(r"[઀-૿]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def test_detect_language_distinguishes_tamil_and_gujarati():
    assert detect_language("திருட்டுக்கான தண்டனை என்ன?") == "ta"
    assert detect_language("ચોરી માટે સજા શું છે?") == "gu"
    # The Hindi and English paths are untouched.
    assert detect_language("चोरी की सजा क्या है?") == "hi"
    assert detect_language("What is the punishment for theft?") == "en"


def test_intent_extraction_normalises_tamil_and_gujarati_to_english():
    glossary = BilingualGlossary.load()
    tamil = glossary.to_english("திருட்டுக்கான தண்டனை என்ன?")
    assert "theft" in tamil.lower().split()
    assert "punishment" in tamil.lower().split()
    assert not _TAMIL.search(tamil)

    gujarati = glossary.to_english("ચોરી માટે સજા શું છે?")
    assert "theft" in gujarati.lower().split()
    assert "punishment" in gujarati.lower().split()
    assert not _GUJARATI.search(gujarati)


def test_intent_extraction_handles_code_mixing_in_tamil_and_gujarati():
    glossary = BilingualGlossary.load()
    tamil = glossary.to_english("என் mobile திருட்டு போனது, தண்டனை என்ன").lower()
    assert "mobile" in tamil
    assert "theft" in tamil
    assert "punishment" in tamil

    gujarati = glossary.to_english("મારો mobile ચોરી થઈ ગયો, સજા શું છે").lower()
    assert "mobile" in gujarati
    assert "theft" in gujarati
    assert "punishment" in gujarati


def test_tamil_query_retrieves_over_english_corpus_and_answers_in_tamil(corpus):
    result = offline_assistant(corpus).answer("திருட்டுக்கான தண்டனை என்ன?")
    assert not result.refused
    assert result.language == "ta"
    # Reasoning ran over the English corpus: the correct BNS section is cited.
    assert any(c.section_number == "303" for c in result.citations)
    # The answer itself is generated in Tamil.
    assert _TAMIL.search(result.explanation)


def test_gujarati_query_retrieves_over_english_corpus_and_answers_in_gujarati(corpus):
    result = offline_assistant(corpus).answer("ચોરી માટે સજા શું છે?")
    assert not result.refused
    assert result.language == "gu"
    assert any(c.section_number == "303" for c in result.citations)
    assert _GUJARATI.search(result.explanation)


def test_citation_anchor_stays_verbatim_english_for_tamil_and_gujarati(corpus):
    assistant = offline_assistant(corpus)
    for query, script in (
        ("திருட்டுக்கான தண்டனை என்ன?", _TAMIL),
        ("ચોરી માટે સજા શું છે?", _GUJARATI),
    ):
        anchor = assistant.answer(query).citations[0].anchor
        # The Citation Anchor (reference + Verbatim Text) is original English only.
        assert not script.search(anchor)
        assert "Bharatiya Nyaya Sanhita" in anchor


def test_critical_terms_show_target_language_with_english_in_brackets(corpus):
    assistant = offline_assistant(corpus)
    glossary = BilingualGlossary.load()

    tamil = assistant.answer("திருட்டுக்கான தண்டனை என்ன?")
    criminal_ta = glossary.term_for("criminal law", "ta")
    assert criminal_ta and criminal_ta in tamil.explanation
    assert "(criminal law)" in tamil.explanation

    gujarati = assistant.answer("ચોરી માટે સજા શું છે?")
    criminal_gu = glossary.term_for("criminal law", "gu")
    assert criminal_gu and criminal_gu in gujarati.explanation
    assert "(criminal law)" in gujarati.explanation


def test_confirmation_step_fires_in_tamil_and_gujarati(corpus):
    assistant = offline_assistant(corpus)

    tamil = assistant.answer("என் உரிமைகள் என்ன?")
    assert tamil.needs_confirmation
    assert not tamil.citations
    assert _TAMIL.search(tamil.confirmation)

    gujarati = assistant.answer("મારા અધિકારો શું છે?")
    assert gujarati.needs_confirmation
    assert not gujarati.citations
    assert _GUJARATI.search(gujarati.confirmation)


def test_refusal_is_returned_in_the_users_language(corpus):
    assistant = offline_assistant(corpus)
    # An out-of-scope query (no grounded chunk) refuses in the user's language.
    tamil = assistant.answer("சிறந்த பிரியாணி செய்முறை என்ன?")
    assert tamil.refused
    assert _TAMIL.search(tamil.explanation)

    gujarati = assistant.answer("શ્રેષ્ઠ બિરયાની રેસીપી શું છે?")
    assert gujarati.refused
    assert _GUJARATI.search(gujarati.explanation)


def test_confirmation_for_resolves_clarifying_text_per_language():
    assert _TAMIL.search(confirmation_for("right", "ta"))
    assert _GUJARATI.search(confirmation_for("right", "gu"))
    # A query with disambiguating legal content is still not ambiguous.
    assert confirmation_for("theft punishment", "ta") is None


def test_tamil_gold_subset_runs_and_every_case_holds(corpus):
    cases = load_gold_cases(language="ta")
    assert cases, "expected a Tamil gold subset"
    report = run_gold_eval(offline_assistant(corpus), cases)
    assert report.total == len(cases)
    assert report.failures == []
    assert report.passed == report.total


def test_gujarati_gold_subset_runs_and_every_case_holds(corpus):
    cases = load_gold_cases(language="gu")
    assert cases, "expected a Gujarati gold subset"
    report = run_gold_eval(offline_assistant(corpus), cases)
    assert report.total == len(cases)
    assert report.failures == []
    assert report.passed == report.total


def test_glossary_flags_terms_lacking_an_official_translation_source():
    glossary = BilingualGlossary.load()
    # The soft spot for these lower-resource languages: a term whose translation
    # could not be checked against an official central-act source is flagged, not
    # presented as authoritative.
    tamil_unverified = glossary.unverified_terms("ta")
    gujarati_unverified = glossary.unverified_terms("gu")
    assert tamil_unverified, "expected at least one flagged Tamil term"
    assert gujarati_unverified, "expected at least one flagged Gujarati term"
    # English, the Source of Truth, is never flagged.
    assert glossary.unverified_terms("en") == []
