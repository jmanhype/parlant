from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, NewType, Optional
from abc import ABC, abstractmethod

from emcie.server.core import common
from emcie.server.core.persistence import DocumentDatabase

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
    ) -> Guideline: ...

    @abstractmethod
    async def list_guidelines(
        self,
        guideline_set: str,
    ) -> Iterable[Guideline]: ...

    @abstractmethod
    async def read_guideline(
        self,
        guideline_set: str,
        guideline_id: GuidelineId,
    ) -> Guideline: ...


class GuidelineDocumentStore(GuidelineStore):
    def __init__(self, database: DocumentDatabase[Guideline]):
        self.database = database

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
        return await self.database.add_document(guideline_set, guideline.id, guideline)

    async def list_guidelines(
        self,
        guideline_set: str,
    ) -> Iterable[Guideline]:
        return await self.database.read_documents(
            guideline_set,
        )

    async def read_guideline(
        self,
        guideline_set: str,
        guideline_id: GuidelineId,
    ) -> Guideline:
        return await self.database.read_document(
            guideline_set,
            guideline_id,
        )
