from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
from enum import Enum
from itertools import chain
import json
from typing import Iterable, NewType
from more_itertools import chunked
from tenacity import retry, stop_after_attempt, wait_fixed

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.guidelines import Guideline, GuidelineId
from emcie.server.engines.alpha.utils import duration_logger, make_llm_client

CoherenceContradictionId = NewType("CoherenceContradictionId", str)

LLM_RETRY_WAIT_TIME_SECONDS = 3.5
LLM_MAX_RETRIES = 100
EVALUATION_BATCH_SIZE = 5


class ContradictionType(Enum):
    HIERARCHICAL = "Hierarchical Contradiction"
    PARALLEL = "Parallel Contradiction"
    TEMPORAL = "Temporal Contradiction"
    CONTEXTUAL = "Contextual Contradiction"


class ContradictionTest(DefaultBaseModel):
    contradiction_type: ContradictionType
    existing_guideline_id: GuidelineId
    proposed_guideline_id: GuidelineId
    severity: int
    rationale: str
    creation_utc: datetime


def _filter_unique_contradictions(
    contradictions: Iterable[ContradictionTest],
) -> Iterable[ContradictionTest]:
    """
    Filter unique contradictions based on the combination of existing and proposed guidelines.

    Args:
        contradictions: Iterable of Contradiction objects to filter.

    Returns:
        Iterable of unique Contradiction objects.
    """

    def _generate_key(g1_id: GuidelineId, g2_id: GuidelineId) -> tuple[GuidelineId, GuidelineId]:
        _sorted_guidelines_tuple = tuple(sorted((g1_id, g2_id)))
        return _sorted_guidelines_tuple  # type: ignore

    seen_keys = set()
    unique_contradictions = []
    for contradiction in contradictions:
        key = _generate_key(
            contradiction.existing_guideline_id, contradiction.proposed_guideline_id
        )
        if key not in seen_keys:
            seen_keys.add(key)
            unique_contradictions.append(contradiction)
    return unique_contradictions


class ContradictionEvaluator(ABC):
    @abstractmethod
    async def evaluate(
        self,
        proposed_guidelines: Iterable[Guideline],
        existing_guidelines: Iterable[Guideline] = [],
    ) -> Iterable[ContradictionTest]: ...


