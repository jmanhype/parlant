from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional

from emcie.server.core.common import generate_id

EndUserId = NewType("EndUserId", str)


@dataclass(frozen=True)
class EndUser:
    id: EndUserId
    creation_utc: datetime
    name: str
    email: str


class EndUserStore:
    def __init__(
        self,
    ) -> None:
        self._end_users: dict[EndUserId, EndUser] = {}

    async def create_end_user(
        self,
        name: str,
        email: str,
        creation_utc: Optional[datetime] = None,
    ) -> EndUser:
        end_user = EndUser(
            id=EndUserId(generate_id()),
            name=name,
            email=email,
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )

        self._end_users[end_user.id] = end_user

        return end_user

    async def read_end_user(self, end_user_id: EndUserId) -> EndUser:
        return self._end_users[end_user_id]
