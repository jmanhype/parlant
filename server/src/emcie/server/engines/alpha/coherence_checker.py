from abc import ABC, abstractmethod
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from itertools import chain
import json
from typing import Iterable, NewType

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_fixed

from emcie.server.core.guidelines import Guideline, GuidelineId
from emcie.server.engines.alpha.utils import duration_logger, make_llm_client
import more_itertools

CoherenceContradictionId = NewType("CoherenceContradictionId", str)


class ContradictionType(Enum):
    HIERARCHICAL = "Hierarchical Contradiction"
    PARALLEL = "Parallel Contradiction"
    TEMPORAL = "Temporal Contradiction"
    CONTEXTUAL = "Contextual Contradiction"
    VALUES = "Values Contradiction"
    DATA_DEPENDENCY = "Data Dependency Contradiction"
    BEHAVIORAL = "Behavioral Contradiction"
    POLICY = "Policy Contradiction"


class Contradiction(BaseModel):
    coherence_contradiction_type: ContradictionType
    reference_guideline_id: GuidelineId
    checked_guideline_id: GuidelineId
    severity: int
    rationale: str
    creation_utc: datetime


class ContradictionEvaluator(ABC):
    @abstractmethod
    async def evaluate(
        self,
        candidates: Iterable[Guideline],
        foundational_guidelines: Iterable[Guideline],
    ) -> Iterable[Contradiction]: ...

    @staticmethod
    def _remove_duplicate_contradictions(
        contradictions: Iterable[Contradiction],
    ) -> Iterable[Contradiction]:
        """
        Filter unique contradictions based on the combination of reference and checked guidelines.

        Args:
            contradictions: Iterable of Contradiction objects to filter.

        Returns:
            Iterable of unique Contradiction objects.
        """

        def _generate_key(
            g1_id: GuidelineId, g2_id: GuidelineId
        ) -> tuple[GuidelineId, GuidelineId]:
            return (g1_id, g2_id) if g1_id > g2_id else (g2_id, g1_id)

        seen_keys = set()
        unique_contradictions = []
        for contradiction in contradictions:
            key = _generate_key(
                contradiction.reference_guideline_id, contradiction.checked_guideline_id
            )
            if key not in seen_keys:
                seen_keys.add(key)
                unique_contradictions.append(contradiction)
        return unique_contradictions


