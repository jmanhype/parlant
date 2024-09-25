from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional, Sequence, TypedDict

from emcie.common.tools import ToolId
from emcie.server.core.common import generate_id
from emcie.server.core.guidelines import GuidelineId
from emcie.server.core.persistence.common import ObjectId
from emcie.server.core.persistence.document_database import (
    DocumentDatabase,
)

GuidelineToolAssociationId = NewType("GuidelineToolAssociationId", str)


@dataclass(frozen=True)
class GuidelineToolAssociation:
    id: GuidelineToolAssociationId
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
    async def list_associations(self) -> Sequence[GuidelineToolAssociation]: ...


class GuidelineToolAssociationDocument(TypedDict, total=False):
    id: ObjectId
    creation_utc: str
    guideline_id: GuidelineId
    tool_id: ToolId


class GuidelineToolAssociationDocumentStore(GuidelineToolAssociationStore):
    def __init__(self, database: DocumentDatabase):
        self._collection = database.get_or_create_collection(
            name="associations", schema=GuidelineToolAssociationDocument
        )

    def _serialize_association(
        self,
        association: GuidelineToolAssociation,
    ) -> GuidelineToolAssociationDocument:
        return GuidelineToolAssociationDocument(
            id=ObjectId(association.id),
            creation_utc=association.creation_utc.isoformat(),
            guideline_id=association.guideline_id,
            tool_id=association.tool_id,
        )

    def _deserialize_association_documet(
        self,
        association_document: GuidelineToolAssociationDocument,
    ) -> GuidelineToolAssociation:
        return GuidelineToolAssociation(
            id=GuidelineToolAssociationId(association_document["id"]),
            creation_utc=datetime.fromisoformat(association_document["creation_utc"]),
            guideline_id=association_document["guideline_id"],
            tool_id=association_document["tool_id"],
        )

    async def create_association(
        self,
        guideline_id: GuidelineId,
        tool_id: ToolId,
        creation_utc: Optional[datetime] = None,
    ) -> GuidelineToolAssociation:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        association = GuidelineToolAssociation(
            id=GuidelineToolAssociationId(generate_id()),
            creation_utc=creation_utc,
            guideline_id=guideline_id,
            tool_id=tool_id,
        )

        await self._collection.insert_one(document=self._serialize_association(association))

        return association

    async def list_associations(self) -> Sequence[GuidelineToolAssociation]:
        return [
            self._deserialize_association_documet(d)
            for d in await self._collection.find(filters={})
        ]
