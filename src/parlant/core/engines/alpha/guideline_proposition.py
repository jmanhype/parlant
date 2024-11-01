# This is a separate module to avoid circular dependencies

from dataclasses import dataclass

from parlant.core.guidelines import Guideline


@dataclass(frozen=True)
class GuidelineProposition:
    guideline: Guideline
    score: int
    rationale: str
