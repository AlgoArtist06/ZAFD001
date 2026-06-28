"""The Seam 2 gold eval harness.

The gold evaluation set is the test suite at this seam: each gold case is
hand-verified against the bare-act text and asserts either that the correct
section is cited or that a Refusal fires for an out-of-scope / advice-seeking
input. The harness runs the cases through the real :func:`answer` path and
reports which held, so it can be re-run whenever the model, prompts, or chunking
change. Cases carry a ``language`` so the same harness serves the per-language
subsets; issue 02 populates only the English subset.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from rag.answer import LegalAssistant

ENGLISH = "en"

_GOLD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "eval", "seam2_gold.json"
)


@dataclass(frozen=True)
class GoldCase:
    """One hand-verified expectation about the answer seam."""

    id: str
    query: str
    language: str = ENGLISH
    mode: str = "citizen"
    expected_act_id: Optional[str] = None
    expected_section: Optional[str] = None
    expect_refusal: bool = False
    expect_high_stakes: bool = False


@dataclass
class CaseResult:
    case: GoldCase
    passed: bool
    detail: str


@dataclass
class EvalReport:
    """The outcome of running the gold cases: per-case results and a tally."""

    results: List[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failures(self) -> List[GoldCase]:
        return [r.case for r in self.results if not r.passed]


def load_gold_cases(
    language: Optional[str] = None,
    path: str = _GOLD_PATH,
    mode: Optional[str] = None,
) -> List[GoldCase]:
    """Load the gold cases, optionally filtered to one language and/or Mode."""
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    cases = [
        GoldCase(
            id=entry["id"],
            query=entry["query"],
            language=entry.get("language", ENGLISH),
            mode=entry.get("mode", "citizen"),
            expected_act_id=entry.get("expected_act_id"),
            expected_section=entry.get("expected_section"),
            expect_refusal=entry.get("expect_refusal", False),
            expect_high_stakes=entry.get("expect_high_stakes", False),
        )
        for entry in raw["cases"]
    ]
    if language is not None:
        cases = [c for c in cases if c.language == language]
    if mode is not None:
        cases = [c for c in cases if c.mode == mode]
    return cases


def _evaluate(case: GoldCase, assistant: LegalAssistant) -> CaseResult:
    result = assistant.answer(case.query, mode=case.mode, language=case.language)

    if case.expect_high_stakes:
        leads = result.high_stakes and result.text.index("112") < result.text.index(
            result.explanation
        )
        detail = (
            "led with emergency contacts as expected"
            if leads
            else "expected High-Stakes Routing leading with emergency contacts"
        )
        return CaseResult(case=case, passed=leads, detail=detail)

    if case.expect_refusal:
        passed = result.refused
        detail = "refused as expected" if passed else "expected a Refusal, got an answer"
        return CaseResult(case=case, passed=passed, detail=detail)

    if result.refused:
        return CaseResult(
            case=case, passed=False, detail="expected a cited answer, got a Refusal"
        )

    cited = any(
        c.section_number == case.expected_section
        and (case.expected_act_id is None or c.act_id == case.expected_act_id)
        for c in result.citations
    )
    detail = (
        f"cited section {case.expected_section}"
        if cited
        else f"expected section {case.expected_section}, got "
        f"{[(c.act_id, c.section_number) for c in result.citations]}"
    )
    return CaseResult(case=case, passed=cited, detail=detail)


def run_gold_eval(
    assistant: LegalAssistant, cases: Sequence[GoldCase]
) -> EvalReport:
    """Run every gold case through the answer seam and tally the outcomes."""
    return EvalReport(results=[_evaluate(case, assistant) for case in cases])
