import asyncio
from dataclasses import dataclass
from itertools import chain
import json
from typing import Sequence
from more_itertools import chunked

from emcie.server.core.agents import Agent
from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.guideline_connections import ConnectionKind
from emcie.server.core.guidelines import GuidelineContent
from emcie.server.core.logging import Logger
from emcie.server.core.nlp.generation import SchematicGenerator
from emcie.server.core.terminology import TerminologyStore
from emcie.server.core.engines.alpha.prompt_builder import PromptBuilder


class GuidelineConnectionPropositionSchema(DefaultBaseModel):
    source_id: int
    target_id: int
    source_then: str
    target_when: str
    is_target_when_implied_by_source_then: bool
    is_target_then_suggestive_or_optional: bool = False
    rationale: str
    implication_score: int


class GuidelineConnectionPropositionsSchema(DefaultBaseModel):
    propositions: list[GuidelineConnectionPropositionSchema]


@dataclass(frozen=True)
class GuidelineConnectionProposition:
    source: GuidelineContent
    target: GuidelineContent
    kind: ConnectionKind
    score: int
    rationale: str


class GuidelineConnectionProposer:
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[GuidelineConnectionPropositionsSchema],
        terminology_store: TerminologyStore,
    ) -> None:
        self._logger = logger
        self._terminology_store = terminology_store
        self._schematic_generator = schematic_generator
        self._batch_size = 5

    async def propose_connections(
        self,
        agent: Agent,
        introduced_guidelines: Sequence[GuidelineContent],
        existing_guidelines: Sequence[GuidelineContent] = [],
    ) -> Sequence[GuidelineConnectionProposition]:
        if not introduced_guidelines:
            return []

        connection_proposition_tasks = []

        for i, introduced_guideline in enumerate(introduced_guidelines):
            filtered_existing_guidelines = [
                g
                for g in chain(
                    introduced_guidelines[i + 1 :],
                    existing_guidelines,
                )
            ]

            guideline_batches = chunked(filtered_existing_guidelines, self._batch_size)

            connection_proposition_tasks.extend(
                [
                    asyncio.create_task(
                        self._generate_propositions(agent, introduced_guideline, batch)
                    )
                    for batch in guideline_batches
                ]
            )

        with self._logger.operation(
            f"Propose guideline connections for {len(connection_proposition_tasks)} "  # noqa
            f"batches (batch size={self._batch_size})",
        ):
            propositions = chain.from_iterable(await asyncio.gather(*connection_proposition_tasks))
            return list(propositions)

    async def _format_connection_propositions(
        self,
        agent: Agent,
        evaluated_guideline: GuidelineContent,
        comparison_set: dict[int, GuidelineContent],
    ) -> str:
        builder = PromptBuilder()
        builder.add_section(
            f"""
In our system, the behavior of conversational AI agents is guided by "guidelines".

Each guideline is composed of two parts:
- "when": this is a natural-language predicate that specifies when a guideline should apply.
          we look at each conversation at any particular state, and we test against this
          predicate to understand if we should have this guideline participate in generating
          the next reply to the user.
- "then": this is a natural-language instruction that should be followed whenever the
          "when" part of the guidelines applies to the conversation in its particular state.

Now, if we have many guidelines, it is possible to encounter a situation like this:
Guideline N: When <X>, then <Y>.
Guideline N+1: When <Y>, then <Z>.

Note, in this edge case, that, when testing these two guidelines (N, N+1) against a conversation,
it may happen that <X> applies and therefore Guideline N should apply.
However, the application of Guideline N would also make necessarily <Y> apply.
But just by looking at the conversation itself, before the application of Guideline N,
<Y> may not necessarily apply, which would lead to Guideline N+1 not applying either.
But this is a bug in the expected behavior, because, if the guideline designer said
"When <X> then <Y>" and "When <Y> then <Z>", they clearly want <Z> to happen when <X> applies.

We therefore need to detect these implicit connections between guidelines, and index them as such.

Your job is to detect cases in evaluated guidelines that follow the pattern:
When <X> then <Y>; When <Y> then <Z>.
Meaning, that the "then" part of the first guideline (called the "source" guideline),
by itself implies and makes true the "when" part of the second guideline (called the "target" guideline).
We call this pattern an "implication".
Please note that there is no implication when <Y> is something that *may* happen in the future following <X>.
It is only about whether <Y> in itself is directly and immediately implied by <X>.

There are two types of implication:
- Entailed: This means that the source guideline's "then" necessarily entails
            the target guideline's "when".
- Suggested: This is the same as "entailed", except in these cases the target's
            "then" is suggestive instead of necessary. For example, in cases such as
             source="When <X> then <Y>", target="When <Y> then consider <Z>".

You will now receive a test guideline to evaluate against a set of other guidelines which are candidates for
implication. For each candidate, the test guideline may be found as either the source or the target in the
connection, or neither.

Please output JSON structured as per the following examples. The output should have one json per every ordered pair of guidelines:

{{
    "propositions": [
        {{
            "source_id": <id of the source guideline>,
            "target_id": <id of the target guideline>,
            "source_then": <The source guideline's 'then'>,
            "target_when": <The target guideline's 'when'>,
            "is_target_when_implied_by_source_then": <BOOL>,
            "is_target_then_suggestive_or_optional": <BOOL>,
            "rationale": <Explanation for the implication between the source's 'then' and the target's 'when'>,
            "implication_score": <Score between 1-10 indicating the strength of the connection>
        }},
        ...
    ]
}}

The following are examples of expected outputs for a given input:
###"""  # noqa
        )

        # Find and add terminology to prompt
        implication_candidates = "\n\t".join(
            f"{{id: {id}, when: {g.predicate}, then: {g.action}}}"
            for id, g in comparison_set.items()
        )
        test_guideline = f"{{id: 0, when: '{evaluated_guideline.predicate}', then: '{evaluated_guideline.action}'}}"
        terms = await self._terminology_store.find_relevant_terms(
            agent.id,
            query=test_guideline + implication_candidates,
        )
        builder.add_terminology(terms)

        builder.add_section(
            f"""
Example 1: ###
{{
**Input**:

Test guideline: ###
{{"id": 0, "when": "providing the weather update", "then": "mention the best time to go for a walk"}}
###

Implication candidates: ###
{{"id": 1, "when": "the user asks about the weather", "then": "provide the current weather update"}}
###

**Expected Output**

```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "mention the best time to go for a walk",
            "target_when": "the user asks about the weather",
            "is_target_when_implied_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "asking about the weather is not entailed from mentioning the best time for a walk",
            "implication_score": 1
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "provide the current weather update",
            "target_when": "providing the weather update",
            "is_target_when_implied_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "Mentioning the best time to go for a walk follows logically from providing a weather update",
            "implication_score": 10
        }}
    ]
}}
```
###


The guidelines you should check for connections are:

Test guideline: ###
{test_guideline}
###

Implication candidates: ###
{implication_candidates}
###"""
        )
        return builder.build()

    async def _generate_propositions(
        self,
        agent: Agent,
        guideline_to_test: GuidelineContent,
        guidelines_to_compare: Sequence[GuidelineContent],
    ) -> list[GuidelineConnectionProposition]:
        guidelines_dict = {i: g for i, g in enumerate(guidelines_to_compare, start=1)}
        guidelines_dict[0] = guideline_to_test
        prompt = await self._format_connection_propositions(
            agent,
            guideline_to_test,
            {k: v for k, v in guidelines_dict.items() if k != 0},
        )

        response = await self._schematic_generator.generate(
            prompt=prompt,
            hints={"temperature": 0.0},
        )

        self._logger.debug(
            f"""
----------------------------------------
Connection Propositions Found:
----------------------------------------
{json.dumps([p.model_dump(mode="json") for p in response.content.propositions], indent=2)}
----------------------------------------
"""
        )

        relevant_propositions = [  # TODO I was here
            GuidelineConnectionProposition(
                source=guidelines_dict[p.source_id],
                target=guidelines_dict[p.target_id],
                kind={
                    False: ConnectionKind.ENTAILS,
                    True: ConnectionKind.SUGGESTS,
                }[p.is_target_then_suggestive_or_optional],
                score=int(p.implication_score),
                rationale=p.rationale,
            )
            for p in response.content.propositions
            if p.implication_score >= 7
        ]

        return relevant_propositions
