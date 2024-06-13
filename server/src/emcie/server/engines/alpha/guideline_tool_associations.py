from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional
from emcie.server.core import common
from emcie.server.core.guidelines import GuidelineId
from emcie.server.core.tools import ToolId

ToolGuidelineAssociationId = NewType("ToolGuidelineAssociationId", str)


@dataclass(frozen=True)
class GuidelineToolAssociation:
    id: ToolGuidelineAssociationId
    creation_utc: datetime
    guideline_id: GuidelineId
    tool_id: ToolId

    def __hash__(self) -> int:
        return hash(self.id)


class GuidelineToolAssociationStore:
    def __init__(
        self,
    ) -> None:
        self._associations: dict[GuidelineId, set[GuidelineToolAssociation]] = defaultdict(set)

    async def create_association(
        self,
        guideline_id: GuidelineId,
        tool_id: ToolId,
        creation_utc: Optional[datetime] = None,
    ) -> GuidelineToolAssociation:
        association = GuidelineToolAssociation(
            id=ToolGuidelineAssociationId(common.generate_id()),
            creation_utc=creation_utc or datetime.now(timezone.utc),
            guideline_id=guideline_id,
            tool_id=tool_id,
        )

        self._associations[guideline_id].add(association)

        return association

    async def list_associations(
        self,
    ) -> dict[GuidelineId, set[GuidelineToolAssociation]]:
        return self._associations
