"""Live LLM adapters behind the domain's generation and intent seams.

Both classes speak the OpenAI-compatible ``/chat/completions`` contract, so one
credential and base URL serve Gemini, NVIDIA, or any other compatible provider.
They are the only implementations the product wires behind the generation and
intent seams (ADR 0010); the wiring happens only in :mod:`rag.composition`.

The generator additionally implements the optional streaming seam: ``stream``
consumes the provider's server-sent-event stream and yields the explanation as
it grows, while the model keeps returning the same JSON object contract - so
citation parsing and verification are identical on both paths.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Sequence

import httpx

from rag.domain.citation import Citation
from rag.domain.expansion import RetrievedSection
from rag.domain.generation import DraftAnswer, ExplanationSoFar
from rag.domain.multilingual import (
    ENGLISH,
    BilingualGlossary,
    NormalizedQuery,
    detect_language,
    has_foreign_script,
)

_LOG = logging.getLogger(__name__)

# Generous read timeout: a long grounded answer can take a while to finish, but
# connecting should be fast, and a stalled provider must not hold threads forever.
_TIMEOUT = httpx.Timeout(60.0, connect=5.0)

_GENERATION_SYSTEM_PROMPT = (
    "Return JSON with explanation, legal_basis, next_step, and "
    "citations. Answer only from the supplied sources. End every "
    "legal claim with its exact Act (year), Section citation. "
    "citations must be a list of act_id and section_number pairs "
    "from the supplied sources. If the sources do not answer the "
    "question, return empty strings and an empty citations list. "
    "Do not give personalised legal advice."
)


def _as_text(value) -> str:
    """Coerce a model-returned field to text.

    The JSON contract asks for strings, but a model sometimes returns a list of
    lines (or null) for ``legal_basis`` / ``next_step``. Downstream softening and
    rendering expect a string, so normalise here at the untrusted-output boundary
    rather than crash. ponytail: newline-join is enough; revisit if a field needs
    structured list rendering.
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "\n".join(_as_text(item) for item in value)
    return str(value)


