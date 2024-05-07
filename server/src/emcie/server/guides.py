from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, NewType, Optional

from emcie.server import common

GuideId = NewType("GuideId", str)


@dataclass(frozen=True)
class Guide:
    id: GuideId
    creation_utc: datetime
    predicate: str
    content: str


class GuideStore:
    def __init__(
        self,
    ) -> None:
        self._guide_sets: dict[str, dict[GuideId, Guide]] = defaultdict(lambda: dict())

    async def create_guide(
        self,
        guide_set: str,
        predicate: str,
        content: str,
        creation_utc: Optional[datetime] = None,
    ) -> Guide:
        guide = Guide(
            id=GuideId(common.generate_id()),
            predicate=predicate,
            content=content,
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )

        self._guide_sets[guide_set][guide.id] = guide

        return guide

    async def list_guides(
        self,
        guide_set: str,
    ) -> Iterable[Guide]:
        return self._guide_sets[guide_set].values()
