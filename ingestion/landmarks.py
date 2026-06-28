"""Curated Landmark Judgment loader.

A hand-verified file of precedents with full official citations. Like the
IPC-BNS mapping it is a structured side-file, never a retrievable Source of
Truth; the generator may cite a judgment only if it appears here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union


@dataclass(frozen=True)
class LandmarkJudgment:
    id: str
    case_name: str
    citation: str
    year: int
    court: str
    official_url: str
    domain: str
    holding: str

    def has_full_citation(self) -> bool:
        return all([self.case_name, self.citation, self.year, self.court, self.official_url])


def load_landmark_judgments(path: Union[str, Path]) -> List[LandmarkJudgment]:
    raw = json.loads(Path(path).read_text())
    return [LandmarkJudgment(**j) for j in raw["judgments"]]
