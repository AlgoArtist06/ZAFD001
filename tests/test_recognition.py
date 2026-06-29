"""IPC-number recognition: normalise old IPC references before retrieval.

The IPC-to-BNS Mapping recognises a repealed IPC section number on input and
rewrites the query toward the current BNS section. It is used only to normalise
the input and to carry the former number forward for annotation - never as a
retrieval source.
"""
from ingestion.mapping import load_ipc_bns_mapping
from rag.recognition import recognize_ipc

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _mapping():
    return load_ipc_bns_mapping(DATA / "ipc_bns_mapping.json")


def test_recognises_an_old_ipc_number_and_normalises_toward_bns():
    recognized = recognize_ipc("What is the punishment under IPC 420?", _mapping())

    assert [r.ipc for r in recognized.references] == ["420"]
    assert recognized.references[0].bns == "318"
    # The normalised query carries the current BNS section forward for retrieval.
    assert "318" in recognized.query


def test_query_without_an_ipc_reference_is_left_unchanged():
    recognized = recognize_ipc("What is the punishment for theft?", _mapping())

    assert recognized.references == []
    assert recognized.query == "What is the punishment for theft?"


def test_a_bare_number_without_ipc_is_not_treated_as_an_ipc_reference():
    # "Section 318" is a current BNS number, not a repealed IPC reference.
    recognized = recognize_ipc("What does Section 318 say?", _mapping())

    assert recognized.references == []