class ContradictionEvaluatorBase(ABC):
    def __init__(
        self,
        contradiction_type: ContradictionType,
    ) -> None:
        self._llm_client = make_llm_client("openai")
        self.contradiction_type = contradiction_type
        self.contradiction_response_outcome_key = (
            f'{self.contradiction_type.value.replace(" ", "_").lower()}s'
        )

    async def evaluate(
        self,
        proposed_guidelines: Iterable[Guideline],
        existing_guidelines: Iterable[Guideline] = [],
    ) -> Iterable[ContradictionTest]:
        existing_guideline_list = list(existing_guidelines)
        proposed_guidelines_list = list(proposed_guidelines)
        tasks = []

        for i, proposed_guideline in enumerate(proposed_guidelines):
            filtered_existing_guidelines = [
                g for g in proposed_guidelines_list[i + 1 :] + existing_guideline_list
            ]
            guideline_batches = chunked(filtered_existing_guidelines, EVALUATION_BATCH_SIZE)
            tasks.extend(
                [
                    asyncio.create_task(self._process_proposed_guideline(proposed_guideline, batch))
                    for batch in guideline_batches
                ]
            )
        with duration_logger(
            f"Evaluating {self.contradiction_type} for {len(tasks)} "
            f"batches (batch size={EVALUATION_BATCH_SIZE})"
        ):
            contradictions = chain.from_iterable(await asyncio.gather(*tasks))

        distinct_contradictions = _filter_unique_contradictions(contradictions)
        return distinct_contradictions

    async def _process_proposed_guideline(
        self,
        proposed_guideline: Guideline,
        existing_guidelines: Iterable[Guideline],
    ) -> Iterable[ContradictionTest]:
        prompt = self._format_contradiction_prompt(
            proposed_guideline,
            list(existing_guidelines),
        )
        contradictions = await self._generate_contradictions(prompt)
        return contradictions

    @abstractmethod
    def _format_contradiction_type_definition(self) -> str: ...

    @abstractmethod
    def _format_contradiction_type_examples(self) -> str: ...

    def _format_contradiction_prompt(
        self,
        proposed_guideline: Guideline,
        existing_guidelines: list[Guideline],
    ) -> str:
        existing_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(existing_guidelines, start=1)
        )
        proposed_guideline_string = (
            f"{{id: {proposed_guideline.id}, "
            f"guideline: When {proposed_guideline.predicate}, then {proposed_guideline.content}}}"
        )
        result_structure = [
            {
                "existing_guideline_id": g.id,
                "proposed_guideline_id": proposed_guideline.id,
                "severity_level": "<Severity Level (1-10): Indicates the intensity "
                "of the contradiction arising from overlapping conditions>",
                "rationale": "<Brief explanation of why the two guidelines have "
                f"a {self.contradiction_type.value}>",
            }
            for g in existing_guidelines
        ]
        return f"""
### Definition of {self.contradiction_type.value}:

{self._format_contradiction_type_definition()}

**Objective**: Evaluate potential {self.contradiction_type.value}s between the set of existing guidelines and the proposed guideline.

**Task Description**:
1. **Input**:
   - Existing Guidelines: ###
   {existing_guidelines_string}
   ###
    - Proposed Guidelines:###
   {proposed_guideline_string}
   ###

2. **Process**:
   - Compare each of the {len(existing_guidelines)} existing guidelines with the proposed guideline.
   - Determine if there is a {self.contradiction_type.value}, where the proposed guideline is more specific and directly contradicts a more general guideline from the existing set.
   - If no contradiction is detected, set the severity_level to 1 to indicate minimal or no contradiction.

3. **Output**:
   - A list of results, each item detailing a potential contradiction, structured as follows:
     ```json
     {{
         "{self.contradiction_response_outcome_key}":
            {result_structure}
     }}
     ```

### Examples of Evaluations:

{self._format_contradiction_type_examples()}
"""  # noqa

    @retry(wait=wait_fixed(LLM_RETRY_WAIT_TIME_SECONDS), stop=stop_after_attempt(LLM_MAX_RETRIES))
    async def _generate_contradictions(
        self,
        prompt: str,
    ) -> Iterable[ContradictionTest]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)[self.contradiction_response_outcome_key]

        contradictions = [
            ContradictionTest(
                contradiction_type=self.contradiction_type,
                existing_guideline_id=json_contradiction["existing_guideline_id"],
                proposed_guideline_id=json_contradiction["proposed_guideline_id"],
                severity=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
                creation_utc=datetime.now(timezone.utc),
            )
            for json_contradiction in json_content
        ]

        return contradictions