class HierarchicalContradictionEvaluator(ContradictionEvaluator):
    def __init__(self) -> None:
        self.coherence_contradiction_type = ContradictionType.HIERARCHICAL
        self._llm_client = make_llm_client("openai")

    async def evaluate(
        self,
        candidates: Iterable[Guideline],
        foundational_guidelines: Iterable[Guideline] = [],
    ) -> Iterable[Contradiction]:
        batch_size = 5
        foundational_guideline_list = list(foundational_guidelines)
        candidates_list = list(candidates)
        tasks = []

        for candidate in candidates:
            filtered_foundational_guidelines = [
                g for g in candidates_list + foundational_guideline_list if g.id != candidate.id
            ]
            guideline_batches = more_itertools.chunked(filtered_foundational_guidelines, batch_size)
            tasks.extend(
                [
                    asyncio.create_task(self._process_candidate(candidate, batch))
                    for batch in guideline_batches
                ]
            )
        with duration_logger(
            f"Evaluate hierarchical coherence contradictions for ({len(tasks)} batches)"
        ):
            contradictions: Iterable[Contradiction] = chain.from_iterable(
                await asyncio.gather(*tasks)
            )

        distinct_contradictions = self._remove_duplicate_contradictions(contradictions)
        return distinct_contradictions

    async def _process_candidate(
        self,
        candidate: Guideline,
        foundational_guidelines: Iterable[Guideline],
    ) -> Iterable[Contradiction]:
        prompt = self._format_candidate_contradiction_prompt(
            candidate,
            foundational_guidelines,
        )
        contradictions: Iterable[Contradiction] = await self._generate_candidate_contradictions(
            prompt
        )
        return contradictions

    def _format_candidate_contradiction_prompt(
        self,
        candidate: Guideline,
        foundational_guidelines: Iterable[Guideline],
    ) -> str:
        foundational_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(foundational_guidelines, start=1)
        )
        candidate_guideline_string = (
            f"{{id: {candidate.id}, "
            f"guideline: When {candidate.predicate}, then {candidate.content}}}"
        )
        return f"""
### Definition of Hierarchical Coherence Contradiction:

Hierarchical Coherence Contradiction arises when there are multiple layers of guidelines, with one being more specific or detailed than the other. This type of Contradiction occurs when the application of a general guideline is contradicted by a more specific guideline under certain conditions, leading to inconsistencies in decision-making.

**Objective**: Evaluate potential hierarchical contradictions between the set of foundational guidelines and the checked guideline.

**Task Description**:
1. **Input**:
   - Foundational Guidelines: ###
   {foundational_guidelines_string}
   ###
   - Checked Guideline: ###
   {candidate_guideline_string}
   ###

2. **Process**:
   - For each guideline in the foundational set, compare it with the checked guideline.
   - Determine if there is a hierarchical contradiction, where the checked guideline is more specific and directly contradicts a more general guideline from the foundational set.
   - If no contradiction is detected, set the severity_level to 1 to indicate minimal or no contradiction.

3. **Output**:
   - A list of results, each item detailing a potential contradiction, structured as follows:
     ```json
     {{
         "hierarchical_coherence_contradictions": [
             {{
                 "reference_guideline_id": "<ID of the reference guideline in the contradiction>",
                 "candidate_guideline_id": "<ID of the checked guideline in the contradiction>",
                 "severity_level": "<Severity Level (1-10): Indicates the intensity of the contradiction arising from overlapping conditions>"
                 "rationale": "<Brief explanation of why the two guidelines have a hierarchical contradiction>"
             }}
         ]
     }}
     ```

### Examples of Evaluations:

#### Example #1:
- **Foundational Guideline**: {{"id": 3, "guideline": "When a customer orders any item, Then prioritize shipping based on customer loyalty level."}}
- **Checked Guideline**: {{"id": 4, "guideline": "When a customer orders a high-demand item, Then ship immediately, regardless of loyalty level."}}
- **Expected Result**:
     ```json
     {{
         "hierarchical_coherence_contradictions": [
             {{
                 "reference_guideline_id": "3",
                 "candidate_guideline_id": "4",
                 "severity_level": 9,
                 "rationale": "The guideline to immediately ship high-demand items directly contradicts the broader policy of prioritizing based on loyalty, leading to a situation where the specific scenario of high-demand items undermines the general loyalty prioritization."
             }}
         ]
     }}
     ```

#### Example #2:
- **Foundational Guideline**: {{"id": 1, "guideline": "When an employee qualifies for any reward, Then distribute rewards based on standard performance metrics."}}
- **Checked Guideline**: {{"id": 2, "guideline": "When an employee excels in a critical project, Then offer additional rewards beyond standard metrics."}}
- **Expected Result**:
     ```json
     {{
         "hierarchical_coherence_contradictions": [
             {{
                 "reference_guideline_id": "1",
                 "candidate_guideline_id": "2",
                 "severity_level": 8,
                 "rationale": "The policy to give additional rewards for critical project performance contradicts the general policy of standard performance metrics, creating a Contradiction where a specific achievement overlaps and supersedes the general reward system."
             }}
         ]
     }}
     ```

#### Example #3:
- **Foundational Guideline**: {{"id": 5, "guideline": "When a customer subscribes to a yearly plan, Then offer a 10% discount on the subscription fee."}}
- **Checked Guideline**: {{"id": 6, "guideline": "When a customer subscribes to any plan during a promotional period, Then offer an additional 5% discount on the subscription fee."}}
- **Expected Result**:
     ```json
     {{
         "hierarchical_coherence_contradictions": [
             {{
                 "reference_guideline_id": "5",
                 "candidate_guideline_id": "6",
                 "severity_level": 1,
                 "rationale": "The policies to offer discounts for yearly subscriptions and additional discounts during promotional periods complement each other rather than contradict. Both discounts can be applied simultaneously without undermining one another, enhancing the overall attractiveness of the subscription offers during promotions."
             }}
         ]
     }}
     ```

#### Example #4:
- **Foundational Guideline**: {{"id": 7, "guideline": "When there is a software update, Then deploy it within 48 hours."}}
- **Checked Guideline**: {{"id": 8, "guideline": "When a software update includes major changes affecting user interfaces, Then delay deployment for additional user training."}}
- **Expected Result**:
     ```json
     {{
         "hierarchical_coherence_contradictions": [
             {{
                 "reference_guideline_id": "7",
                 "candidate_guideline_id": "8",
                 "severity_level": 9,
                 "rationale": "The requirement for additional training for major UI changes contradicts the general guideline of rapid deployment for security updates, showing how a specific feature of an update (UI changes) can override a general security protocol."
             }}
         ]
     }}
     ```
        """  # noqa

    @retry(wait=wait_fixed(3.5), stop=stop_after_attempt(100))
    async def _generate_candidate_contradictions(
        self,
        prompt: str,
    ) -> Iterable[Contradiction]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["hierarchical_coherence_contradictions"]

        contradictions = [
            Contradiction(
                coherence_contradiction_type=ContradictionType.HIERARCHICAL,
                reference_guideline_id=json_contradiction["reference_guideline_id"],
                checked_guideline_id=json_contradiction["candidate_guideline_id"],
                severity=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
                creation_utc=datetime.now(timezone.utc),
            )
            for json_contradiction in json_content
        ]

        return contradictions


