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

# Compact slices of the domains added in the source expansion, so the whole
# gold set resolves against this offline fixture exactly as it does against the
# real corpus. Each carries the section its gold case cites plus one sibling.
_CYBER = """\
ACT_ID: it_act
ACT: Information Technology Act
YEAR: 2000
TYPE: cyber
SOURCE_URL: https://www.indiacode.nic.in/it_act
RETRIEVAL_DATE: 2026-07-02
===
Section 66C. Punishment for identity theft.
Whoever, fraudulently or dishonestly make use of the electronic signature,
password or any other unique identification feature of any other person, shall
be punished with imprisonment which may extend to three years and shall also be
liable to fine.

Section 66D. Punishment for cheating by personation by using computer resource.
Whoever, by means of any communication device or computer resource cheats by
personation, shall be punished with imprisonment which may extend to three years
and shall also be liable to fine.
"""

_TRANSPORT = """\
ACT_ID: mv_act
ACT: Motor Vehicles Act
YEAR: 1988
TYPE: transport
SOURCE_URL: https://www.indiacode.nic.in/mv_act
RETRIEVAL_DATE: 2026-07-02
===
Section 185. Driving by a drunken person.
Whoever, while driving a motor vehicle, has alcohol exceeding the prescribed
limit in his blood, or is under the influence of a drug, shall be punishable for
the first offence with imprisonment which may extend to six months, or with
fine, or with both.

Section 3. Necessity for driving licence.
No person shall drive a motor vehicle in any public place unless he holds an
effective driving licence issued to him authorising him to drive the vehicle.
"""

_GOVERNANCE = """\
ACT_ID: rti_act
ACT: Right to Information Act
YEAR: 2005
TYPE: governance
SOURCE_URL: https://www.indiacode.nic.in/rti_act
RETRIEVAL_DATE: 2026-07-02
===
Section 6. Request for obtaining information.
A person who desires to obtain any information under this Act shall make a
request in writing or through electronic means, accompanying the prescribed fee,
to the Public Information Officer, specifying the particulars of the information
sought by him.

Section 19. Appeal.
Any person aggrieved by a decision of the Public Information Officer may within
thirty days prefer an appeal to an officer senior in rank to the Public
Information Officer in each public authority.
"""

_PROTECTION = """\
ACT_ID: dv_act
ACT: Protection of Women from Domestic Violence Act
YEAR: 2005
TYPE: protection
SOURCE_URL: https://www.indiacode.nic.in/dv_act
RETRIEVAL_DATE: 2026-07-02
===
Section 18. Protection orders.
The Magistrate may, on being prima facie satisfied that domestic violence has
taken place, pass a protection order in favour of the aggrieved person and
prohibit the respondent from committing any act of domestic violence.

Section 20. Monetary reliefs.
The Magistrate may direct the respondent to pay monetary relief to meet the
expenses incurred and losses suffered by the aggrieved person as a result of the
domestic violence.
"""

_WORKPLACE = """\
ACT_ID: posh_act
ACT: Sexual Harassment of Women at Workplace Act
YEAR: 2013
TYPE: protection
SOURCE_URL: https://www.indiacode.nic.in/posh_act
RETRIEVAL_DATE: 2026-07-02
===
Section 9. Complaint of sexual harassment.
Any aggrieved woman may make in writing a complaint of sexual harassment at
workplace to the Internal Committee within a period of three months from the
date of incident.

Section 4. Constitution of Internal Complaints Committee.
Every employer of a workplace shall, by an order in writing, constitute a
Committee to be known as the Internal Complaints Committee.
"""

_SOURCES = [
    _CRIMINAL,
    _CONSUMER,
    _CONSTITUTION,
    _IP,
    _CYBER,
    _TRANSPORT,
    _GOVERNANCE,
    _PROTECTION,
    _WORKPLACE,
]


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
