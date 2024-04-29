from typing import List

from emcie.server.engines.common import Context, Engine
from emcie.server.sessions import Event


class AlphaEngine(Engine):
    async def process(self, context: Context) -> List[Event]:
        return []
