"""LLM-backed multilingual intent extraction at the answer seam.

With the live LLM configured through the config seam, the language-detection and
query-normalization step calls the model: a code-mixed (or non-English) query is
normalized to an English query with the glossary's legal terms injected as hard
constraints, then flows through the unchanged retrieval, grounding,
citation-verification, and guardrail pipeline and is answered in the user's
language. With no key the deterministic normalization serves (covered offline by
``test_multilingual``); these tests pin the keyed path.
"""
import json
import re

from config import load_config
from rag.composition import build_assistant

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_TAMIL = re.compile(r"[஀-௿]")
_GUJARATI = re.compile(r"[઀-૿]")


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _completion(content):
    return _Response({"choices": [{"message": {"content": json.dumps(content)}}]})


def _theft_draft(script_explanation):
    return {
        "explanation": script_explanation,
        "legal_basis": "Bharatiya Nyaya Sanhita (2023), Section 303.",
        "next_step": "Read the cited provision.",
        "citations": [{"act_id": "bns", "section_number": "303"}],
    }


def _is_intent_request(payload):
    """The intent-extraction call carries the glossary hard constraints."""
    user = json.loads(payload["messages"][1]["content"])
    return "term_constraints" in user


def test_code_mixed_query_is_llm_normalized_then_answered_in_hindi(corpus, monkeypatch):
    payloads = []

    def respond(url, json=None, headers=None, timeout=None):
        payloads.append(json)
        if _is_intent_request(json):
            return _completion(
                {"language": "hi", "english_query": "theft of mobile punishment"}
            )
        return _completion(
            _theft_draft(
                "चोरी चल संपत्ति को बेईमानी से लेना है "
                "[Bharatiya Nyaya Sanhita (2023), Section 303]."
            )
        )

    monkeypatch.setattr("httpx.post", respond)
    config = load_config({"LLM_API_KEY": "test-key"})

    result = build_assistant(corpus, config).answer(
        "मेरा mobile चोरी हो गया, सजा क्या है"
    )

    # The LLM intent extractor was called, with the glossary constraints injected.
    intent = next(p for p in payloads if _is_intent_request(p))
    user = json.loads(intent["messages"][1]["content"])
    assert user["query"] == "मेरा mobile चोरी हो गया, सजा क्या है"
    assert user["term_constraints"], "expected glossary hard constraints in the prompt"

    # The normalized English query reached retrieval and the right section is cited.
    assert result.refused is False
    assert result.language == "hi"
    assert any(c.section_number == "303" for c in result.citations)
    # The answer is in the user's language; the Citation Anchor stays English.
    assert _DEVANAGARI.search(result.explanation)
    assert not _DEVANAGARI.search(result.citations[0].anchor)
    assert "Bharatiya Nyaya Sanhita" in result.citations[0].anchor


def _answer_through_llm(corpus, monkeypatch, query, language, script_explanation):
    def respond(url, json=None, headers=None, timeout=None):
        if _is_intent_request(json):
            return _completion(
                {"language": language, "english_query": "theft punishment"}
            )
        return _completion(_theft_draft(script_explanation))

    monkeypatch.setattr("httpx.post", respond)
    config = load_config({"LLM_API_KEY": "test-key"})
    return build_assistant(corpus, config).answer(query)


def test_tamil_query_is_llm_normalized_then_answered_in_tamil(corpus, monkeypatch):
    result = _answer_through_llm(
        corpus,
        monkeypatch,
        "திருட்டுக்கான தண்டனை என்ன?",
        "ta",
        "திருட்டு என்பது அசையும் சொத்தை நேர்மையற்ற முறையில் எடுப்பது "
        "[Bharatiya Nyaya Sanhita (2023), Section 303].",
    )
    assert result.refused is False
    assert result.language == "ta"
    assert any(c.section_number == "303" for c in result.citations)
    assert _TAMIL.search(result.explanation)
    assert not _TAMIL.search(result.citations[0].anchor)


def test_gujarati_query_is_llm_normalized_then_answered_in_gujarati(corpus, monkeypatch):
    result = _answer_through_llm(
        corpus,
        monkeypatch,
        "ચોરી માટે સજા શું છે?",
        "gu",
        "ચોરી એ જંગમ મિલકતને અપ્રામાણિકપણે લેવી છે "
        "[Bharatiya Nyaya Sanhita (2023), Section 303].",
    )
    assert result.refused is False
    assert result.language == "gu"
    assert any(c.section_number == "303" for c in result.citations)
    assert _GUJARATI.search(result.explanation)
    assert not _GUJARATI.search(result.citations[0].anchor)


def test_english_query_skips_the_intent_model_and_keeps_pipeline_offline(
    corpus, monkeypatch
):
    """A pure-English query needs no normalisation, so the only model call is the
    grounded generation - the advice/guardrail screen still runs against the
    original English query before anything reaches retrieval."""
    seen = []

    def respond(url, json=None, headers=None, timeout=None):
        seen.append(json)
        assert not _is_intent_request(json), "English query must skip intent LLM"
        return _completion(
            _theft_draft(
                "Theft is the dishonest taking of movable property "
                "[Bharatiya Nyaya Sanhita (2023), Section 303]."
            )
        )

    monkeypatch.setattr("httpx.post", respond)
    config = load_config({"LLM_API_KEY": "test-key"})
    result = build_assistant(corpus, config).answer(
        "What is the punishment for theft of movable property?"
    )
    assert result.refused is False
    assert result.language == "en"
    assert len(seen) == 1
