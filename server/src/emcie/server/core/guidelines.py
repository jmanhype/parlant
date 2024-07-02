from typing import Iterable, NewType, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from emcie.server.core import common
from emcie.server.core.persistence import DocumentDatabase, FieldFilter

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
    def __init__(self, database: DocumentDatabase):
        self._database = database
        self._collection_name = "guidelines"

    async def create_guideline(
        self,
        guideline_set: str,
        predicate: str,
        content: str,
        creation_utc: Optional[datetime] = None,
    ) -> Guideline:
        guideline_to_insert = {
            "guideline_set": guideline_set,
            "predicate": predicate,
            "content": content,
            "creation_utc": creation_utc or datetime.now(timezone.utc),
        }
        guideline = common.create_instance_from_dict(
            Guideline,
            await self._database.insert_one(self._collection_name, guideline_to_insert),
        )
        return guideline

    async def list_guidelines(self, guideline_set: str) -> Iterable[Guideline]:
        filters = {"guideline_set": FieldFilter(equal_to=guideline_set)}
        return (
            common.create_instance_from_dict(Guideline, d)
            for d in await self._database.find(self._collection_name, filters)
        )

    async def read_guideline(self, guideline_set: str, guideline_id: GuidelineId) -> Guideline:
        filters = {
            "guideline_set": FieldFilter(equal_to=guideline_set),
            "id": FieldFilter(equal_to=guideline_id),
        }
        guideline = common.create_instance_from_dict(
            Guideline, await self._database.find_one(self._collection_name, filters)
        )
        return guideline
