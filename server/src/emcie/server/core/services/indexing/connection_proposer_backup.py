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
Guideline 1: When <X>, then <Y>.
Guideline 2: When <W>, then <Z>.
where the application of <Y> necessarily causes <W> to hold true.

When testing two such guidelines (1, 2) against a conversation,
it may happen that <X> applies and therefore, by Guideline 1, <Y> is applied.
By looking at the conversation itself, before the application of Guideline 1,
<W> may not apply, which would lead to Guideline 2 not applying either.
This is not our desired behavior, however, since applying Guideline 1 causes <Y> to apply immediately, which means that <W> holds true, and Guideline 2 should apply immediately as well.
We therefore need to detect and index such implicit guideline connections.

Your job is to detect cases in evaluated guidelines that follow the pattern:
When <X> then <Y>; When <W> then <Z>; Where applying <Y> causes <W> to hold true.
Meaning, that the application of the "then" part of the first guideline (called the "source" guideline)
necessarily causes the "when" part of the second guideline (called the "target" guideline) to apply.
We call this pattern an "implication".
Please pay special attention to the fact that implication is fulfilled if and only if <W> necessarily becomes true by the application <Y>. By this, if it's possible for <W> to be false while <Y> is true, then <Y> cannot imply <W>. 
Additionally, when examining connections, we might encounter a case where applying <Y> "implies" that <W> is likely to have occurred earlier, or is likely to occur in the future. Note that we do not consider such cases as implications, since it's not the application of <Y> which causes <W> to be true. 

There are two types of implication:
- Entailed: This means that the source guideline's "then" necessarily entails
            the target guideline's "when".
- Suggested: This is the same as "entailed", except in these cases the target's
            "then" is suggestive instead of necessary. For example, in cases such as
             source="When <X> then <Y>", target="When <something implied by <Y>> then consider <Z>".

At the end of this message, you will receive a test guideline to evaluate against a set of other guidelines which are candidates for
implication. For each candidate, the test guideline may be found as either the source or the target in the
connection, or neither. Be forgiving regarding misspelling and grammatical errors.

At the end of this message, you will receive a test guideline to evaluate against a set of other guidelines which are candidates for
implication. For each candidate, the test guideline may be found as either the source or the target in the
connection, or neither. Be forgiving regarding misspelling and grammatical errors.

Please output JSON structured in the following format:

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

The output JSON should have two proposition entries for each implication candidate - one with the test guideline as the source, and one with it as the target. 

