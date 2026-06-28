"""IPC-number recognition - input normalisation via the IPC-to-BNS Mapping.

A user who only knows the repealed IPC section number should still reach the
current BNS section. This module recognises an IPC reference in the query and
rewrites it toward the current BNS section before retrieval, while carrying the
former IPC number forward so the answer can annotate it.

The IPC-to-BNS Mapping is consulted only here (for input normalisation) and at
annotation time. It is never chunked, embedded, or otherwise used as a retrieval
source: recognition only rewrites the query string handed to the retriever.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from ingestion.mapping import IpcBnsMapping, MappingEntry

# Recognition is gated on the literal token "IPC": a bare number like
# "Section 318" is a current BNS reference, not a repealed IPC one, so it must
# not be rewritten. A section number may carry a letter suffix (e.g. 304B, 120B).
_IPC_TOKEN_RE = re.compile(r"\bipc\b", re.IGNORECASE)
_SECTION_RE = re.compile(r"\b(\d{1,3}[A-Z]?)\b")


@dataclass(frozen=True)
class RecognizedQuery:
    """A query after IPC normalisation, with any references it carried forward."""

    query: str
    references: List[MappingEntry] = field(default_factory=list)


def recognize_ipc(query: str, mapping: IpcBnsMapping) -> RecognizedQuery:
    """Recognise repealed IPC numbers and normalise the query toward BNS.

    Returns the original query untouched when no IPC reference is present. When
    the query mentions IPC and a recognised section number, the current BNS
    section number and its label are appended so keyword retrieval reaches the
    BNS section, and the matched mapping entries are returned for annotation.
    """
    if not _IPC_TOKEN_RE.search(query):
        return RecognizedQuery(query=query)

    references: List[MappingEntry] = []
    additions: List[str] = []
    for token in _SECTION_RE.findall(query):
        entry = mapping.lookup(token)
        if entry is None or any(r.ipc == entry.ipc for r in references):
            continue
        references.append(entry)
        additions.append(f"{entry.bns} {entry.label}")

    if not references:
        return RecognizedQuery(query=query)
    return RecognizedQuery(query=query + " " + " ".join(additions), references=references)