class ParallelContradictionEvaluator(ContradictionEvaluator):
    def __init__(self) -> None:
        self.coherence_contradiction_type = ContradictionType.PARALLEL
        self._llm_client = make_llm_client("openai")

    async def evaluate(
        self,
        candidates: Iterable[Guideline],
        foundational_guidelines: Iterable[Guideline],
    ) -> Iterable[Contradiction]:
        batch_size = 5
        foundational_guideline_list = list(foundational_guidelines)
        candidates_list = list(candidates)
        tasks = []

        for candidate in candidates:
            filtered_foundational_guidelines = [
                g for g in candidates_list + foundational_guideline_list if g.id != candidate.id
            ]
            guideline_batches = more_itertools.chunked(filtered_foundational_guidelines, batch_size)
            tasks.extend(
                [
                    asyncio.create_task(self._process_candidate(candidate, batch))
                    for batch in guideline_batches
                ]
            )

        with duration_logger(
            f"Evaluate parallel coherence contradictions for ({len(tasks)} batches)"
        ):
            contradictions: Iterable[Contradiction] = chain.from_iterable(
                await asyncio.gather(*tasks)
            )
        distinct_contradictions = self._remove_duplicate_contradictions(contradictions)
        return distinct_contradictions

    async def _process_candidate(
        self,
        candidate: Guideline,
        foundational_guidelines: Iterable[Guideline],
    ) -> Iterable[Contradiction]:
        prompt = self._format_candidate_contradiction_prompt(
            candidate,
            foundational_guidelines,
        )
        contradictions: Iterable[Contradiction] = await self._generate_candidate_contradictions(
            prompt
        )
        return contradictions

    def _format_candidate_contradiction_prompt(
        self,
        candidate: Guideline,
        foundational_guidelines: Iterable[Guideline],
    ) -> str:
        foundational_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(foundational_guidelines, start=1)
        )
        checked_guideline_string = (
            f"{{id: {candidate.id}, "
            f"guideline: When {candidate.predicate}, then {candidate.content}}}"
        )

        return f"""
### Definition of Parallel Contradiction:

Parallel Contradiction occurs when two guidelines of equal specificity lead to contradictory actions. This happens when conditions for both guidelines are met simultaneously, without a clear resolution mechanism to prioritize one over the other.

**Objective**: Evaluate potential parallel contradictions between the set of foundational guidelines and the checked guideline.

**Task Description**:
1. **Input**:
   - Foundational Guidelines: {foundational_guidelines_string}
   - Checked Guideline: {checked_guideline_string}

2. **Process**:
   - For each guideline in the foundational set, compare it with the checked guideline.
   - Determine if there is a parallel priority contradiction, where both guidelines apply under the same conditions and directly Contradiction without a clear way to resolve the priority.
   - If no contradiction is detected, set the severity_level to 1 to indicate minimal or no contradiction.

3. **Output**:
   - A list of results, each item detailing a potential contradiction, structured as follows:
     ```json
     {{
         "parallel_priority_contradictions": [
             {{
                 "reference_guideline_id": "<ID of the reference guideline in the contradiction>",
                 "candidate_guideline_id": "<ID of the checked guideline in the contradiction>",
                 "severity_level": "<Severity Level (1-10): Indicates the intensity of the contradiction arising from overlapping conditions>"
                 "rationale": "<Brief explanation of why the two guidelines are in parallel priority Contradiction>"
             }}
         ]
     }}
     ```

### Examples of Evaluations:

#### Example #1:
- **Foundation Guideline**: {{"id": 1, "guideline": "When a customer returns an item within 30 days, Then issue a full refund."}}
- **Checked Guideline**: {{"id": 2, "guideline": "When the returned item is a special order, Then do not offer refunds."}}
- **Expected Result**:
     ```json
     {{
         "parallel_priority_contradictions": [
             {{
                 "reference_guideline_id": "1",
                 "candidate_guideline_id": "2",
                 "severity_level": 9,
                 "rationale": "Both guidelines apply when a special order item is returned within 30 days, leading to confusion over whether to issue a refund or deny it based on the special order status."
             }}
         ]
     }}
     ```

#### Example #2:
- **Foundation Guideline**: {{"id": 3, "guideline": "When a project deadline is imminent, Then allocate all available resources to complete the project."}}
- **Checked Guideline**: {{"id": 4, "guideline": "When multiple projects are nearing deadlines at the same time, Then distribute resources equally among projects."}}
- **Expected Result**:
     ```json
     {{
         "parallel_priority_contradictions": [
             {{
                 "reference_guideline_id": "3",
                 "candidate_guideline_id": "4",
                 "severity_level": 8,
                 "rationale": "The requirement to focus all resources on a single project Contradictions with the need to distribute resources equally when multiple projects are due, creating a decision-making deadlock without a clear priority directive."
             }}
         ]
     }}
     ```

#### Example #3:
- **Foundation Guideline**: {{"id": 5, "guideline": "When an employee requests flexible working hours, Then approve to support work-life balance."}}
- **Checked Guideline**: {{"id": 6, "guideline": "When team collaboration is essential, Then require standard working hours for all team members."}}
- **Expected Result**:
     ```json
     {{
         "parallel_priority_contradictions": [
             {{
                 "reference_guideline_id": "5",
                 "candidate_guideline_id": "6",
                 "severity_level": 7,
                 "rationale": "The policy to accommodate flexible working hours Contradictions with the requirement for standard hours to enhance team collaboration, creating a scenario where both policies are justified but contradictory."
             }}
         ]
     }}
     ```

#### Example #4:
- **Foundation Guideline**: {{"id": 7, "guideline": "When a customer inquires about product features, Then provide detailed information and recommendations based on their needs."}}
- **Checked Guideline**: {{"id": 8, "guideline": "When a customer asks about compatibility with other products, Then offer guidance on compatible products and configurations."}}
- **Expected Result**:
     ```json
     {{
         "parallel_priority_contradictions": [
             {{
                 "reference_guideline_id": "7",
                 "candidate_guideline_id": "8",
                 "severity_level": 1,
                 "rationale": "The guidelines address different aspects of customer inquiries without Contradictioning. One provides general product information, while the other focuses specifically on compatibility issues, allowing both guidelines to operate simultaneously without contradiction."
             }}
         ]
     }}
     ```
    """  # noqa

    @retry(wait=wait_fixed(3.5), stop=stop_after_attempt(100))
    async def _generate_candidate_contradictions(
        self,
        prompt: str,
    ) -> Iterable[Contradiction]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["parallel_priority_contradictions"]

        contradictions = [
            Contradiction(
                coherence_contradiction_type=ContradictionType.PARALLEL,
                reference_guideline_id=json_contradiction["reference_guideline_id"],
                checked_guideline_id=json_contradiction["candidate_guideline_id"],
                severity=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
                creation_utc=datetime.now(timezone.utc),
            )
            for json_contradiction in json_content
        ]

        return contradictions


