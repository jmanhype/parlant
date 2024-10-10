import asyncio
from dataclasses import dataclass

from datetime import datetime, timezone
from enum import Enum, auto
from itertools import chain
import json
from typing import Optional, Sequence
from more_itertools import chunked
from tenacity import retry, stop_after_attempt, wait_fixed

from emcie.server.core.common import DefaultBaseModel, ProgressReport
from emcie.server.core.engines.alpha.prompt_builder import PromptBuilder
from emcie.server.core.nlp.generation import SchematicGenerator
from emcie.server.core.guidelines import GuidelineContent
from emcie.server.core.logging import Logger
from emcie.server.core.terminology import TerminologyStore
from emcie.server.core.agents import Agent

LLM_RETRY_WAIT_TIME_SECONDS = 3.5
LLM_MAX_RETRIES = 100
EVALUATION_BATCH_SIZE = 5
CRITICAL_CONTRADICTION_THRESHOLD = 7
CONTRADICTION_SEVERITY_THRESHOLD = 7


class IncoherenceKind(Enum):
    STRICT = auto()
    CONTINGENT = auto()


class PredicatesEntailmentTestSchema(DefaultBaseModel):
    compared_guideline_id: int
    origin_guideline_when: str
    compared_guideline_when: str
    whens_entailment: bool
    severity: int
    rationale: str


class PredicatesEntailmentTestsSchema(DefaultBaseModel):
    predicate_entailments: list[PredicatesEntailmentTestSchema]


class ActionsContradictionTestSchema(DefaultBaseModel):
    compared_guideline_id: int
    origin_guideline_then: str
    compared_guideline_then: str
    thens_contradiction: bool
    severity: int
    rationale: str


class ActionsContradictionTestsSchema(DefaultBaseModel):
    action_contradictions: list[ActionsContradictionTestSchema]


@dataclass(frozen=True)
class ContradictionTestSchema:
    compared_guideline_id: int
    thens_contradiction: bool
    thens_contradiction_severity: int
    thens_contradiction_rationale: str
    whens_entailment: bool
    whens_entailment_severity: int
    whens_entailement_rationale: str


class ContradictionTest(
    DefaultBaseModel
):  # TODO change to predicate, action language here and upstream
    guideline_a: GuidelineContent
    guideline_b: GuidelineContent
    ContradictionKind: IncoherenceKind
    whens_entailment_severity: int
    whens_entailement_rationale: str
    thens_contradiction_severity: int
    thens_contradiction_rationale: str
    creation_utc: datetime


