"""Seam 1 tests: IPC-to-BNS Mapping.

Structural: the lookup loads and normalises old numbers. Content-accuracy:
verified against the committed official correspondence chart (ground truth the
agent did not generate from the corpus).
"""
import json
from pathlib import Path

from ingestion.mapping import load_ipc_bns_mapping

DATA = Path(__file__).resolve().parent.parent / "data"
GROUND_TRUTH = json.loads(
    (DATA / "ground_truth" / "ipc_bns_correspondence.json").read_text()
)["pairs"]


def _mapping():
    return load_ipc_bns_mapping(DATA / "ipc_bns_mapping.json")


def test_recognises_an_old_ipc_number_and_returns_current_bns_section():
    entry = _mapping().lookup("420")
    assert entry.bns == "318"
    assert "cheat" in entry.label.lower()


def test_unknown_ipc_number_returns_none():
    assert _mapping().lookup("99999") is None


def test_mapping_matches_official_correspondence_chart():
    mapping = _mapping()
    for ipc, bns in GROUND_TRUTH.items():
        assert mapping.lookup(ipc).bns == bns, f"IPC {ipc} should map to BNS {bns}"
    assert mapping.verify(GROUND_TRUTH)


def test_verify_fails_against_a_tampered_chart():
    assert not _mapping().verify({"420": "999"})


def test_mapping_is_not_a_retrievable_source():
    # The lookup intentionally exposes no chunk/embedding surface.
    mapping = _mapping()
    assert not hasattr(mapping, "as_chunks")
    assert not hasattr(mapping, "to_documents")
