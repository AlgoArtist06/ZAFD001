"""The grounded answer seam: ``answer(query, language)``.

This is Seam 2 end to end for the English path:

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

from config import AppConfig
from ingestion.mapping import IpcBnsMapping, MappingEntry, load_ipc_bns_mapping
from ingestion.models import Chunk
from ingestion.vectorstore import Embedder, VectorStore
from rag.domain.citation import Citation
from rag.domain.routing import route_domains
from rag.domain.expansion import RetrievedSection, expand
from rag.domain.followup import rewrite_followup
from rag.domain.generation import DraftAnswer, Generator, _DISCLAIMER
from rag.domain.guardrails import (
    ADVICE_REFUSAL_NEXT_STEP,
    ADVICE_REFUSAL_TEXT,
    HIGH_STAKES_NOTICE,
    RequestKind,
    screen_request,
    soften_advice,
)
from rag.domain.multilingual import (
    GUJARATI,
    HINDI,
    TAMIL,
    BilingualGlossary,
    IntentExtractor,
    confirmation_for,
)
from rag.domain.recognition import recognize_ipc
from rag.domain.retrieval import HybridRetriever, expand_query
from rag.domain.verifier import verify_citations

REFUSAL_TEXT = "I do not have a sourced answer for that"

# Refusal copy per Supported Language, so a user is refused in their own language.
_REFUSAL_TEXT_BY_LANGUAGE = {
    HINDI: "मेरे पास इसका कोई स्रोत-समर्थित उत्तर नहीं है",
    TAMIL: "அந்தக் கேள்விக்கு என்னிடம் ஆதாரப்பூர்வமான பதில் இல்லை",
    GUJARATI: "મારી પાસે તેનો કોઈ સ્રોત-આધારિત જવાબ નથી",
}

_DEFAULT_MAPPING_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ipc_bns_mapping.json"
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

_REFUSAL_NEXT_STEP = (
    "For help, consider contacting a lawyer or your nearest Legal Services "
    "Authority (NALSA / DLSA)."
)

_REFUSAL_NEXT_STEP_BY_LANGUAGE = {
    HINDI: (
        "सहायता के लिए किसी वकील या अपने निकटतम विधिक सेवा प्राधिकरण "
        "(NALSA / DLSA) से संपर्क करने पर विचार करें।"
    ),
    TAMIL: (
        "உதவிக்கு, ஒரு வழக்கறிஞரை அல்லது உங்கள் அருகிலுள்ள சட்ட சேவை ஆணையத்தை "
        "(NALSA / DLSA) தொடர்பு கொள்ளவும்."
    ),
    GUJARATI: (
        "મદદ માટે, વકીલનો અથવા તમારી નજીકના કાનૂની સેવા સત્તામંડળ "
        "(NALSA / DLSA) નો સંપર્ક કરવાનું વિચારો."
    ),
}


@dataclass
class GroundedAnswer:
    query: str
    language: str
    explanation: str
    legal_basis: str
    next_step: str
    citations: List[Citation] = field(default_factory=list)
    refused: bool = False
    # Why the answer was refused, for the frontend to say exactly what went
    # wrong: "no_match" (query matched no stored document), "advice" (a request
    # for personalised Legal Advice), or "citations_unverified" (the model's
    # draft survived no citation check). Empty on a non-refusal.
    refusal_reason: str = ""
    high_stakes: bool = False
    high_stakes_notice: str = ""
    former_ipc_note: str = ""
    disclaimer: str = _DISCLAIMER
    needs_confirmation: bool = False
    confirmation: str = ""

    @property
    def text(self) -> str:
        """The structured rendering.

        A Confirmation Step short-circuits to just the clarifying question. Otherwise
        High-Stakes Routing leads with the emergency / legal-aid notice; the
        explanation, legal basis, and next step follow, with the Disclaimer last.
        """
        if self.needs_confirmation:
            return self.confirmation
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


@dataclass
class PreparedQuery:
    """A query that passed every pre-generation gate, ready for the generator.

    Carries what generation and finalization need: the English retrieval query,
    the expanded sections, and the screening outcome (High-Stakes flag and
    notice) that must survive onto the final answer.
    """

    query: str
    language: str
    english_query: str
    sections: List[RetrievedSection]
    high_stakes: bool
    notice: str
    references: List[MappingEntry] = field(default_factory=list)


class LegalAssistant:
    """Holds the retrieval index and answers questions over one Source of Truth."""

    def __init__(
        self,
        chunks: Sequence[Chunk],
        *,
        embedder: Embedder,
        generator: Generator,
        intent_extractor: IntentExtractor,
        mapping: Optional[IpcBnsMapping] = None,
        glossary: Optional[BilingualGlossary] = None,
        app_config: Optional[AppConfig] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        # The three answering seams are REQUIRED: there is no offline default to
        # fall back to (ADR 0010). Production wiring lives in rag.composition;
        # tests inject their own doubles explicitly.
        # No provenance, no answer: only loadable chunks enter the index.
        self._corpus = [c for c in chunks if c.is_loadable()]
        self._retriever = HybridRetriever(
            self._corpus,
            embedder=embedder,
            vector_store=vector_store,
            app_config=app_config,
        )
        # The Bilingual Legal Glossary normalises an incoming query to English and
        # constrains the terminology of the answer; the same instance backs the
        # generator so both directions agree on terms.
        self._glossary = glossary or BilingualGlossary.load()
        self._intent = intent_extractor
        self._generator = generator
        # The IPC-to-BNS Mapping normalises old IPC numbers on input and
        # annotates them on output; it is never added to the retrieval corpus.
        self._mapping = mapping or load_ipc_bns_mapping(_DEFAULT_MAPPING_PATH)

    def prepare(
        self, query: str, language: str = "en"
    ) -> "PreparedQuery | GroundedAnswer":
        """Everything before generation: normalize, screen, retrieve, gate, expand.

        Returns a complete :class:`GroundedAnswer` when the pipeline decides
        without generating (a Confirmation Step, an advice Refusal, or an
        ungrounded Refusal); otherwise a :class:`PreparedQuery` carrying the
        retrieved sections for the generator. Splitting here is what lets the
        streaming path run generation incrementally while every decision stays
        in this seam.
        """
        # Multilingual layer: detect the user's language and extract the query's
        # intent into English (legal terms preserved, code-mixing handled) so every
        # downstream step - screening, recognition, retrieval, reasoning - runs over
        # the single English Source of Truth. The answer is rendered back in the
        # detected language; an explicit non-English language is honoured when the
        # query carries no script of its own.
        normalized = self._intent.normalize(query)
        out_language = normalized.language if normalized.language != "en" else language
        english_query = normalized.english_query

        # Confirmation Step: an ambiguous query is clarified before answering,
        # never guessed at.
        confirmation = confirmation_for(english_query, out_language)
        if confirmation is not None:
            return self._confirm(query, out_language, confirmation)

        # Input-side scope contract first: refuse advice, flag High-Stakes.
        screen = screen_request(english_query)
        notice = HIGH_STAKES_NOTICE if screen.high_stakes else ""
        if screen.kind is RequestKind.ADVICE:
            return self._refuse_advice(query, out_language)

        # Recognise repealed IPC numbers and normalise them to the current BNS
        # section before retrieval; carry the former number forward to annotate.
        recognized = recognize_ipc(english_query, self._mapping)

        # Expand lay phrasing toward legal concepts before retrieval, so a
        # colloquial complaint still reaches the matching statutory section.
        retrieval_query = expand_query(recognized.query)
        domains = route_domains(retrieval_query)
        hits = self._retriever.retrieve(retrieval_query, domains)
        # The cheap support gate: a hit with zero lexical overlap is not
        # grounded at all. A weak incidental overlap can still pass here; the
        # model then judges relevance itself (an empty draft becomes a
        # "no_match" Refusal in finalize), so garbage never becomes an answer.
        grounded = [h for h in hits if h.keyword_score > 0]
        if not grounded:
            return self._refuse(query, out_language, screen.high_stakes, notice)

        return PreparedQuery(
            query=query,
            language=out_language,
            english_query=english_query,
            sections=expand(grounded, self._corpus),
            high_stakes=screen.high_stakes,
            notice=notice,
            references=list(recognized.references),
        )

    def finalize(
        self, prepared: "PreparedQuery", draft: "DraftAnswer"
    ) -> GroundedAnswer:
        """Everything after generation: verify citations, soften, assemble.

        The anti-hallucination backstop lives here: a draft whose every citation
        fails verification becomes a Refusal, never a guess. The reason names
        what happened - an empty draft is the model saying the retrieved
        sources do not answer the question ("no_match"); a substantive draft
        stripped of every citation is "citations_unverified".
        """
        citations = verify_citations(draft.citations, prepared.sections)
        if not citations:
            empty = not draft.explanation.strip() and not draft.citations
            return self._refuse(
                prepared.query,
                prepared.language,
                prepared.high_stakes,
                prepared.notice,
                reason="no_match" if empty else "citations_unverified",
            )

        # Output-side check: soften any phrasing that slipped into advice.
        return GroundedAnswer(
            query=prepared.query,
            language=prepared.language,
            explanation=soften_advice(draft.explanation),
            legal_basis=soften_advice(draft.legal_basis),
            next_step=soften_advice(draft.next_step),
            citations=citations,
            disclaimer=draft.disclaimer,
            refused=False,
            high_stakes=prepared.high_stakes,
            high_stakes_notice=prepared.notice,
            former_ipc_note=_former_ipc_note(prepared.references),
        )

    def answer(
        self, query: str, language: str = "en"
    ) -> GroundedAnswer:
        prepared = self.prepare(query, language)
        if isinstance(prepared, GroundedAnswer):
            return prepared
        draft = self._generator.generate(
            prepared.english_query, prepared.sections, prepared.language
        )
        return self.finalize(prepared, draft)

    @property
    def generator(self) -> Generator:
        """The generation seam, exposed so the streaming service can probe it."""
        return self._generator

    def start_conversation(self) -> "Conversation":
        """Open a Conversation that remembers context across its turns."""
        return Conversation(self)

    def _refuse(
        self,
        query: str,
        language: str,
        high_stakes: bool = False,
        notice: str = "",
        reason: str = "no_match",
    ) -> GroundedAnswer:
        return GroundedAnswer(
            query=query,
            language=language,
            explanation=_REFUSAL_TEXT_BY_LANGUAGE.get(language, REFUSAL_TEXT),
            legal_basis="",
            next_step=_REFUSAL_NEXT_STEP_BY_LANGUAGE.get(language, _REFUSAL_NEXT_STEP),
            citations=[],
            refused=True,
            refusal_reason=reason,
            high_stakes=high_stakes,
            high_stakes_notice=notice,
        )

    def _confirm(
        self, query: str, language: str, confirmation: str
    ) -> GroundedAnswer:
        """Pose a Confirmation Step instead of answering an ambiguous query."""
        return GroundedAnswer(
            query=query,
            language=language,
            explanation=confirmation,
            legal_basis="",
            next_step="",
            citations=[],
            refused=False,
            needs_confirmation=True,
            confirmation=confirmation,
            disclaimer="",
        )

    def _refuse_advice(
        self, query: str, language: str
    ) -> GroundedAnswer:
        """Refuse a request for Legal Advice and redirect to real help."""
        return GroundedAnswer(
            query=query,
            language=language,
            explanation=ADVICE_REFUSAL_TEXT,
            legal_basis="",
            next_step=ADVICE_REFUSAL_NEXT_STEP,
            citations=[],
            refused=True,
            refusal_reason="advice",
        )


class Conversation:
    """A single chat over one shared assistant, remembering context across turns.

    Context is remembered across turns *within* this Conversation only: a
    dependent follow-up ("what is the punishment for it?") is rewritten into a
    standalone query against the bounded recent turns before retrieval, then runs
    the same full pipeline as any other turn. The history lives on the instance,
    so a fresh Conversation - or the stateless :meth:`LegalAssistant.answer` -
    starts with no context and nothing leaks between Conversations.
    """

    # How many recent standalone turns are kept as context for rewriting a
    # follow-up. Bounded so context stays recent and the query cannot grow without
    # limit over a long Conversation.
    _CONTEXT_TURNS = 4

    def __init__(self, assistant: LegalAssistant):
        self._assistant = assistant
        self._recent: List[str] = []

    def ask(self, query: str, language: str = "en") -> GroundedAnswer:
        """Answer a turn in this Conversation.

        A dependent follow-up is first rewritten into a self-contained query using
        the bounded recent context; the resolved query then passes through the
        full pipeline. The resolved query is remembered so later follow-ups can
        build on it in turn.
        """
        resolved = rewrite_followup(query, self._recent)
        self._recent = (self._recent + [resolved])[-self._CONTEXT_TURNS :]
        result = self._assistant.answer(resolved, language=language)
        # Keep the user's actual words on the returned answer, not the rewrite.
        result.query = query
        return result


def answer(
    query: str,
    language: str = "en",
    *,
    assistant: LegalAssistant,
) -> GroundedAnswer:
    """Module-level entry mirroring ``assistant.answer(query, language)``."""
    return assistant.answer(query, language=language)
