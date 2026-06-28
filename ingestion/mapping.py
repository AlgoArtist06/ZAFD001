"""IPC-to-BNS Mapping loader.

A structured lookup, deliberately *not* a Source of Truth: it is never chunked,
embedded, or loaded into the vector store. It exists only to recognise a
repealed IPC number on input and annotate the current BNS section on output.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union


@dataclass(frozen=True)
class MappingEntry:
    ipc: str
    bns: str
    label: str


class IpcBnsMapping:
    def __init__(self, entries: Dict[str, MappingEntry]):
        self._entries = entries

    def lookup(self, ipc_section: str) -> Optional[MappingEntry]:
        return self._entries.get(ipc_section.strip().upper())

    def verify(self, official_chart: Dict[str, str]) -> bool:
        """True iff every pinned IPC->BNS pair in the chart is reproduced."""
        return all(
            (entry := self.lookup(ipc)) is not None and entry.bns == bns
            for ipc, bns in official_chart.items()
        )

    def __len__(self) -> int:
        return len(self._entries)


def load_ipc_bns_mapping(path: Union[str, Path]) -> IpcBnsMapping:
    raw = json.loads(Path(path).read_text())
    entries = {
        e["ipc"].upper(): MappingEntry(ipc=e["ipc"].upper(), bns=e["bns"], label=e["label"])
        for e in raw["entries"]
    }
    return IpcBnsMapping(entries)
