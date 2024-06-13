from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, NewType, Optional

from emcie.server.core import common

GuidelineId = NewType("GuidelineId", str)


@dataclass(frozen=True)
class Guideline:
    id: GuidelineId
    creation_utc: datetime
    predicate: str
    content: str


class GuidelineStore:
    def __init__(
        self,
    ) -> None:
        self._guideline_sets: dict[str, dict[GuidelineId, Guideline]] = defaultdict(dict)

    async def create_guideline(
        self,
        guideline_set: str,
        predicate: str,
        content: str,
        creation_utc: Optional[datetime] = None,
    ) -> Guideline:
        guideline = Guideline(
            id=GuidelineId(common.generate_id()),
            predicate=predicate,
            content=content,
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )

        self._guideline_sets[guideline_set][guideline.id] = guideline

        return guideline

    async def list_guidelines(
        self,
        guideline_set: str,
    ) -> Iterable[Guideline]:
        return self._guideline_sets[guideline_set].values()

    async def read_guideline(
        self,
        guideline_set: str,
        guideline_id: GuidelineId,
    ) -> Guideline:
        return self._guideline_sets[guideline_set][guideline_id]
