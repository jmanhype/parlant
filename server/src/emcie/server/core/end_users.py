from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional

from emcie.server.core import common
from emcie.server.core.persistence import DocumentDatabase, FieldFilter

EndUserId = NewType("EndUserId", str)


@dataclass(frozen=True)
class EndUser:
    id: EndUserId
    creation_utc: datetime
    name: str
    email: str


class EndUserStore(ABC):
    @abstractmethod
    async def create_end_user(
        self,
        name: str,
        email: str,
        creation_utc: Optional[datetime] = None,
    ) -> EndUser: ...

    @abstractmethod
    async def read_end_user(
        self,
        end_user_id: EndUserId,
    ) -> EndUser: ...


class EndUserDocumentStore(EndUserStore):
    def __init__(
        self,
        database: DocumentDatabase,
    ) -> None:
        self._database = database
        self._collection_name = "end_users"

    async def create_end_user(
        self,
        name: str,
        email: str,
        creation_utc: Optional[datetime] = None,
    ) -> EndUser:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        end_user_document = await self._database.insert_one(
            self._collection_name,
            {
                "id": common.generate_id(),
                "name": name,
                "email": email,
                "creation_utc": creation_utc,
            },
        )

        return EndUser(
            id=EndUserId(end_user_document["id"]),
            name=name,
            email=email,
            creation_utc=creation_utc,
        )

    async def read_end_user(
        self,
        end_user_id: EndUserId,
    ) -> EndUser:
        filters = {"id": FieldFilter(equal_to=end_user_id)}
        found_end_user = await self._database.find_one(self._collection_name, filters)

        return EndUser(
            id=EndUserId(found_end_user["id"]),
            name=found_end_user["name"],
            email=found_end_user["email"],
            creation_utc=found_end_user["creation_utc"],
        )
