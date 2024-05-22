from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Iterable, NewType

from emcie.server.core.threads import Message


ModelId = NewType("ModelId", str)


class TextGenerationModel(ABC):
    @abstractmethod
    async def generate_text(
        self,
        messages: Iterable[Message],
    ) -> AsyncIterator[str]:
        yield ""


class ModelRegistry:
    def __init__(
        self,
    ) -> None:
        self._text_generation_models: Dict[ModelId, TextGenerationModel] = {}

    async def add_text_generation_model(
        self,
        model_id: ModelId,
        model: TextGenerationModel,
    ) -> None:
        self._text_generation_models[model_id] = model

    async def get_text_generation_model(
        self,
        model_id: ModelId,
    ) -> TextGenerationModel:
        return self._text_generation_models[model_id]
