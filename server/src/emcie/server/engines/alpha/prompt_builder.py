from __future__ import annotations
from enum import Enum, auto
from itertools import chain
from typing import Any, Mapping, Optional, Sequence, cast

from emcie.server.core.common import generate_id
from emcie.server.core.context_variables import ContextVariable, ContextVariableValue
from emcie.server.core.sessions import Event
from emcie.server.core.tools import Tool
from emcie.server.engines.alpha.guideline_filter import GuidelineProposition
from emcie.server.engines.alpha.tool_caller import produced_tool_events_to_dict
from emcie.server.engines.alpha.utils import context_variables_to_json, events_to_json
from emcie.server.engines.common import ProducedEvent


class BuiltInSection(Enum):
    INTERACTION_HISTORY = auto()
    CONTEXT_VARIABLES = auto()
    GUIDELINE_PROPOSITIONS = auto()
    STAGED_EVENTS = auto()


class SectionStatus(Enum):
    ACTIVE = auto()
    """The section has active information that must be taken into account"""

    PASSIVE = auto()
    """The section is inactive, but may have explicit empty-state inclusion in the prompt"""

    NONE = auto()
    """The section is not included in the prompt in any fashion"""


class PromptBuilder:
    def __init__(self) -> None:
        self._sections: dict[str | BuiltInSection, dict[str, Any]] = {}

    def build(self) -> str:
        section_contents = [s["content"] for s in self._sections.values()]
        prompt = "\n\n".join(section_contents)
        return prompt

    def add_section(
        self,
        content: str,
        name: str | BuiltInSection | None = None,
        title: Optional[str] = None,
        status: Optional[SectionStatus] = None,
    ) -> PromptBuilder:
        while not name:
            candidate = generate_id()

            if candidate not in self._sections:
                name = candidate

        if name in self._sections:
            raise ValueError(f"Section '{name}' was already added")

        self._sections[name] = {
            "content": content.strip(),
            "title": title,
            "status": status,
        }

        return self

    def section_status(self, name: str | BuiltInSection) -> SectionStatus:
        if section := self._sections.get(name):
            return cast(SectionStatus, section["status"])
        else:
            return SectionStatus.NONE

    def add_interaction_history(
        self,
        events: Sequence[Event],
    ) -> PromptBuilder:
        if events:
            events_as_json = events_to_json(events)

            self.add_section(
                name=BuiltInSection.INTERACTION_HISTORY,
                content=f"""
The following is a list of events describing a back-and-forth
interaction between you, an AI assistant, and a user: ###
{events_as_json}
###
""",
                status=SectionStatus.ACTIVE,
            )
        else:
            self.add_section(
                name=BuiltInSection.INTERACTION_HISTORY,
                content="""
You, an AI assistant, are now present in an online session with a user.
An interaction, addressing the user, may or may not be initiated by you now.

Here's how to decide whether to initiate the interaction:
A. If the rules below both apply to the context, as well as suggest that you should say something
to the user, then you should indeed initiate the interaction now.
B. Otherwise, if no reason is provided that suggests you should say something to the user,
then you should not initiate the interaction. Produce no response in this case.
""",
                status=SectionStatus.PASSIVE,
            )

        return self

    def add_context_variables(
        self,
        variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
    ) -> PromptBuilder:
        if variables:
            context_values = context_variables_to_json(variables)

            self.add_section(
                name=BuiltInSection.CONTEXT_VARIABLES,
                content=f"""
The following is information that you're given about the user and context of the interaction: ###
{context_values}
###
""",
                status=SectionStatus.ACTIVE,
            )

        return self

    def add_guideline_propositions(
        self,
        ordinary: Sequence[GuidelineProposition],
        tool_enabled: Mapping[GuidelineProposition, Sequence[Tool]],
    ) -> PromptBuilder:
        all_propositions = list(chain(ordinary, tool_enabled))

        if all_propositions:

            rules = "\n".join(
                f"{i}) When {p.guideline.predicate}, then {p.guideline.content}"
                f"\n    [Priority (1-10): {p.score}, rationale: {p.rationale}]"
                for i, p in enumerate(all_propositions, start=1)
            )

            self.add_section(
                name=BuiltInSection.GUIDELINE_PROPOSITIONS,
                content=f"""
In formulating your response, you are required to follow these behavioral rules,
which are applicable to the latest state of the interaction.
Each rule is accompanied by a priority score indicating its significance,
and a rationale explaining why it is applicable: ###
{rules}
###
""",
                status=SectionStatus.ACTIVE,
            )
        else:
            self.add_section(
                name=BuiltInSection.GUIDELINE_PROPOSITIONS,
                content="""
In formulating your response, you are normally required to follow a number of behavioral rules.
However, in this case, no special behavrioal rules were provided.
""",
                status=SectionStatus.PASSIVE,
            )

        return self

    def add_staged_events(
        self,
        events: Sequence[ProducedEvent],
    ) -> PromptBuilder:
        if events:
            # FIXME: The following is a code-smell. We can't assume staged_events
            #        is necessarily only composed of tool events.
            #        Also, produced_tool_events_to_dict() is an oddball of a function.
            staged_events_as_dict = produced_tool_events_to_dict(events)

            self.add_section(
                name=BuiltInSection.STAGED_EVENTS,
                content=f"""
For your information, here are some staged events that have just been produced,
to assist you with generating your response message while following the rules above: ###
{staged_events_as_dict}
###
""",
                status=SectionStatus.ACTIVE,
            )

        return self