class HierarchicalContradictionEvaluator(ContradictionEvaluatorBase):
    def __init__(self) -> None:
        super().__init__(ContradictionType.HIERARCHICAL)

    def _format_contradiction_type_definition(self) -> str:
        return """
Hierarchical Coherence Contradiction arises when there are multiple layers of guidelines, with one being more specific or detailed than the other.
This type of Contradiction occurs when the application of a general guideline is contradicted by a more specific guideline under certain conditions, leading to inconsistencies in decision-making.
"""  # noqa

    def _format_contradiction_type_examples(self) -> str:
        return f"""
#### Example #1:
- **Foundational Guideline**: {{"id": 3, "guideline": "When a customer orders any item, Then prioritize shipping based on customer loyalty level."}}
- **Proposed Guideline**: {{"id": 4, "guideline": "When a customer orders a high-demand item, Then ship immediately, regardless of loyalty level."}}
- **Expected Result**:
     ```json
     {{
         "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "3",
                 "proposed_guideline_id": "4",
                 "severity_level": 9,
                 "rationale": "The guideline to immediately ship high-demand items directly contradicts the broader policy of prioritizing based on loyalty, leading to a situation where the specific scenario of high-demand items undermines the general loyalty prioritization."
             }}
         ]
     }}
     ```

#### Example #2:
- **Foundational Guideline**: {{"id": 1, "guideline": "When an employee qualifies for any reward, Then distribute rewards based on standard performance metrics."}}
- **Proposed Guideline**: {{"id": 2, "guideline": "When an employee excels in a critical project, Then offer additional rewards beyond standard metrics."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "1",
                 "proposed_guideline_id": "2",
                 "severity_level": 8,
                 "rationale": "The policy to give additional rewards for critical project performance contradicts the general policy of standard performance metrics, creating a Contradiction where a specific achievement overlaps and supersedes the general reward system."
             }}
         ]
     }}
     ```

#### Example #3:
- **Foundational Guideline**: {{"id": 5, "guideline": "When a customer subscribes to a yearly plan, Then offer a 10% discount on the subscription fee."}}
- **Proposed Guideline**: {{"id": 6, "guideline": "When a customer subscribes to any plan during a promotional period, Then offer an additional 5% discount on the subscription fee."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "5",
                 "proposed_guideline_id": "6",
                 "severity_level": 1,
                 "rationale": "The policies to offer discounts for yearly subscriptions and additional discounts during promotional periods complement each other rather than contradict. Both discounts can be applied simultaneously without undermining one another, enhancing the overall attractiveness of the subscription offers during promotions."
             }}
         ]
     }}
     ```

#### Example #4:
- **Foundational Guideline**: {{"id": 7, "guideline": "When there is a software update, Then deploy it within 48 hours."}}
- **Proposed Guideline**: {{"id": 8, "guideline": "When a software update includes major changes affecting user interfaces, Then delay deployment for additional user training."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "7",
                 "proposed_guideline_id": "8",
                 "severity_level": 9,
                 "rationale": "The requirement for additional training for major UI changes contradicts the general guideline of rapid deployment for security updates, showing how a specific feature of an update (UI changes) can override a general security protocol."
             }}
         ]
     }}
     ```
        """  # noqa


class ParallelContradictionEvaluator(ContradictionEvaluatorBase):

    def __init__(self) -> None:
        super().__init__(ContradictionType.PARALLEL)

    def _format_contradiction_type_definition(self) -> str:
        return """
Parallel Contradiction occurs when two guidelines of equal specificity lead to contradictory actions.
This happens when conditions for both guidelines are met simultaneously, without a clear resolution mechanism to prioritize one over the other.
"""  # noqa

    def _format_contradiction_type_examples(self) -> str:
        return f"""#### Example #1:
- **Existing Guideline**: {{"id": 1, "guideline": "When a customer returns an item within 30 days, Then issue a full refund."}}
- **Proposed Guideline**: {{"id": 2, "guideline": "When the returned item is a special order, Then do not offer refunds."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "1",
                 "proposed_guideline_id": "2",
                 "severity_level": 9,
                 "rationale": "Both guidelines apply when a special order item is returned within 30 days, leading to confusion over whether to issue a refund or deny it based on the special order status."
             }}
         ]
     }}
     ```

#### Example #2:
- **Existing Guideline**: {{"id": 3, "guideline": "When a project deadline is imminent, Then allocate all available resources to complete the project."}}
- **Proposed Guideline**: {{"id": 4, "guideline": "When multiple projects are nearing deadlines at the same time, Then distribute resources equally among projects."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "3",
                 "proposed_guideline_id": "4",
                 "severity_level": 8,
                 "rationale": "The requirement to focus all resources on a single project contradicts the need to distribute resources equally when multiple projects are due, creating a decision-making deadlock without a clear priority directive."
             }}
         ]
     }}
     ```

#### Example #3:
- **Existing Guideline**: {{"id": 5, "guideline": "When an employee requests flexible working hours, Then approve to support work-life balance."}}
- **Proposed Guideline**: {{"id": 6, "guideline": "When team collaboration is essential, Then require standard working hours for all team members."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "5",
                 "proposed_guideline_id": "6",
                 "severity_level": 7,
                 "rationale": "The policy to accommodate flexible working hours contradicts the requirement for standard hours to enhance team collaboration, creating a scenario where both policies are justified but contradictory."
             }}
         ]
     }}
     ```

#### Example #4:
- **Existing Guideline**: {{"id": 7, "guideline": "When a customer inquires about product features, Then provide detailed information and recommendations based on their needs."}}
- **Proposed Guideline**: {{"id": 8, "guideline": "When a customer asks about compatibility with other products, Then offer guidance on compatible products and configurations."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "7",
                 "proposed_guideline_id": "8",
                 "severity_level": 1,
                 "rationale": "The guidelines address different aspects of customer inquiries without contradiction. One provides general product information, while the other focuses specifically on compatibility issues, allowing both guidelines to operate simultaneously without contradiction."
             }}
         ]
     }}
     ```
        """  # noqa


