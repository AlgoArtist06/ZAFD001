"""The grounded answer seam: ``answer(query, mode, language)``.

This is Seam 2 end to end for the English / Citizen Mode path:

    route domain -> hybrid retrieve -> expand to parent + siblings ->
    grounded generate -> verify citations -> structured Grounded Answer

If no retrieved chunk is lexically grounded in the query, or no Citation
survives verification, the seam returns a Refusal ("I do not have a sourced
answer for that") rather than a guess.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from ingestion.mapping import IpcBnsMapping, MappingEntry, load_ipc_bns_mapping
from ingestion.models import Chunk
from ingestion.vectorstore import Embedder
from rag.citation import Citation
from rag.domain import route_domains
from rag.expansion import expand
from rag.generation import DeterministicGenerator, Generator, _DISCLAIMER
from rag.guardrails import (
    ADVICE_REFUSAL_NEXT_STEP,
    ADVICE_REFUSAL_TEXT,
    HIGH_STAKES_NOTICE,
    RequestKind,
    screen_request,
    soften_advice,
)
from rag.recognition import recognize_ipc
from rag.retrieval import HybridRetriever, expand_query
from rag.verifier import verify_citations

REFUSAL_TEXT = "I do not have a sourced answer for that"

_DEFAULT_MAPPING_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "ipc_bns_mapping.json"
)


def _former_ipc_note(references: Sequence[MappingEntry]) -> str:
    """A courtesy annotation of the repealed IPC numbers a query referenced.

    The note names the former IPC number (e.g. "formerly IPC 420") so a user who
    only knows the old number recognises the answer, while the answer itself
    stays grounded in - and cites only - the current BNS section.
    """
    if not references:
        return ""
    parts = [f"formerly IPC {r.ipc} ({r.label})" for r in references]
    return (
        "Note: " + "; ".join(parts) + ". This is now covered by the current "
        "BNS section cited above; the former IPC number is given only for "
        "recognition and is not itself a source."
    )

# The two answering profiles over the single shared corpus. Citizen is the
# default for new users; Professional is opted into when a Conversation starts.
CITIZEN = "citizen"
PROFESSIONAL = "professional"

_REFUSAL_NEXT_STEP = (
    "For help, consider contacting a lawyer or your nearest Legal Services "
    "Authority (NALSA / DLSA)."
)


@dataclass
class GroundedAnswer:
    query: str
    mode: str
    language: str
    explanation: str
    legal_basis: str
    next_step: str
    citations: List[Citation] = field(default_factory=list)
    refused: bool = False
    high_stakes: bool = False
    high_stakes_notice: str = ""
    former_ipc_note: str = ""
    disclaimer: str = _DISCLAIMER

    @property
    def text(self) -> str:
        """The structured rendering.

        High-Stakes Routing leads with the emergency / legal-aid notice; the
        explanation, legal basis, and next step follow, with the Disclaimer last.
        """
        parts: List[str] = []
        if self.high_stakes_notice:
            parts.append(self.high_stakes_notice)
        parts.append(self.explanation)
        if self.legal_basis:
            parts.append(self.legal_basis)
        if self.former_ipc_note:
            parts.append(self.former_ipc_note)
        if self.next_step:
            parts.append(self.next_step)
        if self.disclaimer:
            parts.append(self.disclaimer)
        return "\n\n".join(parts)


class LegalAssistant:
    """Holds the retrieval index and answers questions over one Source of Truth."""

    def __init__(
        self,
        chunks: Sequence[Chunk],
        embedder: Embedder | None = None,
        generator: Optional[Generator] = None,
        mapping: Optional[IpcBnsMapping] = None,
    ):
        # No provenance, no answer: only loadable chunks enter the index.
        self._corpus = [c for c in chunks if c.is_loadable()]
        self._retriever = HybridRetriever(self._corpus, embedder=embedder)
        self._generator = generator or DeterministicGenerator()
        # The IPC-to-BNS Mapping normalises old IPC numbers on input and
        # annotates them on output; it is never added to the retrieval corpus.
        self._mapping = mapping or load_ipc_bns_mapping(_DEFAULT_MAPPING_PATH)

    def answer(
        self, query: str, mode: str = "citizen", language: str = "en"
    ) -> GroundedAnswer:
        # Input-side scope contract first: refuse advice, flag High-Stakes.
        screen = screen_request(query)
        notice = HIGH_STAKES_NOTICE if screen.high_stakes else ""
        if screen.kind is RequestKind.ADVICE:
            return self._refuse_advice(query, mode, language)

        # Recognise repealed IPC numbers and normalise them to the current BNS
        # section before retrieval; carry the former number forward to annotate.
        recognized = recognize_ipc(query, self._mapping)

        # Mode shapes the query, not the corpus: Citizen Mode expands lay
        # phrasing toward legal concepts, Professional Mode matches exactly.
        retrieval_query = expand_query(recognized.query, mode)
        domains = route_domains(retrieval_query)
        hits = self._retriever.retrieve(retrieval_query, domains)
        grounded = [h for h in hits if h.keyword_score > 0]
        if not grounded:
            return self._refuse(query, mode, language, screen.high_stakes, notice)

        sections = expand(grounded, self._corpus)
        draft = self._generator.generate(query, sections, mode, language)
        citations = verify_citations(draft.citations, sections)
        if not citations:
            return self._refuse(query, mode, language, screen.high_stakes, notice)

        # Output-side check: soften any phrasing that slipped into advice.
        return GroundedAnswer(
            query=query,
            mode=mode,
            language=language,
            explanation=soften_advice(draft.explanation),
            legal_basis=soften_advice(draft.legal_basis),
            next_step=soften_advice(draft.next_step),
            citations=citations,
            disclaimer=draft.disclaimer,
            refused=False,
            high_stakes=screen.high_stakes,
            high_stakes_notice=notice,
            former_ipc_note=_former_ipc_note(recognized.references),
        )

    def start_conversation(self, mode: str = CITIZEN) -> "Conversation":
        """Open a Conversation whose Mode is fixed for its lifetime.

        Default is Citizen Mode; pass ``mode="professional"`` for the
        terse, citation-dense Professional profile. The chosen Mode cannot be
        changed afterwards - switching Mode means a new Conversation.
        """
        return Conversation(self, mode)

    def _refuse(
        self,
        query: str,
        mode: str,
        language: str,
        high_stakes: bool = False,
        notice: str = "",
    ) -> GroundedAnswer:
        return GroundedAnswer(
            query=query,
            mode=mode,
            language=language,
            explanation=REFUSAL_TEXT,
            legal_basis="",
            next_step=_REFUSAL_NEXT_STEP,
            citations=[],
            refused=True,
            high_stakes=high_stakes,
            high_stakes_notice=notice,
        )

    def _refuse_advice(
        self, query: str, mode: str, language: str
    ) -> GroundedAnswer:
        """Refuse a request for Legal Advice and redirect to real help."""
        return GroundedAnswer(
            query=query,
            mode=mode,
            language=language,
            explanation=ADVICE_REFUSAL_TEXT,
            legal_basis="",
            next_step=ADVICE_REFUSAL_NEXT_STEP,
            citations=[],
            refused=True,
        )


class Conversation:
    """A single chat with a Mode locked at start, over one shared assistant.

    The Mode (Citizen or Professional) is chosen when the Conversation opens and
    is read-only thereafter; every turn answers in that Mode against the
    assistant's one corpus, retrieval index, and citation verifier.
    """

    def __init__(self, assistant: LegalAssistant, mode: str = CITIZEN):
        self._assistant = assistant
        self._mode = mode

    @property
    def mode(self) -> str:
        return self._mode

    def ask(self, query: str, language: str = "en") -> GroundedAnswer:
        """Answer a turn in this Conversation's locked Mode."""
        return self._assistant.answer(query, mode=self._mode, language=language)


def answer(
    query: str,
    mode: str = CITIZEN,
    language: str = "en",
    *,
    assistant: LegalAssistant,
) -> GroundedAnswer:
    """Module-level entry mirroring ``assistant.answer(query, mode, language)``."""
    return assistant.answer(query, mode=mode, language=language)
