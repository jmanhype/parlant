from typing import Iterable, NewType, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from emcie.server.core import common
from emcie.server.core.persistence import DocumentCollection

GuidelineId = NewType("GuidelineId", str)


@dataclass(frozen=True)
class Guideline:
    id: GuidelineId
    creation_utc: datetime
    predicate: str
    content: str


class GuidelineStore(ABC):
    @abstractmethod
    async def create_guideline(
        self,
        guideline_set: str,
        predicate: str,
        content: str,
        creation_utc: Optional[datetime] = None,
    ) -> Guideline:
        pass

    @abstractmethod
    async def list_guidelines(self, guideline_set: str) -> Iterable[Guideline]:
        pass

    @abstractmethod
    async def read_guideline(self, guideline_set: str, guideline_id: GuidelineId) -> Guideline:
        pass


class GuidelineDocumentStore(GuidelineStore):
    def __init__(self, guideline_collection: DocumentCollection[Guideline]):
        self.guideline_collection = guideline_collection

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
        return await self.guideline_collection.add_document(guideline_set, guideline.id, guideline)

    async def list_guidelines(self, guideline_set: str) -> Iterable[Guideline]:
        return await self.guideline_collection.read_documents(guideline_set)

    async def read_guideline(self, guideline_set: str, guideline_id: GuidelineId) -> Guideline:
        return await self.guideline_collection.read_document(guideline_set, guideline_id)