class TemporalContradictionEvaluator(ContradictionEvaluatorBase):
    def __init__(self) -> None:
        super().__init__(ContradictionType.TEMPORAL)

    def _format_contradiction_type_definition(self) -> str:
        return """
Temporal Contradiction occurs when guidelines dependent on timing or sequence overlap in a way that leads to contradictions.
This arises from a lack of clear prioritization or differentiation between actions required at the same time.
"""  # noqa

    def _format_contradiction_type_examples(self) -> str:
        return f"""
#### Example #1:
- **Existing Guideline**: {{"id": 1, "guideline": "When it is the holiday season, Then apply discounts."}}
- **Proposed Guideline**: {{"id": 2, "guideline": "When it is the end-of-year sale period, Then apply no discounts."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "1",
                 "proposed_guideline_id": "2",
                 "severity_level": 9,
                 "rationale": "The guideline to apply discounts during the holiday season contradicts the guideline to withhold discounts during the end-of-year sales period, as these periods can overlap, leading to contradictory pricing strategies."
             }}
         ]
     }}
     ```

#### Example #2:
- **Existing Guideline**: {{"id": 3, "guideline": "When a product reaches its expiration date, Then mark it down for quick sale."}}
- **Proposed Guideline**: {{"id": 4, "guideline": "When a promotional campaign is active, Then maintain standard pricing to maximize campaign impact."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "3",
                 "proposed_guideline_id": "4",
                 "severity_level": 8,
                 "rationale": "The need to sell expiring products at reduced prices contradicts the strategy to maintain standard pricing during active promotional campaigns, particularly problematic when both circumstances coincide."
             }}
         ]
     }}
     ```

#### Example #3:
- **Existing Guideline**: {{"id": 5, "guideline": "When severe weather conditions are forecasted, Then activate emergency protocols and limit business operations."}}
- **Proposed Guideline**: {{"id": 6, "guideline": "When a major sales event is planned, Then ensure maximum operational capacity."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "5",
                 "proposed_guideline_id": "6",
                 "severity_level": 9,
                 "rationale": "The protocol to reduce operations due to severe weather directly opposes the requirement to maximize operational capacity during a major sales event, creating a significant management challenge when both occur at the same time."
             }}
         ]
     }}
     ```

#### Example #4:
- **Existing Guideline**: {{"id": 7, "guideline": "When customer service receives high call volumes, Then deploy additional staff to handle the influx."}}
- **Proposed Guideline**: {{"id": 8, "guideline": "When a new product launch is scheduled, Then prepare customer service for increased inquiries."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "7",
                 "proposed_guideline_id": "8",
                 "severity_level": 1,
                 "rationale": "Both guidelines aim to enhance customer service readiness under different but complementary circumstances, with no direct timing contradiction between them."
             }}
         ]
     }}
     ```
        """  # noqa


