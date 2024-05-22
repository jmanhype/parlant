from typing import AsyncIterator, Iterable, List
from openai import AsyncOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
import os

from emcie.server.core.models import TextGenerationModel
from emcie.server.core.threads import Message


class GPT(TextGenerationModel):
    def __init__(
        self,
        model_id: str,
    ) -> None:
        self.client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model_id = model_id

    async def generate_text(
        self,
        messages: Iterable[Message],
    ) -> AsyncIterator[str]:
        converted_messages = self._convert_messages(messages)

        response = await self.client.chat.completions.create(
            messages=converted_messages,
            model=self.model_id,
            stream=True,
        )

        async for x in response:
            yield x.choices[0].delta.content or ""

    def _convert_messages(self, messages: Iterable[Message]) -> List[ChatCompletionMessageParam]:
        return [{"role": m.role, "content": m.content} for m in messages]  # type: ignore
