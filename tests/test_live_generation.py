import json

from config import load_config
from rag.answer import LegalAssistant


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps(self._payload).encode()


def test_keyed_answer_uses_live_grounded_generation(corpus, monkeypatch):
    requests = []

    def respond(request, timeout):
        requests.append(request)
        draft = {
            "explanation": (
                "Theft is dishonest taking of movable property "
                "[Bharatiya Nyaya Sanhita (2023), Section 303]."
            ),
            "legal_basis": "Bharatiya Nyaya Sanhita (2023), Section 303.",
            "next_step": "Read the cited provision.",
            "citations": [{"act_id": "bns", "section_number": "303"}],
        }
        return _Response(
            {"choices": [{"message": {"content": json.dumps(draft)}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", respond)
    config = load_config({"LLM_API_KEY": "test-key"})

    result = LegalAssistant(corpus, app_config=config).answer(
        "What is theft of movable property?", "citizen", "en"
    )

    assert result.refused is False
    assert result.explanation.startswith("Theft is dishonest taking")
    assert [citation.section_number for citation in result.citations] == ["303"]
    assert requests[0].full_url.endswith("/v1beta/openai/chat/completions")
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert json.loads(requests[0].data)["model"] == "gemini-2.5-flash"


def test_live_answer_rejects_a_citation_that_was_not_retrieved(corpus, monkeypatch):
    def respond(request, timeout):
        draft = {
            "explanation": "A claimed rule [Imaginary Act (2026), Section 999].",
            "legal_basis": "Imaginary Act (2026), Section 999.",
            "next_step": "",
            "citations": [{"act_id": "imaginary", "section_number": "999"}],
        }
        return _Response(
            {"choices": [{"message": {"content": json.dumps(draft)}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", respond)
    result = LegalAssistant(
        corpus, app_config=load_config({"LLM_API_KEY": "test-key"})
    ).answer("What is theft of movable property?", "citizen", "en")

    assert result.refused is True
    assert result.citations == []


def test_advice_request_is_refused_before_live_generation(corpus, monkeypatch):
    def unexpected_request(request, timeout):
        raise AssertionError("advice must not reach the model")

    monkeypatch.setattr("urllib.request.urlopen", unexpected_request)
    result = LegalAssistant(
        corpus, app_config=load_config({"LLM_API_KEY": "test-key"})
    ).answer("Should I sue for theft of my property?", "citizen", "en")

    assert result.refused is True
    assert result.citations == []
