"""Citation - a precise pointer to the statutory basis of a claim.

A Citation is built from a :class:`RetrievedSection`, so it is always backed by
a Provenance Record (no provenance, no answer). The Citation Anchor - the
reference plus Verbatim Text - is kept in the original authoritative English even
when the surrounding explanation is in another language.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rag.expansion import RetrievedSection


@dataclass(frozen=True)
class Citation:
    act_id: str
    act_name: str
    act_year: int
    section_number: str
    verbatim_text: str
    source_url: str
    sub_section: Optional[str] = None

    @property
    def reference(self) -> str:
        """The court-traceable reference, e.g. ``Bharatiya Nyaya Sanhita (2023), Section 303``."""
        return f"{self.act_name} ({self.act_year}), Section {self.section_number}"

    @property
    def anchor(self) -> str:
        """The Citation Anchor: reference and Verbatim Text, original English."""
        return f'{self.reference}: "{self.verbatim_text}"'

    @classmethod
    def from_section(cls, section: RetrievedSection) -> "Citation":
        prov = section.provenance
        return cls(
            act_id=section.act_id,
            act_name=prov.act_name,
            act_year=prov.act_year,
            section_number=section.section_number,
            verbatim_text=section.verbatim_text,
            source_url=prov.source_url,
        )
