import json

from config import load_config
from rag.composition import build_assistant


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


def test_keyed_answer_uses_live_grounded_generation(corpus, monkeypatch):
    requests = []

    def respond(url, json=None, headers=None, timeout=None):
        requests.append((url, json, headers))
        return _completion(
            {
                "explanation": (
                    "Theft is dishonest taking of movable property "
                    "[Bharatiya Nyaya Sanhita (2023), Section 303]."
                ),
                "legal_basis": "Bharatiya Nyaya Sanhita (2023), Section 303.",
                "next_step": "Read the cited provision.",
                "citations": [{"act_id": "bns", "section_number": "303"}],
            }
        )

    monkeypatch.setattr("httpx.post", respond)
    config = load_config({"LLM_API_KEY": "test-key"})

    result = build_assistant(corpus, config).answer(
        "What is theft of movable property?", "en"
    )

    assert result.refused is False
    assert result.explanation.startswith("Theft is dishonest taking")
    assert [citation.section_number for citation in result.citations] == ["303"]
    url, payload, headers = requests[0]
    assert url.endswith("/v1beta/openai/chat/completions")
    assert headers["Authorization"] == "Bearer test-key"
    assert payload["model"] == "gemini-2.5-flash"


def test_live_answer_rejects_a_citation_that_was_not_retrieved(corpus, monkeypatch):
    def respond(url, json=None, headers=None, timeout=None):
        return _completion(
            {
                "explanation": "A claimed rule [Imaginary Act (2026), Section 999].",
                "legal_basis": "Imaginary Act (2026), Section 999.",
                "next_step": "",
                "citations": [{"act_id": "imaginary", "section_number": "999"}],
            }
        )

    monkeypatch.setattr("httpx.post", respond)
    result = build_assistant(
        corpus, load_config({"LLM_API_KEY": "test-key"})
    ).answer("What is theft of movable property?", "en")

    assert result.refused is True
    assert result.citations == []


def test_advice_request_is_refused_before_live_generation(corpus, monkeypatch):
    def unexpected_request(url, json=None, headers=None, timeout=None):
        raise AssertionError("advice must not reach the model")

    monkeypatch.setattr("httpx.post", unexpected_request)
    result = build_assistant(
        corpus, load_config({"LLM_API_KEY": "test-key"})
    ).answer("Should I sue for theft of my property?", "en")

    assert result.refused is True
    assert result.citations == []