The following are examples of expected outputs for a given input:
###
Example 1:
{{
**Input**:

Test guideline: ###
{{"id": 0, "when": "providing the weather update", "then": "mention whether it's likely to rain"}}
###

Implication candidates: ###
{{"id": 1, "when": "the user asked about the weather", "then": "provide the current weather update"}}
{{"id": 2, "when": "discussing whether an umbrella is needed", "then": "refer the user to our electronic store"}}
###

**Expected Output**

```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "mention whether it's likely to rain",
            "target_when": "the user asked about the weather",
            "is_target_when_implied_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "mentioning the likelihood of rain does not cause the user ask about the weather retrospectively",
            "implication_score": 3
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "provide the current weather update",
            "target_when": "providing the weather update",
            "is_target_when_implied_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "providing a current weather update necessarily makes the target's 'when' apply",
            "implication_score": 10
        }},
        {{
            "source_id": 0,
            "target_id": 2,
            "source_then": "mention whether it's likely to rain",
            "target_when": "discussing whether an umbrella is needed",
            "is_target_when_implied_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "mentioning the chances for rain does not retrospectively make the discussion about umbrellas",
            "implication_score": 3
        }},
        {{
            "source_id": 2,
            "target_id": 0,
            "source_then": "refer the user to our electronic store",
            "target_when": "providing the weather update",
            "is_target_when_implied_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "referring to the electronic store does not imply providing a weather update",
            "implication_score": 1
        }}
    ]
}}


Example 2
**Input**:
Test guideline: ###
{{"id": 0, "when": "The user asks for a book recommendation", "then": "suggest a book"}}
###
Implication candidates: ###
###
{{"id": 1, "when": "suggesting a book", "then": "mention its availability in the local library"}}
{{"id": 2, "when": "recommending books", "then": "consider highlighting the ones with the best reviews"}}
{{"id": 3, "when": "the user greets you", "then": "greet them back with 'hello'"}}
{{"id": 4, "when": "suggesting products", "then": "check if the product is available in our store, and only offer it if it is"}}

**Expected Output**
```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "suggest a book",
            "target_when": "suggesting a book",
            "is_target_when_implied_by_source_then": true,
            "rationale": "the source's 'then' and the target's 'when' are equivalent",
            "implication_score": 10
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "mention its availability in the local library",
            "target_when": "The user asks for a book recommendation",
            "is_target_when_implied_by_source_then": false,
            "rationale": "mentioning library availability does not retrospectively make the user ask for book recommendations",
            "implication_score": 1
        }},
        {{
            "source_id": 0,
            "target_id": 2,
            "source_then": "suggest a book",
            "target_when": "recommending books",
            "is_target_when_implied_by_source_then": true,
            "is_target_then_suggestive_or_optional": true,
            "rationale": "by applying 'suggest a book' we are recommending books",
            "implication_score": 9
        }},
        {{
            "source_id": 2,
            "target_id": 0,
            "source_then": "consider highlighting the ones with the best reviews",
            "target_when": "The user asks for a book recommendation",
            "is_target_when_implied_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "highlighting review does not make the user retrospectively ask for anything",
            "implication_score": 1
        }},
        {{
            "source_id": 0,
            "target_id": 3,
            "source_then": "suggest a book",
            "target_when": "the user greets you",
            "is_target_when_implied_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "suggesting a book does not mean that the user has greeted you",
            "implication_score": 1
        }},
        {{
            "source_id": 3,
            "target_id": 0,
            "source_then": "greet them back with 'hello'",
            "target_when": "The user asks for a book recommendation",
            "is_target_when_implied_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "greeting the user does not imply them asking for a book recommendation",
            "implication_score": 1
        }},
        {{
            "source_id": 0,
            "target_id": 4,
            "source_then": "suggest a book",
            "target_when": "suggesting products",
            "is_target_when_implied_by_source_then": true,
            "is_target_then_suggestive_or_optional": true,
            "rationale": "by suggesting a book, we are necessarily suggesting a product",
            "implication_score": 9
        }},
        {{
            "source_id": 4,
            "target_id": 0,
            "source_then": "check if the product is available in our store, and only offer it if it is'",
            "target_when": "The user asks for a book recommendation",
            "is_target_when_implied_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "checking product availability does not directly imply anything about book recommendations",
            "implication_score": 2
        }}
    ]
}}
```

###
Example 3
**Input**:
Test guideline: ###
{{"id": 0, "when": "a new topping is suggested", "then": "announce that the suggestion would be forwarded to management for consideration"}}
###
Implication candidates: ###
###
{{"id": 1, "when": "discussing opening hours", "then": "mention that the store closes early on Sundays"}}
{{"id": 2, "when": "the user asks for a topping we do not offer", "then": "suggest to add the topping to the menu in the future"}}
{{"id": 3, "when": "forwarding messages to management", "then": "forward the message via email"}}

**Expected Output**
```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "announce that the suggestion would be forwarded to management for consideration,
            "target_when": "discussing opening hours",
            "is_target_when_implied_by_source_then": false,
            "rationale": "forwarding something to management has nothing to do with opening hours",
            "implication_score": 1
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "mention that the store closes early on Sundays",
            "target_when": "a new topping is suggested",
            "is_target_when_implied_by_source_then": false,
            "rationale": "store hours discussion does not imply anything about whether a new topping was suggested",
            "implication_score": 1
        }},
        {{
            "source_id": 0,
            "target_id": 2,
            "source_then": "announce that the suggestion would be forwarded to managment for consideration",
            "target_when": "the user asks for a topping we do not offer",
            "is_target_when_implied_by_source_then": false,
            "rationale": "announcing something does not cause the user to have retrospectively asked about anything regarding toppings",
            "implication_score": 2
        }},
        {{
            "source_id": 2,
            "target_id": 0,
            "source_then": "suggest to add the topping to the menu in the future",
            "target_when": "a new topping is suggested",
            "is_target_when_implied_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "by suggesting to add the topping to the menu, a new topping is being suggested",
            "implication_score": 9
        }},
        {{
            "source_id": 0,
            "target_id": 3,
            "source_then": "announce that the suggestion would be forwarded to management for consideration",
            "target_when": "forwarding messages to management",
            "is_target_when_implied_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the announcement from the source's 'when' necessarily implies that a message needs to be forwarded to management",
            "implication_score": 8
        }},
        {{
            "source_id": 3,
            "target_id": 0,
            "source_then": "forward the message via email",
            "target_when": "a new topping is suggested",
            "is_target_when_implied_by_source_then": false,
            "rationale": "emailing a message is not necessarily a new topping suggestion",
            "implication_score": 2
        }}
    ]
}}

```
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
The guidelines you should analyze for connections are:
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
        with open("new format initial prompt 23.9.txt", "w") as f:
            f.write(prompt)  # TODO delete
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

        relevant_propositions = [
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
