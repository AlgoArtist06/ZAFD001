"""Government scheme fact-card loader.

Schemes are curated structured fact-cards rather than parsed statute. Each card
is turned into a single loadable scheme chunk whose Provenance Record carries
the governing authority and official scheme URL in place of a section number.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import List, Union

from ingestion.models import ActType, AmendmentHistory, Chunk, ProvenanceRecord


def load_scheme_chunks(path: Union[str, Path]) -> List[Chunk]:
    raw = json.loads(Path(path).read_text())
    retrieval_date = date.fromisoformat(raw["retrieval_date"])
    chunks: List[Chunk] = []
    for scheme in raw["schemes"]:
        provenance = ProvenanceRecord(
            act_name=scheme["name"],
            act_year=scheme["year"],
            act_type=ActType.SCHEME,
            source_url=scheme["scheme_url"],
            source_hash=scheme["source_hash"],
            retrieval_date=retrieval_date,
            verbatim_text=scheme["facts"],
            governing_authority=scheme["governing_authority"],
            scheme_url=scheme["scheme_url"],
        )
        chunks.append(
            Chunk(
                chunk_id=f"scheme-{scheme['id']}",
                act_id=scheme["id"],
                text=scheme["facts"],
                provenance=provenance,
                amendment_history=AmendmentHistory(none_recorded=True),
            )
        )
    return chunks
