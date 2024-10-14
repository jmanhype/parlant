import asyncio
from datetime import datetime, timezone
from enum import Enum, auto
from itertools import chain
import json
from typing import Optional, Sequence
from more_itertools import chunked
from tenacity import retry, stop_after_attempt, wait_fixed
from dataclasses import dataclass

from emcie.server.core.common import DefaultBaseModel, ProgressReport
from emcie.server.core.engines.alpha.prompt_builder import PromptBuilder
from emcie.server.core.nlp.generation import SchematicGenerator
from emcie.server.core.guidelines import GuidelineContent
from emcie.server.core.logging import Logger
from emcie.server.core.glossary import GlossaryStore
from emcie.server.core.agents import Agent

LLM_RETRY_WAIT_TIME_SECONDS = 5.0
LLM_MAX_RETRIES = 100
EVALUATION_BATCH_SIZE = 5
CRITICAL_CONTRADICTION_THRESHOLD = 6
CONTRADICTION_SEVERITY_THRESHOLD = 6


class IncoherenceKind(Enum):
    STRICT = auto()
    CONTINGENT = auto()


class PredicatesEntailmentTestSchema(DefaultBaseModel):
    compared_guideline_id: int
    origin_guideline_when: str
    compared_guideline_when: str
    whens_entailment: bool
    rationale: str
    severity: int


class PredicatesEntailmentTestsSchema(DefaultBaseModel):
    predicate_entailments: list[PredicatesEntailmentTestSchema]


class ActionsContradictionTestSchema(DefaultBaseModel):
    compared_guideline_id: int
    origin_guideline_then: str
    compared_guideline_then: str
    thens_contradiction: bool
    rationale: str
    severity: int


class ActionsContradictionTestsSchema(DefaultBaseModel):
    action_contradictions: list[ActionsContradictionTestSchema]


@dataclass(frozen=True)
class IncoherencyTest:
    guideline_a: GuidelineContent
    guideline_b: GuidelineContent
    IncoherenceKind: IncoherenceKind
    predicates_entailment_rationale: str
    predicates_entailment_severity: int
    actions_contradiction_rationale: str
    actions_contradiction_severity: int
    creation_utc: datetime


class CoherenceChecker:
    def __init__(
        self,
        logger: Logger,
        predicates_test_schematic_generator: SchematicGenerator[PredicatesEntailmentTestsSchema],
        actions_test_schematic_generator: SchematicGenerator[ActionsContradictionTestsSchema],
        glossary_store: GlossaryStore,
    ) -> None:
        self._logger = logger
        self._predicates_entailment_checker = PredicatesEntailmentChecker(
            logger, predicates_test_schematic_generator, glossary_store
        )
        self._actions_contradiction_checker = ActionsContradictionChecker(
            logger, actions_test_schematic_generator, glossary_store
        )

    async def propose_incoherencies(
        self,
        agent: Agent,
        guidelines_to_evaluate: Sequence[GuidelineContent],
        comparison_guidelines: Sequence[GuidelineContent] = [],
        progress_report: Optional[ProgressReport] = None,
    ) -> Sequence[IncoherencyTest]:
        comparison_guidelines_list = list(comparison_guidelines)
        guidelines_to_evaluate_list = list(guidelines_to_evaluate)
        tasks = []

        for i, guideline_to_evaluate in enumerate(guidelines_to_evaluate):
            filtered_existing_guidelines = [
                g for g in guidelines_to_evaluate_list[i + 1 :] + comparison_guidelines_list
            ]
            guideline_batches = list(chunked(filtered_existing_guidelines, EVALUATION_BATCH_SIZE))
            if progress_report:
                await progress_report.stretch(len(guideline_batches))

            tasks.extend(
                [
                    asyncio.create_task(
                        self._process_proposed_guideline(
                            agent, guideline_to_evaluate, batch, progress_report
                        )
                    )
                    for batch in guideline_batches
                ]
            )
        with self._logger.operation(
            f"Evaluating contradictions for {len(tasks)} "
            f"batches (batch size={EVALUATION_BATCH_SIZE})",
        ):
            contradictions = list(chain.from_iterable(await asyncio.gather(*tasks)))

        return contradictions

    async def _process_proposed_guideline(
        self,
        agent: Agent,
        guideline_to_evaluate: GuidelineContent,
        comparison_guidelines: Sequence[GuidelineContent],
        progress_report: Optional[ProgressReport],
    ) -> Sequence[IncoherencyTest]:
        indexed_comparison_guidelines = {i: c for i, c in enumerate(comparison_guidelines, start=1)}
        predicates_entailment_responses, actions_contradiction_responses = await asyncio.gather(
            self._predicates_entailment_checker.evaluate(
                agent, guideline_to_evaluate, indexed_comparison_guidelines
            ),
            self._actions_contradiction_checker.evaluate(
                agent, guideline_to_evaluate, indexed_comparison_guidelines
            ),
        )

        contradictions = []
        for id, g in indexed_comparison_guidelines.items():
            w = [w for w in predicates_entailment_responses if w.compared_guideline_id == id][0]
            t = [t for t in actions_contradiction_responses if t.compared_guideline_id == id][0]
            if t.severity >= CONTRADICTION_SEVERITY_THRESHOLD:
                contradictions.append(
                    IncoherencyTest(
                        guideline_a=guideline_to_evaluate,
                        guideline_b=g,
                        IncoherenceKind=IncoherenceKind.STRICT
                        if w.severity >= CRITICAL_CONTRADICTION_THRESHOLD
                        else IncoherenceKind.CONTINGENT,
                        predicates_entailment_rationale=w.rationale,
                        predicates_entailment_severity=w.severity,
                        actions_contradiction_rationale=t.rationale,
                        actions_contradiction_severity=t.severity,
                        creation_utc=datetime.now(timezone.utc),
                    )
                )

        if progress_report:
            await progress_report.increment()

        return contradictions


