"""The shared answer-streaming helper behind the HTTP demo surfaces."""
from rag.answer import LegalAssistant
from rag.api import stream_answer


def test_stream_yields_progressive_chunks(corpus):
    assistant = LegalAssistant(corpus)
    parts = list(stream_answer(assistant, "theft of property", "citizen", "en"))
    assert len(parts) > 1
    joined = "".join(parts)
    assert "Legal basis" in joined
    assert "Practical next step" in joined