def _post_chat(url: str, api_key: str, payload: dict) -> dict:
    """POST a chat-completions request, with one retry on transient failure.

    Retries once on a connect/transport error or a 5xx; a 4xx is the caller's
    bug and propagates immediately.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    for attempt in (1, 2):
        try:
            response = httpx.post(
                url, json=payload, headers=headers, timeout=_TIMEOUT
            )
            if response.status_code >= 500 and attempt == 1:
                _LOG.warning("llm returned %s, retrying once", response.status_code)
                continue
            response.raise_for_status()
            return response.json()
        except httpx.TransportError as exc:
            if attempt == 2:
                raise
            _LOG.warning("llm unreachable (%s), retrying once", type(exc).__name__)
    raise AssertionError("unreachable")


class _ExplanationScanner:
    """Incrementally extracts the ``"explanation"`` string from partial JSON.

    The streaming response is the same JSON object the non-streaming call
    returns, arriving as a growing prefix. This scanner finds the explanation
    field's opening quote and decodes its value as far as the buffer reaches,
    stopping cleanly before an incomplete escape sequence - so the caller can
    surface the explanation token by token while the rest of the object (the
    citations) is still on the wire.
    """

    _KEY = '"explanation"'

    def __init__(self) -> None:
        self._buffer = ""
        self._value_start: int | None = None

    def feed(self, text: str) -> str | None:
        """Add streamed text; return the decoded explanation so far, if visible."""
        self._buffer += text
        start = self._find_value_start()
        if start is None:
            return None
        decoded, _, _ = self._decode_from(start)
        return decoded

    def _find_value_start(self) -> int | None:
        if self._value_start is not None:
            return self._value_start
        key = self._buffer.find(self._KEY)
        if key < 0:
            return None
        i = key + len(self._KEY)
        while i < len(self._buffer) and self._buffer[i] in " \t\r\n:":
            i += 1
        if i >= len(self._buffer) or self._buffer[i] != '"':
            return None
        self._value_start = i + 1
        return self._value_start

    def _decode_from(self, start: int) -> tuple[str, int, bool]:
        """Decode the string value from ``start``; stop before incomplete escapes.

        Returns (decoded text, index after the last consumed char, closed?).
        """
        out: list[str] = []
        i = start
        buf = self._buffer
        while i < len(buf):
            ch = buf[i]
            if ch == '"':
                return "".join(out), i + 1, True
            if ch != "\\":
                out.append(ch)
                i += 1
                continue
            # An escape sequence: only consume it when it is complete.
            if i + 1 >= len(buf):
                break
            esc = buf[i + 1]
            if esc == "u":
                if i + 6 > len(buf):
                    break
                out.append(chr(int(buf[i + 2 : i + 6], 16)))
                i += 6
            else:
                out.append(
                    {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}.get(esc, esc)
                )
                i += 2
        return "".join(out), i, False


class OpenAICompatibleGenerator:
    """Generate a grounded draft through an OpenAI-compatible endpoint."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model

    def _payload(
        self, query: str, sections: Sequence[RetrievedSection], language: str
    ) -> dict:
        sources = [
            {
                "act_id": section.act_id,
                "act_name": section.provenance.act_name,
                "act_year": section.provenance.act_year,
                "section_number": section.section_number,
                "source_url": section.provenance.source_url,
                "verbatim_text": section.verbatim_text,
            }
            for section in sections
        ]
        return {
            "model": self._model,
            "response_format": {"type": "json_object"},
            # Explicit budget: gateway defaults can be tiny, and a reasoning
            # model spends tokens thinking before the JSON - a "length" cutoff
            # mid-object would otherwise kill every long grounded answer.
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": _GENERATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "language": language,
                            "sources": sources,
                        }
                    ),
                },
            ],
        }

    def _draft_from_content(
        self, content: dict, sections: Sequence[RetrievedSection]
    ) -> DraftAnswer:
        by_section = {
            (section.act_id, section.section_number): section for section in sections
        }
        citations = []
        for item in content.get("citations", []):
            act_id = str(item.get("act_id", ""))
            section_number = str(item.get("section_number", ""))
            section = by_section.get((act_id, section_number))
            citations.append(
                Citation.from_section(section)
                if section
                else Citation(act_id, "", 0, section_number, "", "")
            )
        return DraftAnswer(
            explanation=_as_text(content.get("explanation")),
            legal_basis=_as_text(content.get("legal_basis")),
            next_step=_as_text(content.get("next_step")),
            citations=citations,
        )

    def generate(
        self, query: str, sections: Sequence[RetrievedSection], language: str
    ) -> DraftAnswer:
        completion = _post_chat(
            self._url, self._api_key, self._payload(query, sections, language)
        )
        content = json.loads(completion["choices"][0]["message"]["content"])
        return self._draft_from_content(content, sections)

    async def stream(
        self, query: str, sections: Sequence[RetrievedSection], language: str
    ) -> AsyncIterator[ExplanationSoFar | DraftAnswer]:
        """Stream the draft: cumulative explanations, then the complete draft.

        The provider streams the same JSON object as deltas over SSE; the
        scanner surfaces the growing ``explanation`` field, and the fully
        accumulated body is parsed at the end for the citations - so the
        non-streaming and streaming paths share one output contract.
        """
        payload = self._payload(query, sections, language)
        payload["stream"] = True
        scanner = _ExplanationScanner()
        body = ""
        last_sent = ""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream(
                "POST",
                self._url,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    # Some gateways signal failure as an SSE error event on a
                    # 200 stream; surface it as the provider failure it is.
                    if line.startswith("event:") and "error" in line:
                        raise RuntimeError(f"llm stream error event: {line.strip()}")
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        delta = json.loads(data)["choices"][0]["delta"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    piece = delta.get("content") or ""
                    if not piece:
                        continue
                    body += piece
                    explanation = scanner.feed(piece)
                    if explanation and explanation != last_sent:
                        last_sent = explanation
                        yield ExplanationSoFar(explanation)
        if not body:
            raise RuntimeError("llm stream ended without any content")
        content = json.loads(body)
        yield self._draft_from_content(content, sections)


class LLMIntentExtractor:
    """Normalise a query to English through an OpenAI-compatible LLM endpoint.

    The model detects the language, extracts intent, and rewrites the query into
    English with legal terms preserved and lay complaints mapped to legal concepts,
    handling code-mixing such as Hinglish. The Bilingual Legal Glossary's critical
    terms for the detected language are injected into the prompt as hard
    constraints, so the curated glossary - not the model - still fixes the
    legal terminology. A pure-English query needs no normalisation and never reaches
    the model; a response that omits the rewritten query is an error (ADR 0010) -
    it surfaces to the user as a service failure, never a silent stand-in.
    """

    def __init__(
        self, api_key: str, base_url: str, model: str, glossary: BilingualGlossary
    ):
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._glossary = glossary

    def normalize(self, query: str) -> NormalizedQuery:
        if not has_foreign_script(query):
            # Already English: nothing to normalise, so spend no LLM call.
            return NormalizedQuery(ENGLISH, query)
        language = detect_language(query)
        completion = _post_chat(
            self._url,
            self._api_key,
            {
                "model": self._model,
                "response_format": {"type": "json_object"},
                # Same explicit budget as generation: reasoning tokens count
                # against it, and a "length" cutoff truncates the JSON.
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Normalise a user's legal question for retrieval over an "
                            "English statute corpus. Detect the language, extract the "
                            "intent, and rewrite the question in English. Preserve "
                            "legal terms, map lay complaints to legal concepts, and "
                            "keep any Latin-script words already in English "
                            "(code-mixing). For each listed legal concept you must "
                            "use exactly the supplied English term. Return JSON with "
                            "language (an ISO 639-1 code) and english_query."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "query": query,
                                "term_constraints": self._glossary.constraints_for(
                                    language
                                ),
                            }
                        ),
                    },
                ],
            },
        )
        content = json.loads(completion["choices"][0]["message"]["content"])
        english_query = content.get("english_query")
        if not english_query:
            raise ValueError("intent extraction returned no english_query")
        return NormalizedQuery(
            language=content.get("language") or language,
            english_query=english_query,
        )