class PredicatesEntailmentChecker:
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[PredicatesEntailmentTestsSchema],
        glossary_store: GlossaryStore,
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator
        self._glossary_store = glossary_store

    @retry(wait=wait_fixed(LLM_RETRY_WAIT_TIME_SECONDS), stop=stop_after_attempt(LLM_MAX_RETRIES))
    async def evaluate(
        self,
        agent: Agent,
        guideline_to_evaluate: GuidelineContent,
        indexed_comparison_guidelines: dict[int, GuidelineContent],
    ) -> Sequence[PredicatesEntailmentTestSchema]:
        prompt = await self._format_prompt(
            agent, guideline_to_evaluate, indexed_comparison_guidelines
        )

        response = await self._schematic_generator.generate(
            prompt=prompt,
            hints={"temperature": 0.0},
        )
        self._logger.debug(
            f"""
----------------------------------------
Predicate Entailment Test Results:
----------------------------------------
{json.dumps([p.model_dump(mode="json") for p in response.content.predicate_entailments], indent=2)}
----------------------------------------
"""
        )

        return response.content.predicate_entailments

    async def _format_prompt(
        self,
        agent: Agent,
        guideline_to_evaluate: GuidelineContent,
        indexed_comparison_guidelines: dict[int, GuidelineContent],
    ) -> str:
        builder = PromptBuilder()
        comparison_candidates_text = "\n".join(
            f"""{{"id": {id}, "when": "{g.predicate}", "then": "{g.action}"}}"""
            for id, g in indexed_comparison_guidelines.items()
        )
        guideline_to_evaluate_text = f"""{{"when": "{guideline_to_evaluate.predicate}", "then": "{guideline_to_evaluate.action}"}}"""

        builder.add_agent_identity(agent)
        builder.add_section(
            f"""
In our system, the behavior of a conversational AI agent is guided by "guidelines". The agent makes use of these guidelines whenever it interacts with a user.

Each guideline is composed of two parts:
- "when": This is a natural-language predicate that specifies when a guideline should apply.
          We look at each conversation at any particular state, and we test against this
          predicate to understand if we should have this guideline participate in generating
          the next reply to the user.
- "then": This is a natural-language instruction that should be followed by the agent
          whenever the "when" part of the guideline applies to the conversation in its particular state.
          Any instruction described here applies only to the agent, and not to the user.


Your task is to evaluate whether pairs of guidelines have entailing 'when' statements. 
Two guidelines should be detected as having entailing 'when' statements if and only if one of their 'when' statements being true entails that the other's 'when' statement is also true.
By this, if there is any context in which the 'when' statement of guideline A is false while the 'when' statement of guideline B is true - guideline B can not entail guideline A.
If one 'when' statement being true merely implies that the other 'when' statement is true, but strict entailment is not fulfilled - do not consider the 'when' statements as entailing. If one 'when' statement holding true typically means that another 'when' is true, it is not sufficient to be considered entailment.   
If entailment is fulfilled in at least one direction, consider the 'when' statements as entailing, even if the entailment is not bidirectional.

Be forgiving regarding misspellings and grammatical errors.

Please output JSON structured in the following format:
```json
{{
    "predicate_entailments": [
        {{
            "compared_guideline_id": <id of the compared guideline>,
            "origin_guideline_when": <The origin guideline's 'when'>,
            "compared_guideline_when": <The compared guideline's 'when'>,
            "whens_entailment": <BOOL of whether one of the 'when' statements entails the other>,
            "rationale": <Explanation for if and how one of the 'when' statement's entails the other>,
            "severity": <Score between 1-10 indicating the strength of the entailment>,
        }},
        ...
    ]
}}
```
The output json should have one such object for each pairing of the origin guideline with one of the compared guidelines.

The following are examples of expected outputs for a given input:
###
Example 1:
###
Input:

Test guideline: ###
{{"when": "a customer orders an electrical appliance", "then": "ship the item immediately"}}
###

Comparison candidates: ###
{{"id": 1, "when": "a customer orders a TV", "then": "wait for the manager's approval before shipping"}}
{{"id": 2, "when": "a customer orders any item", "then": "refer the user to our electronic store"}}
{{"id": 3, "when": "a customer orders a chair", "then": "reply that the product can only be delivered in-store"}}
{{"id": 4, "when": "a customer asks which discounts we offer on electrical appliances", "then": "reply that we offer free shipping for items over 100$"}}
{{"id": 5, "when": "a customer greets you", "then": "greet them back"}}

###

Expected Output:
```json
{{
    "predicate_entailments": [
        {{
            "compared_guideline_id": 1,
            "origin_guideline_when": "a customer orders an electrical appliance",
            "compared_guideline_when": "a customer orders a TV",
            "whens_entailment": true,
            "rationale": "since TVs are electronic appliances, ordering a TV entails ordering an electrical appliance",
            "severity": 9
        }},
        {{
            "compared_guideline_id": 2,
            "origin_guideline_when": "a customer orders an electrical appliance",
            "compared_guideline_when": "a customer orders any item",
            "whens_entailment": true,
            "rationale": "electrical appliances are items, so ordering an electrical appliance entails ordering an item",
            "severity": 10
        }},
        {{
            "compared_guideline_id": 3,
            "origin_guideline_when": "a customer orders an electrical appliance",
            "compared_guideline_when": "a customer orders a chair",
            "whens_entailment": false,
            "rationale": "chairs are not electrical appliances, so ordering a chair does not entail ordering an electrical appliance, nor vice-versa",
            "severity": 2
        }},
        {{
            "compared_guideline_id": 4,
            "origin_guideline_when": "a customer orders an electrical appliance",
            "compared_guideline_when": "a customer asks which discounts we offer on electrical appliances",
            "whens_entailment": false,
            "rationale": "an electrical appliance can be ordered without asking for a discount, and vice-versa, meaning that neither when statement entails the other",
            "severity": 3
        }},
        {{
            "compared_guideline_id": 5,
            "origin_guideline_when": "a customer orders an electrical appliance",
            "compared_guideline_when": "a customer greets you",
            "whens_entailment": true,
            "rationale": "a customer be greeted without ordering an electrical appliance and vice-versa, meaning that neither when statement entails the other",
            "severity": 10
        }},
    ]
}}
```

###
Example 2:
###
Input:

Test guideline: ###
{{"when": "offering products to the user", "then": "mention the price of the suggested product"}}
###

Comparison candidates: ###
{{"id": 1, "when": "suggesting a TV", "then": "mention the size of the screen"}}
{{"id": 2, "when": "the user asks for recommendations", "then": "recommend items from the sales department"}}
{{"id": 3, "when": "recommending a TV warranty plan", "then": "encourage the use to get an upgraded warranty"}}

###

Expected Output:
```json
{{
    "predicate_entailments": [
        {{
            "compared_guideline_id": 1,
            "origin_guideline_when": "offering products to the user",
            "compared_guideline_when": "suggesting a TV",
            "whens_entailment": true,
            "rationale": "by suggesting a TV, a product is offered to the user, so suggesting a TV entails offering a product",
            "severity": 9
        }},
        {{
            "compared_guideline_id": 2,
            "origin_guideline_when": "offering products to the user",
            "compared_guideline_when": "the user asks for recommendations",
            "whens_entailment": false,
            "rationale": "the user asking for recommendations does not entail that a product is offered to them. On the other direction, offering products to the user does not necessarily mean that they asked for recommendations, even though it is implied",
            "severity": 4
        }},
        {{
            "compared_guideline_id": 3,
            "origin_guideline_when": "offering products to the user",
            "compared_guideline_when": "recommending a TV warranty plan",
            "whens_entailment": true,
            "rationale": "when a TV warranty plan is recommended, a product (the warranty) is offered to the user, so recommending a TV warranty plan entails offering a product",
            "severity": 8
        }},
        
    ]
}}
```
###
            """  # noqa
        )

        terms = await self._glossary_store.find_relevant_terms(
            agent.id,
            query=guideline_to_evaluate_text + comparison_candidates_text,
        )
        builder.add_glossary(terms)

        builder.add_section(f"""
The guidelines you should analyze for entailments are:
Origin guideline: ###
{guideline_to_evaluate_text}
###

Comparison candidates: ###
{comparison_candidates_text}
###""")
        return builder.build()