class TemporalContradictionEvaluator(ContradictionEvaluator):
    def __init__(self) -> None:
        self.coherence_contradiction_type = ContradictionType.TEMPORAL
        self._llm_client = make_llm_client("openai")

    async def evaluate(
        self,
        candidates: Iterable[Guideline],
        foundational_guidelines: Iterable[Guideline],
    ) -> Iterable[Contradiction]:
        batch_size = 5
        foundational_guideline_list = list(foundational_guidelines)
        candidates_list = list(candidates)
        tasks = []

        for candidate in candidates:
            filtered_foundational_guidelines = [
                g for g in candidates_list + foundational_guideline_list if g.id != candidate.id
            ]
            guideline_batches = more_itertools.chunked(filtered_foundational_guidelines, batch_size)
            tasks.extend(
                [
                    asyncio.create_task(self._process_candidate(candidate, batch))
                    for batch in guideline_batches
                ]
            )

        with duration_logger(
            f"Evaluate temporal coherence contradictions for({len(tasks)} batches)"
        ):
            contradictions: Iterable[Contradiction] = chain.from_iterable(
                await asyncio.gather(*tasks)
            )

        distinct_contradictions = self._remove_duplicate_contradictions(contradictions)
        return distinct_contradictions

    async def _process_candidate(
        self,
        candidate: Guideline,
        foundational_guidelines: Iterable[Guideline],
    ) -> Iterable[Contradiction]:
        prompt = self._format_candidate_contradiction_prompt(
            candidate,
            foundational_guidelines,
        )
        contradictions: Iterable[Contradiction] = await self._generate_candidate_contradictions(
            prompt
        )
        return contradictions

    def _format_candidate_contradiction_prompt(
        self,
        candidate: Guideline,
        foundational_guidelines: Iterable[Guideline],
    ) -> str:
        foundational_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(foundational_guidelines, start=1)
        )
        candidate_guideline_string = (
            f"{{id: {candidate.id}, "
            f"guideline: When {candidate.predicate}, then {candidate.content}}}"
        )
        return f"""
### Definition of Temporal Contradiction:

Temporal Contradiction occurs when guidelines dependent on timing or sequence overlap in a way that leads to contradictions.
This arises from a lack of clear prioritization or differentiation between actions required at the same time.

**Objective**: Evaluate potential temporal contradictions between sets of guidelines that are based on timing.

**Task Description**:
1. **Input**:
   - Foundational Guidelines: {foundational_guidelines_string}
   - Checked Guideline: {candidate_guideline_string}

2. **Process**:
   - Analyze the conditions and the timing specified for each pair of guidelines.
   - Determine if there is a temporal contradiction, where the timings of the guidelines conflict without a clear way to resolve which action should take precedence.
   - If no contradiction is detected, set the contradiction level to 1 to indicate minimal or no contradiction.

3. **Output**:
   - A list of results, each detailing either a potential contradiction or the absence of one, structured as follows:
     ```json
     {{
         "temporal_contradictions": [
             {{
                 "reference_guideline_id": "<ID of the reference guideline in the contradiction>",
                 "candidate_guideline_id": "<ID of the checked guideline in the contradiction>",
                 "severity_level": "<Contradiction Level (1-10): Measures the degree of contradiction due to timing overlap>",
                 "rationale": "<Brief explanation of why the two guidelines are in temporal contradiction or why they are not>"
             }}
         ]
     }}
     ```

### Examples of Evaluations:

#### Example #1:
- **Foundational guideline**: {{"id": 1, "guideline": "When it is the holiday season, Then apply discounts."}}
- **Checked Guideline**: {{"id": 2, "guideline": "When it is the end-of-year sale period, Then apply no discounts."}}
- **Expected Result**:
     ```json
     {{
         "temporal_contradictions": [
             {{
                 "reference_guideline_id": "1",
                 "candidate_guideline_id": "2",
                 "severity_level": 9,
                 "rationale": "The guideline to apply discounts during the holiday season contradicts the guideline to withhold discounts during the end-of-year sales period, even though these periods can overlap, leading to contradictory pricing strategies."
             }}
         ]
     }}
     ```

#### Example #2:
- **Foundational guideline**: {{"id": 3, "guideline": "When a product reaches its expiration date, Then mark it down for quick sale."}}
- **Checked Guideline**: {{"id": 4, "guideline": "When a promotional campaign is active, Then maintain standard pricing to maximize campaign impact."}}
- **Expected Result**:
     ```json
     {{
         "temporal_contradictions": [
             {{
                 "reference_guideline_id": "3",
                 "candidate_guideline_id": "4",
                 "severity_level": 8,
                 "rationale": "The need to sell expiring products at reduced prices contradicts the strategy to maintain standard pricing during active promotional campaigns, especially problematic when both circumstances coincide."
             }}
         ]
     }}
     ```

#### Example #3:
- **Foundational guideline**: {{"id": 5, "guideline": "When severe weather conditions are forecasted, Then activate emergency protocols and limit business operations."}}
- **Checked Guideline**: {{"id": 6, "guideline": "When a major sales event is planned, Then ensure maximum operational capacity."}}
- **Expected Result**:
     ```json
     {{
         "temporal_contradictions": [
             {{
                 "reference_guideline_id": "5",
                 "candidate_guideline_id": "6",
                 "severity_level": 9,
                 "rationale": "The protocol to reduce operations due to severe weather directly opposes the requirement to maximize operational capacity during a major sales event, creating a significant management challenge when both occur at the same time."
             }}
         ]
     }}
     ```

#### Example #4:
- **Foundational guideline**: {{"id": 7, "guideline": "When customer service receives high call volumes, Then deploy additional staff to handle the influx."}}
- **Checked Guideline**: {{"id": 8, "guideline": "When a new product launch is scheduled, Then prepare customer service for increased inquiries."}}
- **Expected Result**:
     ```json
     {{
         "temporal_contradictions": [
             {{
                 "reference_guideline_id": "7",
                 "candidate_guideline_id": "8",
                 "severity_level": 1,
                 "rationale": "Both guidelines aim to enhance customer service readiness under different but complementary circumstances, with no direct timing contradiction between them."
             }}
         ]
     }}
     ```
"""  # noqa

    @retry(wait=wait_fixed(3.5), stop=stop_after_attempt(100))
    async def _generate_candidate_contradictions(
        self,
        prompt: str,
    ) -> Iterable[Contradiction]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["temporal_contradictions"]

        contradictions = [
            Contradiction(
                coherence_contradiction_type=ContradictionType.TEMPORAL,
                reference_guideline_id=json_contradiction["reference_guideline_id"],
                checked_guideline_id=json_contradiction["candidate_guideline_id"],
                severity=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
                creation_utc=datetime.now(timezone.utc),
            )
            for json_contradiction in json_content
        ]

        return contradictions


