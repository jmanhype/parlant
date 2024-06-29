from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional

from emcie.server.core.common import generate_id
from emcie.server.core.persistence import DocumentCollection

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
        self, name: str, email: str, creation_utc: Optional[datetime] = None
    ) -> EndUser:
        pass

    @abstractmethod
    async def read_end_user(self, end_user_id: EndUserId) -> EndUser:
        pass


class EndUserDocumentStore(EndUserStore):
    def __init__(self, end_user_collection: DocumentCollection[EndUser]):
        self.end_user_collection = end_user_collection

    async def create_end_user(
        self, name: str, email: str, creation_utc: Optional[datetime] = None
    ) -> EndUser:
        end_user = EndUser(
            id=EndUserId(generate_id()),
            name=name,
            email=email,
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )
        await self.end_user_collection.add_document("end_users", end_user.id, end_user)
        return end_user

    async def read_end_user(self, end_user_id: EndUserId) -> EndUser:
        return await self.end_user_collection.read_document("end_users", end_user_id)