class ActionsContradictionChecker:
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[ActionsContradictionTestsSchema],
        glossary_store: GlossaryStore,
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator
        self._glossary_store = glossary_store

    @retry(wait=wait_fixed(LLM_RETRY_WAIT_TIME_SECONDS), stop=stop_after_attempt(LLM_MAX_RETRIES))
    async def evaluate(
        self,
        agent: Agent,
        guideline_to_evaluate: GuidelineContent,
        indexed_comparison_guidelines: dict[int, GuidelineContent],
    ) -> Sequence[ActionsContradictionTestSchema]:
        prompt = await self._format_prompt(
            agent, guideline_to_evaluate, indexed_comparison_guidelines
        )
        response = await self._schematic_generator.generate(
            prompt=prompt,
            hints={"temperature": 0.0},
        )
        self._logger.debug(
            f"""
----------------------------------------
Action Contradiction Test Results:
----------------------------------------
{json.dumps([p.model_dump(mode="json") for p in response.content.action_contradictions], indent=2)}
----------------------------------------
"""
        )

        return response.content.action_contradictions

    async def _format_prompt(
        self,
        agent: Agent,
        guideline_to_evaluate: GuidelineContent,
        indexed_comparison_guidelines: dict[int, GuidelineContent],
    ) -> str:
        builder = PromptBuilder()
        comparison_candidates_text = "\n".join(
            f"""{{"id": {id}, "when": "{g.predicate}", "then": "{g.action}"}}"""
            for id, g in indexed_comparison_guidelines.items()
        )
        guideline_to_evaluate_text = f"""{{"when": "{guideline_to_evaluate.predicate}", "then": "{guideline_to_evaluate.action}"}}"""

        builder.add_agent_identity(agent)
        builder.add_section(
            f"""
In our system, the behavior of a conversational AI agent is guided by "guidelines". The agent makes use of these guidelines whenever it interacts with a user.

Each guideline is composed of two parts:
- "when": This is a natural-language predicate that specifies when a guideline should apply.
          We look at each conversation at any particular state, and we test against this
          predicate to understand if we should have this guideline participate in generating
          the next reply to the user.
- "then": This is a natural-language instruction that should be followed by the agent
          whenever the "when" part of the guideline applies to the conversation in its particular state.
          Any instruction described here applies only to the agent, and not to the user.

To ensure consistency, it is crucial to avoid scenarios where multiple guidelines with conflicting 'then' statements are applied. Your task is to assess whether pairs of guidelines contain contradictory 'then' statements. Two 'then' statements are considered contradictory if:

1. Applying both results in an illogical or contradictory action.
2. Applying both leads to a confusing or paradoxical response.
3. Applying both would result in the agent taking an action that does not align with the response it should provide to the user.

While your evaluation should focus on the 'then' statements, remember that each 'then' statement is contextualized by its corresponding 'when' statement. Analyze each 'then' statement within the context provided by its "when" condition. Please be lenient with any misspellings or grammatical errors.
          
Be forgiving regarding misspellings and grammatical errors.
 


Please output JSON structured in the following format:
```json
{{
    "action_contradictions": [
        {{
            "compared_guideline_id": <id of the compared guideline>,
            "origin_guideline_then": <The origin guideline's 'then'>,
            "compared_guideline_then": <The compared guideline's 'then'>,
            "thens_contradiction": <BOOL of whether the two 'then' statements are contradictory>,
            "rationale": <Explanation for if and how the 'then' statements contradict each other>,
            "severity": <Score between 1-10 indicating the strength of the contradiction>
        }},
        ...
    ]
}}
```
The output json should have one such object for each pairing of the origin guideline with one of the compared guidelines.

The following are examples of expected outputs for a given input:
###
Example 1:
###
Input:

Test guideline: ###
{{"when": "a customer orders an electrical appliance", "then": "ship the item immediately"}}
###

Comparison candidates: ###
{{"id": 1, "when": "a customer orders a TV", "then": "wait for the manager's approval before shipping"}}
{{"id": 2, "when": "a customer orders any item", "then": "refer the user to our electronic store"}}
{{"id": 3, "when": "a customer orders a chair", "then": "reply that the product can only be delivered in-store"}}
{{"id": 4, "when": "a customer asks which discounts we offer on electrical appliances", "then": "reply that we offer free shipping for items over 100$"}}
{{"id": 5, "when": "a customer greets you", "then": "greet them back"}}

###

Expected Output:
```json
{{
    "action_contradictions": [
        {{
            "compared_guideline_id": 1,
            "origin_guideline_then": "ship the item immediately",
            "compared_guideline_then": "wait for the manager's approval before shipping",
            "thens_contradiction": true,
            "rationale": "shipping the item immediately contradicts waiting for the manager's approval",
            "severity": 10
        }},
        {{
            "compared_guideline_id": 2,
            "origin_guideline_then": "ship the item immediately",
            "compared_guideline_then": "refer the user to our electronic store",
            "thens_contradiction": false,
            "rationale": "the agent can both ship the item immediately and refer the user to the electronic store at the same time, the actions are not contradictory",
            "severity": 2
        }},
        {{
            "compared_guideline_id": 3,
            "origin_guideline_then": "ship the item immediately",
            "compared_guideline_then": "reply that the product can only be delivered in-store",
            "thens_contradiction": true,
            "rationale": "shipping the item immediately contradicts the reply that the product can only be delivered in-store",
            "severity": 9
        }},
        {{
            "compared_guideline_id": 4,
            "origin_guideline_then": "ship the item immediately",
            "compared_guideline_then": "reply that we offer free shipping for items over 100$",
            "thens_contradiction": false,
            "rationale": "replying that we offer free shipping for expensive items does not contradict shipping an item immediately, both actions can be taken simultaneously",
            "severity": 1
        }},
        {{
            "compared_guideline_id": 5,
            "origin_guideline_then": "ship the item immediately",
            "compared_guideline_then": "greet them back",
            "thens_contradiction": false,
            "rationale": "shipping the item immediately can be done while also greeting the customer, both actions can be taken simultaneously",
            "severity": 1
        }},
    ]
}}
```

###
Example 2:
###
Input:

Test guideline: ###
{{"when": "the user mentions health issues", "then": "register them to the 5km race"}}
###

Comparison candidates: ###
{{"id": 1, "when": "the user asks about registering available races", "then": "Reply that you can register them either to the 5km or the 10km race"}}
{{"id": 2, "when": "the user wishes to register to a race without being verified", "then": "Inform them that they cannot register to races without verification"}}
###

Expected Output:
```json
{{
    "action_contradictions": [
        {{
            "compared_guideline_id": 1,
            "origin_guideline_then": "register them to the 5km race",
            "compared_guideline_then": "Reply that you can register them either to the 5km or the 10km race",
            "thens_contradiction": true,
            "rationale": "allowing the user to select from the multiple options for races, while already registering them to the 5km race is contradictory, as it ascribes an action that doesn't align with the agent's response",
            "severity": 7
        }},
        {{
            "compared_guideline_id": 2,
            "origin_guideline_then": "register them to the 5km race",
            "compared_guideline_then": "Inform them that they cannot register to races without verification",
            "thens_contradiction": true,
            "rationale": "Informing the user that they cannot register to races while registering them to a race is contradictory - the action does not align with the agent's response",
            "severity": 8
        }},
        
    ]
}}
```

###"""  # noqa
        )

        terms = await self._glossary_store.find_relevant_terms(
            agent.id,
            query=guideline_to_evaluate_text + comparison_candidates_text,
        )
        builder.add_glossary(terms)

        builder.add_section(f"""
The guidelines you should analyze for entailments are:
Origin guideline: ###
{guideline_to_evaluate_text}
###

Comparison candidates: ###
{comparison_candidates_text}
###""")
        return builder.build()
