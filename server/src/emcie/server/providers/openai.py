from typing import AsyncGenerator, Iterable, List
from openai import OpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
import os

from emcie.server.models import TextGenerationModel
from emcie.server.threads import Message


class GPT4Turbo(TextGenerationModel):
    def __init__(
        self,
    ) -> None:
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def generate_text(
        self,
        messages: Iterable[Message],
    ) -> AsyncGenerator[str, None]:
        converted_messages = self._convert_messages(messages)

        response = self.client.chat.completions.create(
            messages=converted_messages,
            model="gpt-4-turbo-preview",
            stream=True,
        )

        for x in response:
            yield x.choices[0].delta.content or ""

    def _convert_messages(self, messages: Iterable[Message]) -> List[ChatCompletionMessageParam]:
        return [{"role": m.role, "content": m.content} for m in messages]  # type: ignore
