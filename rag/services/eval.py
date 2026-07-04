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
from typing import Dict, List, Optional, Sequence

from rag.domain.answer import LegalAssistant

ENGLISH = "en"

# The four Supported Languages, in the order the final eval pass reports them.
SUPPORTED_LANGUAGES = ("en", "hi", "ta", "gu")

# The accuracy a per-language gold subset must clear in the final pass. The
# curated subsets are hand-verified to hold completely, so the bar is total
# correctness; a single regression in any language fails the pass.
ACCURACY_BAR = 1.0

_GOLD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "eval", "seam2_gold.json"
)


@dataclass(frozen=True)
class GoldCase:
    """One hand-verified expectation about the answer seam."""

    id: str
    query: str
    language: str = ENGLISH
    expected_act_id: Optional[str] = None
    expected_section: Optional[str] = None
    expect_refusal: bool = False
    expect_high_stakes: bool = False
    expect_confirmation: bool = False
    # A multi-turn case: a sequence of turns (question then dependent follow-up)
    # run through one Conversation, with the expectation checked on the last turn.
    # Empty for a single-turn case, whose ``query`` is used instead.
    turns: Sequence[str] = ()


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
) -> List[GoldCase]:
    """Load the gold cases, optionally filtered to one language."""
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    cases = [
        GoldCase(
            id=entry["id"],
            query=entry["query"],
            language=entry.get("language", ENGLISH),
            expected_act_id=entry.get("expected_act_id"),
            expected_section=entry.get("expected_section"),
            expect_refusal=entry.get("expect_refusal", False),
            expect_high_stakes=entry.get("expect_high_stakes", False),
            expect_confirmation=entry.get("expect_confirmation", False),
            turns=tuple(entry.get("turns", ())),
        )
        for entry in raw["cases"]
    ]
    if language is not None:
        cases = [c for c in cases if c.language == language]
    return cases


def _answer_case(case: GoldCase, assistant: LegalAssistant):
    """The answer a case is judged on.

    A multi-turn case is run through one Conversation - so a dependent follow-up
    resolves against the earlier turns - and judged on its final turn. A
    single-turn case goes straight through the stateless answer path.
    """
    if case.turns:
        convo = assistant.start_conversation()
        result = None
        for turn in case.turns:
            result = convo.ask(turn, language=case.language)
        return result
    return assistant.answer(case.query, language=case.language)


def _evaluate(case: GoldCase, assistant: LegalAssistant) -> CaseResult:
    result = _answer_case(case, assistant)

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

    if case.expect_confirmation:
        passed = result.needs_confirmation
        detail = (
            "posed a Confirmation Step as expected"
            if passed
            else "expected a Confirmation Step, got a direct answer"
        )
        return CaseResult(case=case, passed=passed, detail=detail)

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


@dataclass
class LanguageEvalResult:
    """One Supported Language's outcome in the final eval pass."""

    language: str
    report: EvalReport
    bar: float = ACCURACY_BAR

    @property
    def accuracy(self) -> float:
        """The fraction of the language's gold cases that held (0 if empty)."""
        if self.report.total == 0:
            return 0.0
        return self.report.passed / self.report.total

    @property
    def meets_bar(self) -> bool:
        """Whether this language cleared the accuracy bar on a non-empty subset."""
        return self.report.total > 0 and self.accuracy >= self.bar


@dataclass
class FinalEvalReport:
    """The final per-language pass: one :class:`LanguageEvalResult` per language."""

    by_language: Dict[str, LanguageEvalResult] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """The whole pass holds only when every Supported Language clears its bar."""
        return bool(self.by_language) and all(
            result.meets_bar for result in self.by_language.values()
        )


def run_final_eval(
    assistant: LegalAssistant,
    languages: Sequence[str] = SUPPORTED_LANGUAGES,
    bar: float = ACCURACY_BAR,
    cases_by_language: Optional[Dict[str, Sequence[GoldCase]]] = None,
) -> FinalEvalReport:
    """Run the gold eval for every Supported Language and check the accuracy bar.

    For each language the curated gold subset (or an override in
    ``cases_by_language``) runs through the real answer seam, and its accuracy is
    held against ``bar``. The whole pass holds only when each language does.
    """
    by_language: Dict[str, LanguageEvalResult] = {}
    for language in languages:
        if cases_by_language is not None and language in cases_by_language:
            cases: Sequence[GoldCase] = cases_by_language[language]
        else:
            cases = load_gold_cases(language=language)
        report = run_gold_eval(assistant, cases)
        by_language[language] = LanguageEvalResult(
            language=language, report=report, bar=bar
        )
    return FinalEvalReport(by_language=by_language)