class ContextualContradictionEvaluator(ContradictionEvaluator):
    def __init__(self) -> None:
        self.coherence_contradiction_type = ContradictionType.CONTEXTUAL
        self._llm_client = make_llm_client("openai")

    async def evaluate(
        self,
        candidates: Iterable[Guideline],
        foundational_guidelines: Iterable[Guideline],
    ) -> Iterable[Contradiction]:
        batch_size = 5
        foundational_guideline_list = list(foundational_guidelines)
        candidates_list = list(candidates)
        tasks = []

        for candidate in candidates:
            filtered_foundational_guidelines = [
                g for g in candidates_list + foundational_guideline_list if g.id != candidate.id
            ]
            guideline_batches = more_itertools.chunked(filtered_foundational_guidelines, batch_size)
            tasks.extend(
                [
                    asyncio.create_task(self._process_candidate(candidate, batch))
                    for batch in guideline_batches
                ]
            )

        with duration_logger(
            f"Evaluate contextual coherence contradictions for({len(tasks)} batches)"
        ):
            contradictions: Iterable[Contradiction] = chain.from_iterable(
                await asyncio.gather(*tasks)
            )

        distinct_contradictions = self._remove_duplicate_contradictions(contradictions)
        return distinct_contradictions

    async def _process_candidate(
        self,
        candidate: Guideline,
        foundational_guidelines: Iterable[Guideline],
    ) -> Iterable[Contradiction]:
        prompt = self._format_candidate_contradiction_prompt(
            candidate,
            foundational_guidelines,
        )
        contradictions: Iterable[Contradiction] = await self._generate_candidate_contradictions(
            prompt
        )
        return contradictions

    def _format_candidate_contradiction_prompt(
        self,
        candidate: Guideline,
        foundational_guidelines: Iterable[Guideline],
    ) -> str:
        foundational_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(foundational_guidelines, start=1)
        )
        candidate_guideline_string = (
            f"{{id: {candidate.id}, "
            f"guideline: When {candidate.predicate}, then {candidate.content}}}"
        )
        return f"""
### Definition of Contextual Contradiction:

Contextual Contradiction occurs when external conditions or operational contexts lead to contradictory actions.
These conflicts arise from different but potentially overlapping circumstances requiring actions that are valid under each specific context yet oppose each other.

**Objective**: Evaluate potential contextual contradictions between sets of guidelines that are influenced by external or operational conditions.

**Task Description**:
1. **Input**:
   - Foundational Guidelines: {foundational_guidelines_string}
   - Checked Guideline: {candidate_guideline_string}

2. **Process**:
   - Analyze the conditions and operational contexts specified for each pair of guidelines.
   - Determine if there is a contextual contradiction, where the guidelines apply under overlapping external conditions but lead to opposing actions.
   - If no contradiction is detected, set the contradiction level to 1 to indicate minimal or no contradiction.

3. **Output**:
   - A list of results, each detailing either a potential contradiction or the absence of one, structured as follows:
     ```json
     {{
         "contextual_contradictions": [
             {{
                 "reference_guideline_id": "<ID of the reference guideline in the contradiction>",
                 "candidate_guideline_id": "<ID of the checked guideline in the contradiction>",
                 "severity_level": "<Contradiction Level (1-10): Measures the degree of contradiction due to conflicting contexts>",
                 "rationale": "<Brief explanation of why the two guidelines are in contextual contradiction or why they are not>"
             }}
         ]
     }}
     ```

### Examples of Evaluations:

#### Example #1:
- **Foundational guideline**: {{"id": 1, "guideline": "When operating in urban areas, Then offer free shipping."}}
- **Checked Guideline**: {{"id": 2, "guideline": "When operational costs need to be minimized, Then restrict free shipping."}}
- **Expected Result**:
     ```json
     {{
         "contextual_contradictions": [
             {{
                 "reference_guideline_id": "1",
                 "candidate_guideline_id": "2",
                 "severity_level": 9,
                 "rationale": "The guideline to offer free shipping in urban areas contradicts the need to minimize operational costs, especially problematic when both conditions are relevant, leading to conflicting shipping policies."
             }}
         ]
     }}
     ```

#### Example #2:
- **Foundational guideline**: {{"id": 3, "guideline": "When customer surveys indicate a preference for environmentally friendly products, Then shift production to eco-friendly materials."}}
- **Checked Guideline**: {{"id": 4, "guideline": "When cost considerations drive decisions, Then continue using less expensive, traditional materials."}}
- **Expected Result**:
     ```json
     {{
         "contextual_contradictions": [
             {{
                 "reference_guideline_id": "3",
                 "candidate_guideline_id": "4",
                 "severity_level": 8,
                 "rationale": "Customer data supporting the preference for eco-friendly products contradicts cost-driven strategies to use cheaper, less sustainable materials, creating a dilemma when both customer preference and cost reduction are priorities."
             }}
         ]
     }}
     ```

#### Example #3:
- **Foundational guideline**: {{"id": 5, "guideline": "When market data shows customer preference for high-end products, Then focus on premium product lines."}}
- **Checked Guideline**: {{"id": 6, "guideline": "When internal strategy targets mass market appeal, Then increase production of lower-cost items."}}
- **Expected Result**:
     ```json
     {{
         "contextual_contradictions": [
             {{
                 "reference_guideline_id": "5",
                 "candidate_guideline_id": "6",
                 "severity_level": 9,
                 "rationale": "Market data indicating a preference for premium products contradicts internal strategies aimed at expanding the mass market with lower-cost items, especially when both market data and strategic goals are concurrently actionable."
             }}
         ]
     }}
     ```
#### Example #4:
- **Foundational guideline**: {{"id": 7, "guideline": "When a technology product is released, Then launch a marketing campaign to promote the new product."}}
- **Checked Guideline**: {{"id": 8, "guideline": "When a new software update is released, Then send notifications to existing customers to encourage updates."}}
- **Expected Result**:
     ```json
     {{
         "contextual_contradictions": [
             {{
                 "reference_guideline_id": "7",
                 "candidate_guideline_id": "8",
                 "severity_level": 1,
                 "rationale": "Both guidelines aim to promote new developments (product or software) without overlapping contexts or conflicting actions. The marketing campaign targets potential buyers, while the notification process targets existing users, ensuring both actions complement each other without contradiction."
             }}
         ]
     }}
     ```

"""  # noqa

    @retry(wait=wait_fixed(3.5), stop=stop_after_attempt(100))
    async def _generate_candidate_contradictions(
        self,
        prompt: str,
    ) -> Iterable[Contradiction]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["contextual_contradictions"]

        contradictions = [
            Contradiction(
                coherence_contradiction_type=ContradictionType.CONTEXTUAL,
                reference_guideline_id=json_contradiction["reference_guideline_id"],
                checked_guideline_id=json_contradiction["candidate_guideline_id"],
                severity=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
                creation_utc=datetime.now(timezone.utc),
            )
            for json_contradiction in json_content
        ]

        return contradictions


