from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, NewType, Optional

from emcie.server.core import common
from emcie.server.core.guidelines import GuidelineId
from emcie.server.core.tools import ToolId
from emcie.server.core.persistence import DocumentCollection

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
    def __init__(self, association_collection: DocumentCollection[GuidelineToolAssociation]):
        self._collection = association_collection

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
        await self._collection.add_document(guideline_id, association.id, association)
        return association

    async def list_associations(self) -> Iterable[GuidelineToolAssociation]:
        associations: list[GuidelineToolAssociation] = []
        for guideline_id in await self._collection.list_collections():
            associations.extend(await self._collection.read_documents(guideline_id))
        return associations
