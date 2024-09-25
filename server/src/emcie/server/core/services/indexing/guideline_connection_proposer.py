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
    is_target_when_caused_by_source_then: bool
    is_target_then_suggestive_or_optional: bool = False
    rationale: str
    causation_score: int


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
In our system, the behavior of a conversational AI agent is guided by "guidelines". The agent makes use of these guidelines whenever it interacts with a user.

Each guideline is composed of two parts:
- "when": this is a natural-language predicate that specifies when a guideline should apply.
          we look at each conversation at any particular state, and we test against this
          predicate to understand if we should have this guideline participate in generating
          the next reply to the user.
- "then": this is a natural-language instruction that should be followed by the agent
          whenever the "when" part of the guideline applies to the conversation in its particular state.
          Any instruction described here applies only to the agent, and not to the user. 


Now, if we have multiple guidelines, situations might arise where:
Guideline 1: When <X>, then <Y>.
Guideline 2: When <W>, then <Z>.
Sometimes, applying the "then" of Guideline 1 (<Y>) may directly cause the "when" of Guideline 2 (<W>) to hold true, forming what we call a "causal connection" or simply "causation" from Guideline 1 to Guideline 2. This causation can only happen if the agent's action in <Y> directly causes the "when" in Guideline 2 (<W>) to become true.

Important clarification: An action taken by the agent can never cause the user to do anything. Causation only occurs if applying the source's "then" action directly and immediately causes the the "when" of the target guideline to apply. Cases where the source's "then" implies that the target's "when" happened in the past, or will happen in the future, are not considered causation. 
As a result of this, if there's any scenerio where the source's "then" can be applied while the target's "when" is false - then causation neccesarily isn't fulfilled.


There are two types of causal connections:
- Entailed: This means that the source guideline's "then" necessarily entails
            the target guideline's "when".
- Suggested: This is the a specific case of "entailed", where the target’s "then" action is optional or merely recommended when the "when" condition is met, as opposed to necessary. For example, in cases such as
             source="When <X> then <Y>", target="When <W> then consider <Z>" (where <W> is caused by <Y>).

At the end of this message, you will receive a test guideline to evaluate against a set of other guidelines which are candidates for
causal connections. For each candidate, the test guideline may be found as either the source or the target in the
connection, or neither. Be forgiving regarding misspelling and grammatical errors.

Your task is to evaluate pairs of guidelines and detect which pairs fulfill such causal connections.

Please output JSON structured in the following format:

{{
    "propositions": [
        {{
            "source_id": <id of the source guideline>,
            "target_id": <id of the target guideline>,
            "source_then": <The source guideline's 'then'>,
            "target_when": <The target guideline's 'when'>,
            "is_target_when_caused_by_source_then": <BOOL>,
            "is_target_then_suggestive_or_optional": <BOOL>,
            "rationale": <Explanation for if and how the source's 'then' causes the target's 'when'. The explanation should revolve around the word 'cause' or a conjugation of it>,
            "causation_score": <Score between 1-10 indicating the strength of the connection>
        }},
        ...
    ]
}}

For each causation candidate, you should evaluate two potential propositions: one in which the test guideline is treated as the "source" and the candidate as the "target," and another in which the roles are reversed

