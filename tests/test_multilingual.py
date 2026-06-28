"""The multilingual answering layer, proven out with Hindi.

These tests pin the behaviour the issue asks for: detect the user's language,
extract intent into an English query (legal terms preserved, code-mixing handled),
retrieve and reason over the single English Source of Truth, then answer back in
Hindi. The Bilingual Legal Glossary constrains the Hindi terminology; the Citation
Anchor stays verbatim English; critical terms appear in Hindi with the English term
inline in brackets; and a Confirmation Step fires for ambiguous Citizen-mode
queries.
"""
import re

from rag.answer import LegalAssistant
from rag.eval import load_gold_cases, run_gold_eval
from rag.multilingual import (
    BilingualGlossary,
    confirmation_for,
    detect_language,
)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def test_detect_language_distinguishes_hindi_from_english():
    assert detect_language("चोरी की सजा क्या है?") == "hi"
    assert detect_language("What is the punishment for theft?") == "en"


def test_intent_extraction_normalises_hindi_to_english_preserving_legal_terms():
    glossary = BilingualGlossary.load()
    english = glossary.to_english("चोरी की सजा क्या है?")
    stems = english.lower().split()
    assert "theft" in stems
    assert "punishment" in stems
    # No Devanagari survives normalisation: retrieval runs over English only.
    assert not _DEVANAGARI.search(english)


def test_intent_extraction_handles_code_mixing_keeping_latin_terms():
    """Hinglish: a Devanagari query that carries an English word inline keeps the
    English word and still maps the Hindi legal terms."""
    glossary = BilingualGlossary.load()
    english = glossary.to_english("मेरा mobile चोरी हो गया, सजा क्या है")
    lowered = english.lower()
    assert "mobile" in lowered
    assert "theft" in lowered
    assert "punishment" in lowered


def test_hindi_query_retrieves_over_english_corpus_and_answers_in_hindi(corpus):
    assistant = LegalAssistant(corpus)
    result = assistant.answer("चोरी की सजा क्या है?")
    assert not result.refused
    assert result.language == "hi"
    # Reasoning ran over the English corpus: the correct BNS section is cited.
    assert any(c.section_number == "303" for c in result.citations)
    # The answer itself is generated in Hindi.
    assert _DEVANAGARI.search(result.explanation)


def test_citation_anchor_stays_verbatim_english_in_a_hindi_answer(corpus):
    assistant = LegalAssistant(corpus)
    result = assistant.answer("चोरी की सजा क्या है?")
    anchor = result.citations[0].anchor
    # The Citation Anchor (reference + Verbatim Text) is original English only.
    assert not _DEVANAGARI.search(anchor)
    assert "Bharatiya Nyaya Sanhita" in anchor


def test_glossary_constrains_hindi_terminology_with_english_in_brackets(corpus):
    """The Bilingual Legal Glossary supplies the Hindi term, and the critical term
    is rendered in Hindi with the English term inline in brackets."""
    glossary = BilingualGlossary.load()
    criminal_hi = glossary.hindi_for("criminal law")
    assert criminal_hi  # the glossary is the source of the Hindi term
    result = LegalAssistant(corpus).answer("चोरी की सजा क्या है?")
    assert criminal_hi in result.explanation
    assert "(criminal law)" in result.explanation


def test_confirmation_step_fires_for_ambiguous_citizen_query(corpus):
    assistant = LegalAssistant(corpus)
    result = assistant.answer("मेरे अधिकार क्या हैं?")
    assert result.needs_confirmation
    assert not result.citations
    # The clarifying check is posed in the user's language.
    assert _DEVANAGARI.search(result.confirmation)


def test_confirmation_step_does_not_fire_in_professional_mode(corpus):
    assistant = LegalAssistant(corpus)
    convo = assistant.start_conversation(mode="professional")
    result = convo.ask("मेरे अधिकार क्या हैं?")
    assert not result.needs_confirmation


def test_confirmation_for_only_triggers_on_ambiguous_only_queries():
    assert confirmation_for("right", "en") is not None
    # A query with disambiguating legal content is not ambiguous.
    assert confirmation_for("life personal liberty", "en") is None
    assert confirmation_for("theft punishment", "en") is None


def test_hindi_gold_subset_runs_and_every_case_holds(corpus):
    cases = load_gold_cases(language="hi")
    assert cases, "expected a Hindi gold subset"
    report = run_gold_eval(LegalAssistant(corpus), cases)
    assert report.total == len(cases)
    assert report.failures == []
    assert report.passed == report.total
