"""The LLM adapter must survive off-contract model output.

The JSON contract asks for string fields, but a live model sometimes returns a
list of lines or null. `_as_text` normalises those so downstream softening and
rendering never crash on a non-string, and `_draft_from_content` builds a draft
whose text fields are always strings.
"""
from rag.infrastructure.llm import OpenAICompatibleGenerator, _as_text


def test_as_text_coerces_list_null_and_scalar():
    assert _as_text("plain") == "plain"
    assert _as_text(None) == ""
    assert _as_text(["one", "two"]) == "one\ntwo"
    assert _as_text(42) == "42"


def test_draft_from_content_stringifies_a_list_legal_basis():
    gen = OpenAICompatibleGenerator("key", "https://example.test", "model")
    draft = gen._draft_from_content(
        {"explanation": "e", "legal_basis": ["BNS 303", "BNS 304"], "next_step": None},
        sections=[],
    )
    assert draft.legal_basis == "BNS 303\nBNS 304"
    assert draft.next_step == ""
    assert isinstance(draft.explanation, str)
