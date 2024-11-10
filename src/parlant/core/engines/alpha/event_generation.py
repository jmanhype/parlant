from dataclasses import dataclass
from typing import Optional, Sequence

from parlant.core.emissions import EmittedEvent
from parlant.core.nlp.generation import GenerationInfo


@dataclass(frozen=True)
class EventGenerationResult:
    generation_info: GenerationInfo
    events: Sequence[Optional[EmittedEvent]]
