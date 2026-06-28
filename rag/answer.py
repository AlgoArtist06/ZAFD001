"""The grounded answer seam: ``answer(query, mode, language)``.

This is Seam 2 end to end for the English / Citizen Mode path:

    route domain -> hybrid retrieve -> expand to parent + siblings ->
    grounded generate -> verify citations -> structured Grounded Answer

If no retrieved chunk is lexically grounded in the query, or no Citation
survives verification, the seam returns a Refusal ("I do not have a sourced
answer for that") rather than a guess.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from ingestion.models import Chunk
from ingestion.vectorstore import Embedder
from rag.citation import Citation
from rag.domain import route_domains
from rag.expansion import expand
from rag.generation import DeterministicGenerator, Generator, _DISCLAIMER
from rag.retrieval import HybridRetriever
from rag.verifier import verify_citations

REFUSAL_TEXT = "I do not have a sourced answer for that"

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
    disclaimer: str = _DISCLAIMER

    @property
    def text(self) -> str:
        """The structured rendering: explanation, legal basis, next step."""
        parts = [self.explanation]
        if self.legal_basis:
            parts.append(self.legal_basis)
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
    ):
        # No provenance, no answer: only loadable chunks enter the index.
        self._corpus = [c for c in chunks if c.is_loadable()]
        self._retriever = HybridRetriever(self._corpus, embedder=embedder)
        self._generator = generator or DeterministicGenerator()

    def answer(
        self, query: str, mode: str = "citizen", language: str = "en"
    ) -> GroundedAnswer:
        domains = route_domains(query)
        hits = self._retriever.retrieve(query, domains)
        grounded = [h for h in hits if h.keyword_score > 0]
        if not grounded:
            return self._refuse(query, mode, language)

        sections = expand(grounded, self._corpus)
        draft = self._generator.generate(query, sections, mode, language)
        citations = verify_citations(draft.citations, sections)
        if not citations:
            return self._refuse(query, mode, language)

        return GroundedAnswer(
            query=query,
            mode=mode,
            language=language,
            explanation=draft.explanation,
            legal_basis=draft.legal_basis,
            next_step=draft.next_step,
            citations=citations,
            disclaimer=draft.disclaimer,
            refused=False,
        )

    def _refuse(self, query: str, mode: str, language: str) -> GroundedAnswer:
        return GroundedAnswer(
            query=query,
            mode=mode,
            language=language,
            explanation=REFUSAL_TEXT,
            legal_basis="",
            next_step=_REFUSAL_NEXT_STEP,
            citations=[],
            refused=True,
        )


def answer(
    query: str,
    mode: str = "citizen",
    language: str = "en",
    *,
    assistant: LegalAssistant,
) -> GroundedAnswer:
    """Module-level entry mirroring ``assistant.answer(query, mode, language)``."""
    return assistant.answer(query, mode=mode, language=language)