The following are examples of expected outputs for a given input:
###
Example 1:
{{
Input:

Test guideline: ###
{{"id": 0, "when": "providing the weather update", "then": "mention whether it's likely to rain"}}
###

Causation candidates: ###
{{"id": 1, "when": "the user asked about the weather", "then": "provide the current weather update"}}
{{"id": 2, "when": "discussing whether an umbrella is needed", "then": "refer the user to our electronic store"}}
###

Expected Output:

```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "mention whether it's likely to rain",
            "target_when": "the user asked about the weather",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's mentioning the likelihood of rain does not cause the user ask about the weather retrospectively",
            "causation_score": 3
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "provide the current weather update",
            "target_when": "providing the weather update",
            "is_target_when_caused_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's providing a current weather update necessarily causes a weather update to be provided",
            "causation_score": 10
        }},
        {{
            "source_id": 0,
            "target_id": 2,
            "source_then": "mention whether it's likely to rain",
            "target_when": "discussing whether an umbrella is needed",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's mentioning the chances for rain does not retrospectively make the discussion about umbrellas",
            "causation_score": 3
        }},
        {{
            "source_id": 2,
            "target_id": 0,
            "source_then": "refer the user to our electronic store",
            "target_when": "providing the weather update",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's referring to the electronic store does not cause a weather update to be provided",
            "causation_score": 1
        }}
    ]
}}


Example 2
Input:
Test guideline: ###
{{"id": 0, "when": "The user asks for a book recommendation", "then": "suggest a book"}}
###
Causation candidates: 
###
{{"id": 1, "when": "suggesting a book", "then": "mention its availability in the local library"}}
{{"id": 2, "when": "recommending books", "then": "consider highlighting the ones with the best reviews"}}
{{"id": 3, "when": "the user greets you", "then": "greet them back with 'hello'"}}
{{"id": 4, "when": "suggesting products", "then": "check if the product is available in our store, and only offer it if it is"}}

Expected Output:
```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "suggest a book",
            "target_when": "suggesting a book",
            "is_target_when_caused_by_source_then": true,
            "rationale": "the agent's suggusting a book causes the suggestion of a book",
            "causation_score": 10
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "mention its availability in the local library",
            "target_when": "The user asks for a book recommendation",
            "is_target_when_caused_by_source_then": false,
            "rationale": "the agent's mentioning library availability does not retrospectively make the user ask for book recommendations",
            "causation_score": 1
        }},
        {{
            "source_id": 0,
            "target_id": 2,
            "source_then": "suggest a book",
            "target_when": "recommending books",
            "is_target_when_caused_by_source_then": true,
            "is_target_then_suggestive_or_optional": true,
            "rationale": "the agent's applying of 'suggest a book' causes the recommendation of books to occur",
            "causation_score": 9
        }},
        {{
            "source_id": 2,
            "target_id": 0,
            "source_then": "consider highlighting the ones with the best reviews",
            "target_when": "The user asks for a book recommendation",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's highlighting reviews does not cause the user to retrospectively ask for anything",
            "causation_score": 1
        }},
        {{
            "source_id": 0,
            "target_id": 3,
            "source_then": "suggest a book",
            "target_when": "the user greets you",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's suggesting a book does not cause the user to greet the agent retrospectively",
            "causation_score": 1
        }},
        {{
            "source_id": 3,
            "target_id": 0,
            "source_then": "greet them back with 'hello'",
            "target_when": "The user asks for a book recommendation",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's greeting the user does not cause them to ask for a book recommendation retrospectively",
            "causation_score": 1
        }},
        {{
            "source_id": 0,
            "target_id": 4,
            "source_then": "suggest a book",
            "target_when": "suggesting products",
            "is_target_when_caused_by_source_then": true,
            "is_target_then_suggestive_or_optional": true,
            "rationale": "the agent's suggesting a book, necessarily causes the suggestion of a product",
            "causation_score": 9
        }},
        {{
            "source_id": 4,
            "target_id": 0,
            "source_then": "check if the product is available in our store, and only offer it if it is'",
            "target_when": "The user asks for a book recommendation",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's checking product availability does not cause the user to ask for book recommendations retrospectively",
            "causation_score": 2
        }}
    ]
}}
```

###
Example 3
Input:
Test guideline: ###
{{"id": 0, "when": "a new topping is suggested", "then": "announce that the suggestion will be forwarded to management for consideration"}}
###
Causation candidates: ###
{{"id": 1, "when": "discussing opening hours", "then": "mention that the store closes early on Sundays"}}
{{"id": 2, "when": "the user asks for a topping we do not offer", "then": "suggest to add the topping to the menu in the future"}}
{{"id": 3, "when": "forwarding messages to management", "then": "forward the message via email"}}

Expected Output:
```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "announce that the suggestion will be forwarded to management for consideration",
            "target_when": "discussing opening hours",
            "is_target_when_caused_by_source_then": false,
            "rationale": "the agent's forwarding something to management has nothing to do with opening hours",
            "causation_score": 1
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "mention that the store closes early on Sundays",
            "target_when": "a new topping is suggested",
            "is_target_when_caused_by_source_then": false,
            "rationale": "the agent's store hours discussion does not cause any new topping suggestion to occur",
            "causation_score": 1
        }},
        {{
            "source_id": 0,
            "target_id": 2,
            "source_then": "announce that the suggestion will be forwarded to management for consideration",
            "target_when": "the user asks for a topping we do not offer",
            "is_target_when_caused_by_source_then": false,
            "rationale": "the agent's announcing something does not cause the user to have retrospectively asked about anything regarding toppings",
            "causation_score": 2
        }},
        {{
            "source_id": 2,
            "target_id": 0,
            "source_then": "suggest to add the topping to the menu in the future",
            "target_when": "a new topping is suggested",
            "is_target_when_caused_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's suggesting to add the topping to the menu is causing a new topping is being suggested",
            "causation_score": 9
        }},
        {{
            "source_id": 0,
            "target_id": 3,
            "source_then": "announce that the suggestion will be forwarded to management for consideration",
            "target_when": "forwarding messages to management",
            "is_target_when_caused_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's' announcement from the source's 'then' should cause a message to be forwarded to management",
            "causation_score": 8
        }},
        {{
            "source_id": 3,
            "target_id": 0,
            "source_then": "forward the message via email",
            "target_when": "a new topping is suggested",
            "is_target_when_caused_by_source_then": false,
            "rationale": "the agent's emailing a message is not necessarily a new topping suggestion",
            "causation_score": 2
        }}
    ]
}}

