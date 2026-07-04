"""Startup check that the vector store holds the corpus the runtime expects.

The RAG runtime reads Qdrant but never writes it - loading is the ingestion
pipeline's job. That decoupling means the two can silently diverge: an empty or
stale collection makes retrieval miss and parent expansion degrade with no
error anywhere. This check fails fast at startup instead, naming the fix.
"""
from __future__ import annotations

import logging
import random
from typing import Sequence

from ingestion.models import Chunk

_LOG = logging.getLogger(__name__)

_HINT = (
    "the Qdrant collection does not match the corpus this process serves. "
    "Re-run the ingestion pipeline (python -m ingestion) against this Qdrant "
    "instance, then restart."
)


class CorpusInconsistent(RuntimeError):
    """The vector store's contents do not match the in-process corpus."""


def check_corpus_consistency(
    store,
    corpus: Sequence[Chunk],
    *,
    strict: bool = True,
    sample_size: int = 5,
    rng: random.Random | None = None,
) -> bool:
    """Verify the store holds exactly the loadable corpus, by count and sample.

    ``store`` is a :class:`~ingestion.vectorstore.QdrantVectorStore` (or any
    store with ``count()`` and ``fetch(chunk_ids)``). The count must match the
    loadable corpus, and a random sample of chunks must come back with the same
    ``source_hash`` - so a same-sized collection built from different source
    text still fails. Returns ``True`` when consistent; raises
    :class:`CorpusInconsistent` when ``strict``, else logs a warning and
    returns ``False`` (development mode keeps running for offline work).
    """
    loadable = [chunk for chunk in corpus if chunk.is_loadable()]
    problems = []

    stored_count = store.count()
    if stored_count != len(loadable):
        problems.append(
            f"collection holds {stored_count} chunks, corpus has {len(loadable)}"
        )
    else:
        picker = rng or random.Random()
        sample = picker.sample(loadable, min(sample_size, len(loadable)))
        stored = {c.chunk_id: c for c in store.fetch([c.chunk_id for c in sample])}
        for chunk in sample:
            match = stored.get(chunk.chunk_id)
            if match is None:
                problems.append(f"chunk {chunk.chunk_id} missing from the collection")
            elif match.provenance.source_hash != chunk.provenance.source_hash:
                problems.append(
                    f"chunk {chunk.chunk_id} was ingested from different source text"
                )

    if not problems:
        return True
    message = "; ".join(problems) + " - " + _HINT
    if strict:
        raise CorpusInconsistent(message)
    _LOG.warning("corpus consistency: %s", message)
    return False
