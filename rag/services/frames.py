"""NDJSON frame assembly for a streamed Grounded Answer.

The frontend renders each signal the answer seam decided - the high-stakes
notice, the plain-language explanation, each verbatim-English Citation, the
practical next step, and the disclaimer with its legal-aid pointer - in its own
safe, distinct presentation. The ``meta`` frame leads with the answer's state so
a refusal, an emergency answer, and a normal answer are each rendered
distinguishably. This is presentation only: every decision (what is refused,
what is high-stakes, what is cited) stays in the seam.
"""
from __future__ import annotations

import json
from typing import Iterator

from rag.domain.answer import GroundedAnswer


def frame(payload: dict) -> str:
    """One NDJSON frame: a JSON object on its own line."""
    return json.dumps(payload, ensure_ascii=False) + "\n"


def citation_payload(citation) -> dict:
    """The wire form of one Citation."""
    return {
        "kind": "citation",
        "reference": citation.reference,
        "verbatim": citation.verbatim_text,
        "url": citation.source_url,
    }


def answer_state(result: GroundedAnswer) -> str:
    """The rendering state the ``meta`` frame leads with."""
    if result.refused:
        return "refusal"
    if result.high_stakes:
        return "emergency"
    return "normal"


def answer_frames(result: GroundedAnswer) -> Iterator[str]:
    """A Grounded Answer as NDJSON frames, one structured part per line."""
    meta = {"kind": "meta", "state": answer_state(result), "language": result.language}
    if result.refused:
        # The machine-readable why, so the frontend can say exactly what went
        # wrong: no matching stored document, an advice request, or a draft
        # whose citations all failed verification.
        meta["reason"] = result.refusal_reason
    yield frame(meta)
    if result.high_stakes_notice:
        yield frame({"kind": "highStakesNotice", "text": result.high_stakes_notice})
    yield frame({"kind": "explanation", "text": result.explanation})
    for citation in result.citations:
        yield frame(citation_payload(citation))
    if result.former_ipc_note:
        yield frame({"kind": "note", "text": result.former_ipc_note})
    if result.next_step:
        yield frame({"kind": "nextStep", "text": result.next_step})
    if result.disclaimer:
        yield frame({"kind": "disclaimer", "text": result.disclaimer})