```
###
Example 4:
Input:

Test guideline: ###
{{"id": 0, "when": "Asking about our venues in New York", "then": "Reply that our largest venue is in New York"}}
###

Causation candidates: ###
{{"id": 1, "when": "Asked where our biggest venues is", "then": "Reply that it's in New York"}}
###

Expected Output:

```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "Reply that our largest venue is in New York",
            "target_when": "Asked where our biggest venues is",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "The agent's replying about our largest venue does not cause any question to be asked retrospectively",
            "causation_score": 3
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "Reply that it's in New York",
            "target_when": "Asking about our venues in New York",
            "is_target_when_caused_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "The agent's replying something to the user doesn't make them ask any questions retrospectively",
            "causation_score": 3
        }}
    ]
}}
###
Example 5:
Input:

Test guideline: ###
{{"id": 0, "when": "the user asks for something yellow", "then": "add bananas to the order"}}
###

Causation candidates: ###
{{"id": 1, "when": "the user orders bananas", "then": "compliment the user for their choice"}}
###

Expected Output:

```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "add bananas to the order",
            "target_when": "the user orders bananas",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "adding bananas to the order does not retrospectively cause the user to order bananas, even though it implies that it happened in the past",
            "causation_score": 1
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "compliment the user for their choice",
            "target_when": "the user asks for something yellow",
            "is_target_when_caused_by_source_then": true,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "complimenting the user for their choice does not retrospectively cause them to ask for anything",
            "causation_score": 3
        }}
    ]
}}
###
Example 6:
Input:

Test guideline: ###
{{"id": 0, "when": "the user asks what's the tallest building in the world", "then": "reply that it's the Burj Khalifa"}}
###

Causation candidates: ###
{{"id": 1, "when": "asked for a building that starts with a B", "then": "reply Burj Khalifa"}}
###

Expected Output:

```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "reply that it's the Burj Khalifa",
            "target_when": "asked for a building that starts with a B",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's replying 'Burj Khalifa' does not cause the user to retrospectively ask for anything, even though the user might've asked a question earlier",
            "causation_score": 3
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "reply Burj Khalifa",
            "target_when": "the user asks what's the tallest building in the world",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "the agent's replying 'Burj Khalifa' does not cause the user to retrospectively ask for anything, even though the user might've asked a question earlier",
            "causation_score": 3
        }}
    ]
}}
```

###
Example 7:
Input:

Test guideline: ###
{{"id": 0, "when": "the user requests a refund", "then": "ask the user for the date of their purchase"}}
###

Causation candidates: ###
{{"id": 1, "when": "the user mentions a past purchase", "then": "ask for the order number"}}
###

Expected Output:

```json
{{
    "propositions": [
        {{
            "source_id": 0,
            "target_id": 1,
            "source_then": "ask the user for the date of their purchase",
            "target_when": "the user mentions a past purchase",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "actions taken by the agent cannot ever cause the user to do anything",
            "causation_score": 3
        }},
        {{
            "source_id": 1,
            "target_id": 0,
            "source_then": "ask for the order number",
            "target_when": "the user requests a refund",
            "is_target_when_caused_by_source_then": false,
            "is_target_then_suggestive_or_optional": false,
            "rationale": "actions taken by the agent cannot ever cause the user to do anything",
            "causation_score": 3
        }}
    ]
}}
```
###
"""  # noqa
        )
        # Find and add terminology to prompt
        causation_candidates = "\n\t".join(
            f"{{id: {id}, when: {g.predicate}, then: {g.action}}}"
            for id, g in comparison_set.items()
        )
        test_guideline = f"{{id: 0, when: '{evaluated_guideline.predicate}', then: '{evaluated_guideline.action}'}}"
        terms = await self._terminology_store.find_relevant_terms(
            agent.id,
            query=test_guideline + causation_candidates,
        )
        builder.add_terminology(terms)

        builder.add_section(
            f"""
The guidelines you should analyze for connections are:
Test guideline: ###
{test_guideline}
###

Causation candidates: ###
{causation_candidates}
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
                score=int(p.causation_score),
                rationale=p.rationale,
            )
            for p in response.content.propositions
            if p.causation_score >= 7
        ]

        return relevant_propositions
