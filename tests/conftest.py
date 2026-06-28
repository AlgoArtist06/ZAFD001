"""Shared fixtures for the Seam 2 (RAG answer) tests.

The corpus here is a tiny, self-contained slice of the real in-scope acts so the
suite runs fully offline against the deterministic embedder. It spans several
Covered Domains (criminal, consumer, constitutional, IP) so domain routing has
something to route between.
"""
from ingestion.chunker import chunk_act
from ingestion.parser import parse_act

_CRIMINAL = """\
ACT_ID: bns
ACT: Bharatiya Nyaya Sanhita
YEAR: 2023
TYPE: criminal
SOURCE_URL: https://www.indiacode.nic.in/bns
RETRIEVAL_DATE: 2026-06-28
===
Section 303. Theft.
Whoever intending to take dishonestly any movable property out of the
possession of any person commits theft.

Section 318. Cheating.
Whoever by deceiving any person fraudulently or dishonestly induces the person
so deceived to deliver any property to any person is said to cheat.
"""

_CONSUMER = """\
ACT_ID: cpa
ACT: Consumer Protection Act
YEAR: 2019
TYPE: consumer
SOURCE_URL: https://www.indiacode.nic.in/cpa
RETRIEVAL_DATE: 2026-06-28
===
Section 35. Manner in which complaint shall be made.
(1) A complaint in relation to any goods sold or delivered or any service
provided may be filed with a District Commission by the consumer to whom such
goods are sold or delivered or such service provided.
(2) Every complaint filed under sub-section (1) shall be accompanied with such
amount of fee and payable in such manner as may be prescribed.
"""

_CONSTITUTION = """\
ACT_ID: constitution
ACT: Constitution of India (Part III - Fundamental Rights)
YEAR: 1950
TYPE: constitutional
SOURCE_URL: https://www.indiacode.nic.in/constitution
RETRIEVAL_DATE: 2026-06-28
===
Article 21. Protection of life and personal liberty.
No person shall be deprived of his life or personal liberty except according to
procedure established by law.
"""

_IP = """\
ACT_ID: copyright
ACT: Copyright Act
YEAR: 1957
TYPE: ip
SOURCE_URL: https://www.indiacode.nic.in/copyright
RETRIEVAL_DATE: 2026-06-28
===
Section 51. When copyright infringed.
Copyright in a work shall be deemed to be infringed when any person without a
licence granted by the owner of the copyright does anything the exclusive right
to do which is by this Act conferred upon the owner of the copyright.
"""

_SOURCES = [_CRIMINAL, _CONSUMER, _CONSTITUTION, _IP]


def build_corpus():
    chunks = []
    for source in _SOURCES:
        chunks.extend(chunk_act(parse_act(source), token_threshold=30))
    return chunks


import pytest


@pytest.fixture
def corpus():
    """The tiny offline Source of Truth slice, shared across Seam 2 tests."""
    return build_corpus()