class ContextualContradictionEvaluator(ContradictionEvaluatorBase):
    def __init__(self) -> None:
        super().__init__(ContradictionType.CONTEXTUAL)

    def _format_contradiction_type_definition(self) -> str:
        return """
Contextual Contradiction occurs when external conditions or operational contexts lead to contradictory actions.
These conflicts arise from different but potentially overlapping circumstances requiring actions that are valid under each specific context yet oppose each other.
"""  # noqa

    def _format_contradiction_type_examples(self) -> str:
        return f"""

#### Example #1:
- **Foundational guideline**: {{"id": 1, "guideline": "When operating in urban areas, Then offer free shipping."}}
- **Proposed Guideline**: {{"id": 2, "guideline": "When operational costs need to be minimized, Then restrict free shipping."}}
- **Expected Result**:
     ```json
     {{
         "contextual_contradictions": [
             {{
                 "existing_guideline_id": "1",
                 "proposed_guideline_id": "2",
                 "severity_level": 9,
                 "rationale": "The guideline to offer free shipping in urban areas contradicts the need to minimize operational costs, especially problematic when both conditions are relevant, leading to conflicting shipping policies."
             }}
         ]
     }}
     ```

#### Example #2:
- **Foundational guideline**: {{"id": 3, "guideline": "When customer surveys indicate a preference for environmentally friendly products, Then shift production to eco-friendly materials."}}
- **Proposed Guideline**: {{"id": 4, "guideline": "When cost considerations drive decisions, Then continue using less expensive, traditional materials."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "3",
                 "proposed_guideline_id": "4",
                 "severity_level": 8,
                 "rationale": "Customer data supporting the preference for eco-friendly products contradicts cost-driven strategies to use cheaper, less sustainable materials, creating a dilemma when both customer preference and cost reduction are priorities."
             }}
         ]
     }}
     ```

#### Example #3:
- **Foundational guideline**: {{"id": 5, "guideline": "When market data shows customer preference for high-end products, Then focus on premium product lines."}}
- **Proposed Guideline**: {{"id": 6, "guideline": "When internal strategy targets mass market appeal, Then increase production of lower-cost items."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "5",
                 "proposed_guideline_id": "6",
                 "severity_level": 9,
                 "rationale": "Market data indicating a preference for premium products contradicts internal strategies aimed at expanding the mass market with lower-cost items, especially when both market data and strategic goals are concurrently actionable."
             }}
         ]
     }}
     ```
#### Example #4:
- **Foundational guideline**: {{"id": 7, "guideline": "When a technology product is released, Then launch a marketing campaign to promote the new product."}}
- **Proposed Guideline**: {{"id": 8, "guideline": "When a new software update is released, Then send notifications to existing customers to encourage updates."}}
- **Expected Result**:
     ```json
     {{
        "{self.contradiction_response_outcome_key}": [
             {{
                 "existing_guideline_id": "7",
                 "proposed_guideline_id": "8",
                 "severity_level": 1,
                 "rationale": "Both guidelines aim to promote new developments (product or software) without overlapping contexts or conflicting actions. The marketing campaign targets potential buyers, while the notification process targets existing users, ensuring both actions complement each other without contradiction."
             }}
         ]
     }}
     ```
        """  # noqa


class CoherenceChecker:
    def __init__(self) -> None:
        self._llm_client = make_llm_client("openai")
        self.hierarchical_contradiction_evaluator = HierarchicalContradictionEvaluator()
        self.parallel_contradiction_evaluator = ParallelContradictionEvaluator()
        self.temporal_contradiction_evaluator = TemporalContradictionEvaluator()
        self.contextual_contradiction_evaluator = ContextualContradictionEvaluator()

    async def evaluate_coherence(
        self,
        proposed_guidelines: Iterable[Guideline],
        existing_guidelines: Iterable[Guideline],
    ) -> Iterable[ContradictionTest]:
        hierarchical_contradictions_task = self.hierarchical_contradiction_evaluator.evaluate(
            proposed_guidelines,
            existing_guidelines,
        )
        parallel_contradictions_task = self.parallel_contradiction_evaluator.evaluate(
            proposed_guidelines,
            existing_guidelines,
        )
        temporal_contradictions_task = self.temporal_contradiction_evaluator.evaluate(
            proposed_guidelines,
            existing_guidelines,
        )
        contextual_contradictions_task = self.contextual_contradiction_evaluator.evaluate(
            proposed_guidelines,
            existing_guidelines,
        )
        combined_contradictions = chain.from_iterable(
            await asyncio.gather(
                hierarchical_contradictions_task,
                parallel_contradictions_task,
                temporal_contradictions_task,
                contextual_contradictions_task,
            )
        )
        return combined_contradictions
