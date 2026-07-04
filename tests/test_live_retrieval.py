"""Phase-0 smoke test for an explicitly configured live Qdrant instance."""
import os

import pytest

from config import load_config
from ingestion.models import ActType
from ingestion.pipeline import default_config, run_ingestion
from rag.domain.expansion import expand
from rag.domain.retrieval import HybridRetriever

pytestmark = pytest.mark.skipif(
    not os.getenv("QDRANT_URL"), reason="QDRANT_URL is not configured"
)


def test_known_queries_return_the_correct_sections_from_live_qdrant():
    settings = load_config()
    result = run_ingestion(default_config(), settings)
    retriever = HybridRetriever(result.chunks, app_config=settings)

    cheating = retriever.retrieve(
        "deceived into dishonestly delivering property", [ActType.CRIMINAL]
    )
    rights = retriever.retrieve(
        "protection of life and personal liberty", [ActType.CONSTITUTIONAL]
    )

    assert expand(cheating, result.chunks)[0].section_number == "318"
    assert expand(rights, result.chunks)[0].section_number == "21"
