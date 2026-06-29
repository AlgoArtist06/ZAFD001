"""Seam 2 - the grounded answer seam, English Citizen Mode.

These tests exercise the public ``answer(query, mode, language)`` entry through a
``LegalAssistant`` built over the tiny offline corpus from ``conftest``.
"""
from rag.answer import REFUSAL_TEXT, LegalAssistant, answer


def test_supported_english_citizen_query_returns_grounded_answer(corpus):
    result = LegalAssistant(corpus).answer(
        "What is the punishment for theft of movable property?",
        mode="citizen",
        language="en",
    )
    assert result.refused is False
    assert result.citations
    assert any(c.section_number == "303" for c in result.citations)


def test_module_level_answer_entry_matches_the_method(corpus):
    assistant = LegalAssistant(corpus)
    result = answer("theft of property", "citizen", "en", assistant=assistant)
    assert result.refused is False
    assert result.citations


def test_unsupported_query_is_refused_not_guessed(corpus):
    result = LegalAssistant(corpus).answer(
        "What is the best recipe for biryani?", "citizen", "en"
    )
    assert result.refused is True
    assert result.citations == []
    assert result.explanation == REFUSAL_TEXT


def test_every_citation_is_backed_by_a_provenance_record(corpus):
    result = LegalAssistant(corpus).answer("theft of property", "citizen", "en")
    assert result.citations
    for citation in result.citations:
        assert citation.act_name
        assert citation.act_year
        assert citation.section_number
        assert citation.source_url
        assert citation.verbatim_text


def test_citation_anchor_is_shown_verbatim_in_english(corpus):
    result = LegalAssistant(corpus).answer("theft of property", "citizen", "en")
    citation = result.citations[0]
    # The Citation Anchor quotes the Verbatim Text of the section, in English.
    assert "intending to take dishonestly any movable property" in citation.verbatim_text
    assert citation.verbatim_text in result.text


def test_old_ipc_number_is_normalised_and_grounded_in_current_bns(corpus):
    # A user who only knows the repealed IPC number still gets the BNS answer.
    result = LegalAssistant(corpus).answer(
        "What is the punishment under IPC 420?", "citizen", "en"
    )
    assert result.refused is False
    # Grounded in the current BNS section (318), not the repealed IPC number.
    assert any(c.act_id == "bns" and c.section_number == "318" for c in result.citations)


def test_old_ipc_number_is_annotated_but_never_cited_as_a_source(corpus):
    result = LegalAssistant(corpus).answer(
        "What is the punishment under IPC 420?", "citizen", "en"
    )
    # The former IPC number is annotated as a courtesy...
    assert "formerly IPC 420" in result.text
    # ...but no Citation is ever the repealed IPC number.
    assert all(c.act_id == "bns" for c in result.citations)
    assert all(c.section_number != "420" for c in result.citations)


def test_query_without_an_ipc_reference_carries_no_annotation(corpus):
    result = LegalAssistant(corpus).answer("theft of property", "citizen", "en")
    assert "formerly IPC" not in result.text


def test_answer_uses_the_structured_format(corpus):
    result = LegalAssistant(corpus).answer("theft of property", "citizen", "en")
    text = result.text
    # plain-language explanation, then legal basis with Citation, then next step.
    assert "In plain language" in result.explanation
    assert "Legal basis" in result.legal_basis
    assert result.citations[0].reference in result.legal_basis
    assert "Practical next step" in result.next_step
    assert text.index(result.explanation) < text.index(result.legal_basis) < text.index(
        result.next_step
    )