class CoherenceChecker:
    def __init__(self) -> None:
        self._llm_client = make_llm_client("openai")
        self.hierarchical_contradiction_evaluator = HierarchicalContradictionEvaluator()
        self.parallel_contradiction_evaluator = ParallelContradictionEvaluator()
        self.temporal_contradiction_evaluator = TemporalContradictionEvaluator()
        self.contexutal_contradiction_evaluator = ContextualContradictionEvaluator()

    async def evaluate_coherence(
        self,
        candidates: Iterable[Guideline],
        foundational_guidelines: Iterable[Guideline],
    ) -> str:
        hierarchical_contradictions_task = self.hierarchical_contradiction_evaluator.evaluate(
            candidates,
            foundational_guidelines,
        )
        parallel_contradictions_task = self.parallel_contradiction_evaluator.evaluate(
            candidates,
            foundational_guidelines,
        )
        temporal_contradictions_task = self.temporal_contradiction_evaluator.evaluate(
            candidates,
            foundational_guidelines,
        )
        contexutal_contradictions_task = self.contexutal_contradiction_evaluator.evaluate(
            candidates,
            foundational_guidelines,
        )
        altogether_contradictions = chain.from_iterable(
            await asyncio.gather(
                hierarchical_contradictions_task,
                parallel_contradictions_task,
                temporal_contradictions_task,
                contexutal_contradictions_task,
            )
        )
        filtered_contradictions = filter(lambda c: c.severity >= 7, altogether_contradictions)
        merged_contradictrions = self._merge_same_guidelines_contradictions(filtered_contradictions)
        if not merged_contradictrions:
            return "Coherence check finished successfully, and no contradictions were found!"

        coherence_response = self._format_coherence_response(
            merged_contradictrions, chain.from_iterable([candidates, foundational_guidelines])
        )
        return coherence_response

    def _merge_same_guidelines_contradictions(
        self,
        contradictions: Iterable[Contradiction],
    ) -> list[list[Contradiction]]:
        same_guidelines_contradictions = defaultdict(list)

        def _generate_key(
            g1_id: GuidelineId, g2_id: GuidelineId
        ) -> tuple[GuidelineId, GuidelineId]:
            return (g1_id, g2_id) if g1_id > g2_id else (g2_id, g1_id)

        for contradiction in contradictions:
            key = _generate_key(
                contradiction.reference_guideline_id, contradiction.checked_guideline_id
            )
            same_guidelines_contradictions[key].append(contradiction)
        return list(same_guidelines_contradictions.values())

    def _map_guidelines(
        self,
        guidelines: Iterable[Guideline],
    ) -> dict[GuidelineId, Guideline]:
        result = {g.id: g for g in guidelines}
        return result

    def _format_contradictions(
        self,
        contradictions: list[list[Contradiction]],
        guidelines: Iterable[Guideline],
    ) -> str:
        guidelines_map = self._map_guidelines(guidelines)
        formatted_contradictions = [
            self._format_contradiction_group(contradiction_group, guidelines_map, j)
            for j, contradiction_group in enumerate(contradictions, start=1)
        ]
        return "\n".join(formatted_contradictions)

    def _format_contradiction_group(
        self,
        contradiction_group: list[Contradiction],
        guidelines_map: dict[GuidelineId, Guideline],
        group_index: int,
    ) -> str:
        reference_guideline = guidelines_map[contradiction_group[0].reference_guideline_id]
        checked_guideline = guidelines_map[contradiction_group[0].checked_guideline_id]
        contradictions_details = [
            f"\t{group_index}.{i}) Type: {c.coherence_contradiction_type.value}, "
            f"Severity Level: {c.severity}, "
            f"Rationale: {c.rationale}"
            for i, c in enumerate(contradiction_group, start=1)
        ]
        return (
            f"{group_index}) Contradiction between:\n"
            f"\t#1: Guideline: When {reference_guideline.predicate}, then {reference_guideline.content}. \n\tGuideline id: {reference_guideline.id}\n"  # noqa
            f"\t#2: Guideline: When {checked_guideline.predicate}, then {checked_guideline.content}. \n\tGuideline id: {checked_guideline.id}\n"  # noqa
            f"Contradictions found:\n" + "\n".join(contradictions_details) + "\n"
        )

    def _format_coherence_response(
        self,
        contraidctions: list[list[Contradiction]],
        guidelines: Iterable[Guideline],
    ) -> str:
        contradiction_string = self._format_contradictions(contraidctions, guidelines)
        return f"""
### Coherence Contradictions Summary Report
{contradiction_string}
"""