class CoherenceChecker:
    def __init__(
        self,
        logger: Logger,
        predicates_test_schematic_generator: SchematicGenerator[PredicatesEntailmentTestsSchema],
        actions_test_schematic_generator: SchematicGenerator[ActionsContradictionTestsSchema],
        terminology_store: TerminologyStore,
    ) -> None:
        self._logger = logger
        self._predicates_entailment_checker = PredicatesEntailmentChecker(
            logger, predicates_test_schematic_generator, terminology_store
        )
        self._actions_contradiction_checker = ActionsContradictionChecker(
            logger, actions_test_schematic_generator, terminology_store
        )

    async def propose_incoherencies(
        self,
        agent: Agent,
        guidelines_to_evaluate: Sequence[GuidelineContent],
        comparison_guidelines: Sequence[GuidelineContent] = [],
        progress_report: Optional[ProgressReport] = None,
    ) -> Sequence[ContradictionTest]:
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
    ) -> Sequence[ContradictionTest]:
        indexed_comparison_guidelines = {i: c for i, c in enumerate(comparison_guidelines, start=1)}
        predicates_entailment_reponses, actions_contradiction_reponses = await asyncio.gather(
            self._predicates_entailment_checker.evaluate(
                agent, guideline_to_evaluate, indexed_comparison_guidelines
            ),
            self._actions_contradiction_checker.evaluate(
                agent, guideline_to_evaluate, indexed_comparison_guidelines
            ),
        )

        contradictions = []
        for id, g in indexed_comparison_guidelines.items():
            w = [w for w in predicates_entailment_reponses if w.compared_guideline_id == id][0]
            t = [t for t in actions_contradiction_reponses if t.compared_guideline_id == id][0]
            if t.severity > CONTRADICTION_SEVERITY_THRESHOLD:
                contradictions.append(
                    ContradictionTest(
                        guideline_a=guideline_to_evaluate,
                        guideline_b=g,
                        ContradictionKind=IncoherenceKind.STRICT
                        if w.severity >= CRITICAL_CONTRADICTION_THRESHOLD
                        else IncoherenceKind.CONTINGENT,
                        whens_entailment_severity=w.severity,
                        whens_entailement_rationale=w.rationale,
                        thens_contradiction_severity=t.severity,
                        thens_contradiction_rationale=t.rationale,
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
        terminology_store: TerminologyStore,
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator
        self._terminology_store = terminology_store

    #    @retry(wait=wait_fixed(LLM_RETRY_WAIT_TIME_SECONDS), stop=stop_after_attempt(LLM_MAX_RETRIES))
    async def evaluate(  # TODO write
        self,
        agent: Agent,
        guideline_to_evaluate: GuidelineContent,
        indexed_comparison_guidelines: dict[int, GuidelineContent],
    ) -> Sequence[PredicatesEntailmentTestSchema]:
        prompt = await self._format_prompt(
            agent, guideline_to_evaluate, indexed_comparison_guidelines
        )
        with open("predicate entailment prompt.txt", "w", encoding="utf-8") as file:
            file.write(prompt)
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
    ) -> str:  # TODO write
        builder = PromptBuilder()
        comparison_candidates_text = "\n\t".join(
            f"{{id: {id}, when: {g.predicate}, then: {g.action}}}"
            for id, g in indexed_comparison_guidelines.items()
        )
        guideline_to_evaluate_text = (
            f"{{when: {guideline_to_evaluate.predicate}, then: {guideline_to_evaluate.action}}}"
        )

        builder.add_agent_identity(
            agent
        )  # TODO ask dor about where this should be placed for prompt caching
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
Two guidelines should be detected as having entailing 'when' statements if and only if one of their 'when' statements being true must mean that the other's 'when' statement is true.
By this, if there is any context in which the 'when' statement of guideline A is false while the 'when' statement of guideline B is true - guideline B can not entail guideline A. 
The entailment might be in either direction - for guidelines A and B, identify them as having entailing 'when' statements if either the 'when' of A entails the when of 'b', or if the 'when' of B entails the 'when' of A.
If two guidelines have equivalent 'when' statements, meaning that they both entail each other - then identify the guidelines as having entailing 'when's. 

Please output JSON structured in the following format:
```json
{{
    "predicate_entailments": [
        {{
            "compared_guideline_id": <id of the compared guideline>
            "origin_guideline_when": <The origin guideline's 'when'>
            "compared_guideline_when": <The compared guideline's 'when'>
            "whens_entailment": <BOOL of whether one of the 'when' statements entails the other>
            "severity": <Score between 1-10 indicating the strength of the entailment>
            "rationale": <Explanation for if and how one of the 'when' statement's entails the other>
        }},
        ...
    ]
}}
```
The output json should have one such object for each pairing of the origin guideline with one of the compared guidelines.

The following are examples of expected outputs for a given input:
###
Example 1:
{{
Input:

Test guideline: ###
{{"when": "a customer orders an electrical appliance", "then": "ship the item immediately"}}
###

Comparison candidates: ###
{{"id": 1, "when": "a customer orders a TV", "then": "wait for the manager's approval before shipping"}}
{{"id": 2, "when": "a costumer orders any item", "then": "refer the user to our electronic store"}}
{{"id": 3, "when": "a customer orders a chair", "then": "reply that the product can only be delivered in-store"}}
{{"id": 4, "when": "a customer asks which discounts we offer on electrical appliances", "then": "reply that we offer free shipping for items over 100$"}}
{{"id": 5, "when": "a customer greets you", "then": "greet them back"}}

###

Expected Output:
```json
{{
    "predicate_entailments": [
        {{
            "compared_guideline_id": 1
            "origin_guideline_when": "a customer orders an electrical appliance"
            "compared_guideline_when": "a customer orders a TV"
            "whens_entailment": True
            "severity": 10
            "rationale": "since TVs are electronic appliances, ordering a TV entails ordering an electrical appliance"
        }},
        {{
            "compared_guideline_id": 2
            "origin_guideline_when": "a customer orders an electrical appliance"
            "compared_guideline_when": "a costumer orders any item"
            "whens_entailment": True
            "severity": 10
            "rationale": "electrical appliances are items, so ordering an electrical appliance entails ordering an item"
        }},
        {{
            "compared_guideline_id": 3
            "origin_guideline_when": "a customer orders an electrical appliance"
            "compared_guideline_when": "a customer orders a chair"
            "whens_entailment": False
            "severity": 2
            "rationale": "chairs are not electrical appliances, so ordering a chair does not entail ordering an electrical appliance, nor vice-versa"
        }},
        {{
            "compared_guideline_id": 4
            "origin_guideline_when": "a customer orders an electrical appliance"
            "compared_guideline_when": "a customer asks which discounts we offer on electrical appliances"
            "whens_entailment": False
            "severity": 3
            "rationale": "an electrical appliance can be ordered without asking for a discount, and vice-versa, meaning that neither when statement entails the other"
        }},
        {{
            "compared_guideline_id": 5
            "origin_guideline_when": "a customer orders an electrical appliance"
            "compared_guideline_when": "a customer greets you"
            "whens_entailment": True
            "severity": 10
            "rationale": "a customer be greeted without ordering an electrical appliance and vice-versa, meaning that neither when statement entails the other"
        }},
    ]
}}
```
            """  # noqa
        )

        terms = await self._terminology_store.find_relevant_terms(
            agent.id,
            query=guideline_to_evaluate_text + comparison_candidates_text,
        )
        builder.add_terminology(terms)

        builder.add_section(f"""
The guidelines you should analyze for entailments are:
Origin guideline: ###
{guideline_to_evaluate_text}
###

Comparison candidates: ###
{comparison_candidates_text}
###""")
        builder.add_section(  # output format
            f"""

                            """  # noqa
        )
        return builder.build()


class ActionsContradictionChecker:
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[ActionsContradictionTestsSchema],
        terminology_store: TerminologyStore,
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator
        self._terminology_store = terminology_store

    # @retry(wait=wait_fixed(LLM_RETRY_WAIT_TIME_SECONDS), stop=stop_after_attempt(LLM_MAX_RETRIES))
    async def evaluate(
        self,
        agent: Agent,
        guideline_to_evaluate: GuidelineContent,
        indexed_comparison_guidelines: dict[int, GuidelineContent],
    ) -> Sequence[ActionsContradictionTestSchema]:
        prompt = await self._format_prompt(
            agent, guideline_to_evaluate, indexed_comparison_guidelines
        )
        with open("action contradiction prompt.txt", "w", encoding="utf-8") as file:
            file.write(prompt)
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
        comparison_candidates_text = "\n\t".join(
            f"{{id: {id}, when: {g.predicate}, then: {g.action}}}"
            for id, g in indexed_comparison_guidelines.items()
        )
        guideline_to_evaluate_text = (
            f"{{when: {guideline_to_evaluate.predicate}, then: {guideline_to_evaluate.action}}}"
        )

        builder.add_agent_identity(
            agent
        )  # TODO ask dor about where this should be placed for prompt caching
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


To maintain consistency, we must avoid cases where multiple guidelines with contradictory 'then' statements are applied.

Your role is to evaluate whether pairs of guideline have contradictory 'then' statements. Two 'then' statements should be detected as contradictory
if and only if applying them both simultaneously would be illogical, or would result in an incoherent action / response. 
While your determination should depend solely on the guidelines' 'then' statements, note that each 'then' statement might be contextualized by its respective 'then' statement.
Therefore, to find whether two guidelines have contradictory 'then' statements, begin by understanding each guideline's 'then' statement, through the context of their respective 'when's, and then evaluate whether applying them simultaneously would be contradictory. 

Please output JSON structured in the following format:
```json
{{
    "action_contradictions": [
        {{
            "compared_guideline_id": <id of the compared guideline>
            "origin_guideline_then": <The origin guideline's 'then'>
            "compared_guideline_then": <The compared guideline's 'then'>
            "thens_contradiction": <BOOL of whether the two 'then' statements are contradictory>
            "severity": <Score between 1-10 indicating the strength of the contradiction>
            "rationale": <Explanation for if and how the 'then' statements contradict each other>
        }},
        ...
    ]
}}
```
The output json should have one such object for each pairing of the origin guideline with one of the compared guidelines.

The following are examples of expected outputs for a given input:
###
Example 1:
{{
Input:

Test guideline: ###
{{"when": "a customer orders an electrical appliance", "then": "ship the item immediately"}}
###

Comparison candidates: ###
{{"id": 1, "when": "a customer orders a TV", "then": "wait for the manager's approval before shipping"}}
{{"id": 2, "when": "a costumer orders any item", "then": "refer the user to our electronic store"}}
{{"id": 3, "when": "a customer orders a chair", "then": "reply that the product can only be delivered in-store"}}
{{"id": 4, "when": "a customer asks which discounts we offer on electrical appliances", "then": "reply that we offer free shipping for items over 100$"}}
{{"id": 5, "when": "a customer greets you", "then": "greet them back"}}

###

Expected Output:
```json
{{
    "action_contradictions": [
        {{
            "compared_guideline_id": 1
            "origin_guideline_then": "ship the item immediately"
            "compared_guideline_then": "wait for the manager's approval before shipping"
            "thens_contradiction": True
            "severity": 10
            "rationale": "shipping the item immediately contradicts waiting for the manager's approval"
        }},
        {{
            "compared_guideline_id": 2
            "origin_guideline_then": "ship the item immediately"
            "compared_guideline_then": "refer the user to our electronic store"
            "thens_contradiction": False
            "severity": 2
            "rationale": "the agent can both ship the item immediately and refer the user to the electronic store at the same time, the actions are not contradictory"
        }},
        {{
            "compared_guideline_id": 3
            "origin_guideline_then": "ship the item immediately"
            "compared_guideline_then": "reply that the product can only be delivered in-store"
            "thens_contradiction": True
            "severity": 9
            "rationale": "shipping the item immediately contradicts the reply that the product can only be delivered in-store"
        }},
        {{
            "compared_guideline_id": 4
            "origin_guideline_then": "ship the item immediately"
            "compared_guideline_then": "reply that we offer free shipping for items over 100$"
            "thens_contradiction": False
            "severity": 1
            "rationale": "replying that we offer free shipping for expensive items does not contradict shipping an item immediately, both actions can be taken simultaneously"
        }},
        {{
            "compared_guideline_id": 5
            "origin_guideline_then": "ship the item immediately"
            "compared_guideline_then": "greet them back"
            "thens_contradiction": True
            "severity": 1
            "rationale": "shipping the item immediately can be done while also greeting the customer, both actions can be taken simultaneously"
        }},
    ]
}}
```
            """  # noqa
        )

        terms = await self._terminology_store.find_relevant_terms(
            agent.id,
            query=guideline_to_evaluate_text + comparison_candidates_text,
        )
        builder.add_terminology(terms)

        builder.add_section(f"""
The guidelines you should analyze for entailments are:
Origin guideline: ###
{guideline_to_evaluate_text}
###

Comparison candidates: ###
{comparison_candidates_text}
###""")
        builder.add_section(  # output format
            f"""

                                """  # noqa
        )
        return builder.build()
