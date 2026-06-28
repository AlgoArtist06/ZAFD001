"""Seam 1 structural tests: the bare-act parser."""
from ingestion.models import ActType
from ingestion.parser import parse_act

SAMPLE = """\
ACT_ID: bns
ACT: Bharatiya Nyaya Sanhita
YEAR: 2023
TYPE: criminal
SOURCE_URL: https://www.indiacode.nic.in/bns
RETRIEVAL_DATE: 2026-06-28
===
Section 2. Definitions.
In this Sanhita, unless the context otherwise requires, "act" denotes a series
of acts as a single act.
@AMENDMENT 2024: Substituted by Act 8 of 2024.

Section 318. Cheating.
(1) Whoever, by deceiving any person, fraudulently or dishonestly induces the
person so deceived to deliver any property, is said to cheat.
(2) Whoever cheats shall be punished with imprisonment which may extend to one
year, or with fine, or with both.

Section 319. Cheating by personation.
A person is said to cheat by personation if he cheats by pretending to be some
other person.
"""


def test_parses_act_level_metadata():
    act = parse_act(SAMPLE)
    assert act.act_id == "bns"
    assert act.act_name == "Bharatiya Nyaya Sanhita"
    assert act.act_year == 2023
    assert act.act_type == ActType.CRIMINAL
    assert act.source_url == "https://www.indiacode.nic.in/bns"


def test_computes_a_stable_source_hash():
    assert parse_act(SAMPLE).source_hash == parse_act(SAMPLE).source_hash
    assert len(parse_act(SAMPLE).source_hash) == 64


def test_detects_every_section():
    act = parse_act(SAMPLE)
    assert [s.section_number for s in act.sections] == ["2", "318", "319"]


def test_splits_sub_sections_of_a_large_section():
    act = parse_act(SAMPLE)
    cheating = next(s for s in act.sections if s.section_number == "318")
    assert [ss.label for ss in cheating.sub_sections] == ["1", "2"]
    assert "fraudulently or dishonestly" in cheating.sub_sections[0].text


def test_section_without_sub_sections_has_none():
    act = parse_act(SAMPLE)
    personation = next(s for s in act.sections if s.section_number == "319")
    assert personation.sub_sections == []
    assert "pretending to be some" in personation.full_text


def test_flags_definitions_section():
    act = parse_act(SAMPLE)
    definitions = next(s for s in act.sections if s.section_number == "2")
    assert definitions.is_definition


def test_captures_amendment_history_per_section():
    act = parse_act(SAMPLE)
    definitions = next(s for s in act.sections if s.section_number == "2")
    assert definitions.amendments[0].year == 2024
    cheating = next(s for s in act.sections if s.section_number == "318")
    assert cheating.amendments == []
