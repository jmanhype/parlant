from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, NewType, Optional

from emcie.server.core import common
from emcie.server.core.guidelines import GuidelineId
from emcie.server.core.tools import ToolId
from emcie.server.core.persistence import DocumentDatabase

ToolGuidelineAssociationId = NewType("ToolGuidelineAssociationId", str)


@dataclass(frozen=True)
class GuidelineToolAssociation:
    id: ToolGuidelineAssociationId
    creation_utc: datetime
    guideline_id: GuidelineId
    tool_id: ToolId

    def __hash__(self) -> int:
        return hash(self.id)


class GuidelineToolAssociationStore(ABC):
    @abstractmethod
    async def create_association(
        self,
        guideline_id: GuidelineId,
        tool_id: ToolId,
        creation_utc: Optional[datetime] = None,
    ) -> GuidelineToolAssociation: ...

    @abstractmethod
    async def list_associations(self) -> Iterable[GuidelineToolAssociation]: ...


class GuidelineToolAssociationDocumentStore(GuidelineToolAssociationStore):
    def __init__(self, database: DocumentDatabase):
        self._database = database
        self._collection_name = "associations"

    async def create_association(
        self,
        guideline_id: GuidelineId,
        tool_id: ToolId,
        creation_utc: Optional[datetime] = None,
    ) -> GuidelineToolAssociation:
        association_data = {
            "creation_utc": creation_utc or datetime.now(timezone.utc),
            "guideline_id": guideline_id,
            "tool_id": tool_id,
        }
        inserted_association = await self._database.insert_one(
            self._collection_name, association_data
        )

        association = common.create_instance_from_dict(
            GuidelineToolAssociation, inserted_association
        )
        return association

    async def list_associations(self) -> Iterable[GuidelineToolAssociation]:
        associations_data = await self._database.find(self._collection_name, filters={})
        associations = (
            common.create_instance_from_dict(GuidelineToolAssociation, a) for a in associations_data
        )
        return associations
