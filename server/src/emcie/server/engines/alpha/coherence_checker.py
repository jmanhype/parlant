from abc import ABC, abstractmethod
from enum import Enum
import json
from typing import Iterable, NewType

from pydantic import BaseModel

from emcie.server.core.guidelines import Guideline, GuidelineId
from emcie.server.engines.alpha.utils import make_llm_client


CoherenceContradictionId = NewType("CoherenceContradictionId", str)


class CoherenceContradictionType(Enum):
    HIERARCHICAL = "Hierarchical Contradiction"
    PARALLEL = "Parallel Contradiction"
    TEMPORAL = "Temporal Contradiction"
    CONTEXTUAL = "Contextual Contradiction"
    VALUES = "Values Contradiction"
    DATA_DEPENDENCY = "Data Dependency Contradiction"
    BEHAVIORAL = "Behavioral Contradiction"
    POLICY = "Policy Contradiction"


class CoherenceContradiction(BaseModel):
    coherence_contradiction_type: CoherenceContradictionType
    reference_guideline_id: GuidelineId
    candidate_guideline_id: GuidelineId
    severity_level: int
    rationale: str


class CoherenceContradictionEvaluator(ABC):
    @abstractmethod
    async def evaluate(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> Iterable[CoherenceContradiction]: ...


class HierarchicalContradictionEvaluator(CoherenceContradictionEvaluator):
    def __init__(self) -> None:
        self.coherence_contradiction_type = CoherenceContradictionType.HIERARCHICAL
        self._llm_client = make_llm_client("openai")

    async def evaluate(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> Iterable[CoherenceContradiction]:
        prompt = self._format_hierarchical_contradiction_evaluation_prompt(
            foundational_guidelines,
            candidate_guideline,
        )
        contradictions: Iterable[CoherenceContradiction] = await self._generate_llm_response(prompt)
        return contradictions

    def _format_hierarchical_contradiction_evaluation_prompt(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> str:
        foundational_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(foundational_guidelines, start=1)
        )
        candidate_guideline_string = (
            f"{{id: {candidate_guideline.id}, "
            f"guideline: When {candidate_guideline.predicate}, then {candidate_guideline.content}}}"
        )
        return f"""
### Definition of Hierarchical Coherence Contradiction:

Hierarchical Coherence Contradiction arises when there are multiple layers of guidelines, with one being more specific or detailed than the other. This type of Contradiction occurs when the application of a general guideline is contradicted by a more specific guideline under certain conditions, leading to inconsistencies in decision-making.

**Objective**: Evaluate potential hierarchical contradictions between the set of foundational guidelines and the candidate guideline.

**Task Description**:
1. **Input**:
   - Foundational Guidelines: ###
   {foundational_guidelines_string}
   ###
   - Candidate Guideline: ###
   {candidate_guideline_string}
   ###

2. **Process**:
   - For each guideline in the foundational set, compare it with the candidate guideline.
   - Determine if there is a hierarchical contradiction, where the candidate guideline is more specific and directly contradicts a more general guideline from the foundational set.
   - If no contradiction is detected, set the severity_level to 1 to indicate minimal or no contradiction.

3. **Output**:
   - A list of results, each item detailing a potential contradiction, structured as follows:
     ```json
     {{
         "hierarchical_coherence_contradictions": [
             {{
                 "reference_guideline_id": "<ID of the reference guideline in the contradiction>",
                 "candidate_guideline_id": "<ID of the candidate guideline in the contradiction>",
                 "severity_level": "<Severity Level (1-10): Indicates the intensity of the contradiction arising from overlapping conditions>"
                 "rationale": "<Brief explanation of why the two guidelines have a hierarchical contradiction>"
             }}
         ]
     }}
     ```

### Examples of Evaluations:

#### Example #1:
- **Foundational Guideline**: {{"id": 3, "guideline": "When a customer orders any item, Then prioritize shipping based on customer loyalty level."}}
- **Candidate Guideline**: {{"id": 4, "guideline": "When a customer orders a high-demand item, Then ship immediately, regardless of loyalty level."}}
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
- **Candidate Guideline**: {{"id": 2, "guideline": "When an employee excels in a critical project, Then offer additional rewards beyond standard metrics."}}
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
- **Candidate Guideline**: {{"id": 6, "guideline": "When a customer subscribes to any plan during a promotional period, Then offer an additional 5% discount on the subscription fee."}}
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
- **Candidate Guideline**: {{"id": 8, "guideline": "When a software update includes major changes affecting user interfaces, Then delay deployment for additional user training."}}
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

    async def _generate_llm_response(
        self,
        prompt: str,
    ) -> Iterable[CoherenceContradiction]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["hierarchical_coherence_contradictions"]

        contradictions = [
            CoherenceContradiction(
                coherence_contradiction_type=CoherenceContradictionType.HIERARCHICAL,
                reference_guideline_id=json_contradiction["reference_guideline_id"],
                candidate_guideline_id=json_contradiction["candidate_guideline_id"],
                severity_level=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
            )
            for json_contradiction in json_content
        ]

        return contradictions


class ParallelContradictionEvaluator(CoherenceContradictionEvaluator):
    def __init__(self) -> None:
        self.coherence_contradiction_type = CoherenceContradictionType.PARALLEL
        self._llm_client = make_llm_client("openai")

    async def evaluate(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> Iterable[CoherenceContradiction]:
        prompt = self._format_parallel_contradiction_evaluation_prompt(
            foundational_guidelines,
            candidate_guideline,
        )
        contradictions: Iterable[CoherenceContradiction] = await self._generate_llm_response(prompt)
        return contradictions

    def _format_parallel_contradiction_evaluation_prompt(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> str:
        foundational_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(foundational_guidelines, start=1)
        )
        candidate_guideline_string = (
            f"{{id: {candidate_guideline.id}, "
            f"guideline: When {candidate_guideline.predicate}, then {candidate_guideline.content}}}"
        )

        return f"""
### Definition of Parallel Contradiction:

Parallel Contradiction occurs when two guidelines of equal specificity lead to contradictory actions. This happens when conditions for both guidelines are met simultaneously, without a clear resolution mechanism to prioritize one over the other.

**Objective**: Evaluate potential parallel contradictions between the set of foundational guidelines and the candidate guideline.

**Task Description**:
1. **Input**:
   - Foundational Guidelines: {foundational_guidelines_string}
   - Candidate Guideline: {candidate_guideline_string}

2. **Process**:
   - For each guideline in the foundational set, compare it with the candidate guideline.
   - Determine if there is a parallel priority contradiction, where both guidelines apply under the same conditions and directly Contradiction without a clear way to resolve the priority.
   - If no contradiction is detected, set the severity_level to 1 to indicate minimal or no contradiction.

3. **Output**:
   - A list of results, each item detailing a potential contradiction, structured as follows:
     ```json
     {{
         "parallel_priority_contradictions": [
             {{
                 "reference_guideline_id": "<ID of the reference guideline in the contradiction>",
                 "candidate_guideline_id": "<ID of the candidate guideline in the contradiction>",
                 "severity_level": "<Severity Level (1-10): Indicates the intensity of the contradiction arising from overlapping conditions>"
                 "rationale": "<Brief explanation of why the two guidelines are in parallel priority Contradiction>"
             }}
         ]
     }}
     ```

### Examples of Evaluations:

#### Example #1:
- **Foundation Guideline**: {{"id": 1, "guideline": "When a customer returns an item within 30 days, Then issue a full refund."}}
- **Candidate Guideline**: {{"id": 2, "guideline": "When the returned item is a special order, Then do not offer refunds."}}
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
- **Candidate Guideline**: {{"id": 4, "guideline": "When multiple projects are nearing deadlines at the same time, Then distribute resources equally among projects."}}
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
- **Candidate Guideline**: {{"id": 6, "guideline": "When team collaboration is essential, Then require standard working hours for all team members."}}
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
- **Candidate Guideline**: {{"id": 8, "guideline": "When a customer asks about compatibility with other products, Then offer guidance on compatible products and configurations."}}
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

    async def _generate_llm_response(
        self,
        prompt: str,
    ) -> Iterable[CoherenceContradiction]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["parallel_priority_contradictions"]

        contradictions = [
            CoherenceContradiction(
                coherence_contradiction_type=CoherenceContradictionType.PARALLEL,
                reference_guideline_id=json_contradiction["reference_guideline_id"],
                candidate_guideline_id=json_contradiction["candidate_guideline_id"],
                severity_level=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
            )
            for json_contradiction in json_content
        ]

        return contradictions


class TemporalContradictionEvaluator(CoherenceContradictionEvaluator):
    def __init__(self) -> None:
        self.coherence_contradiction_type = CoherenceContradictionType.TEMPORAL
        self._llm_client = make_llm_client("openai")

    async def evaluate(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> Iterable[CoherenceContradiction]:
        prompt = self._format_temporal_contradiction_evaluation_prompt(
            foundational_guidelines,
            candidate_guideline,
        )
        contradictions: Iterable[CoherenceContradiction] = await self._generate_llm_response(prompt)
        return contradictions

    def _format_temporal_contradiction_evaluation_prompt(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> str:
        foundational_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(foundational_guidelines, start=1)
        )
        candidate_guideline_string = (
            f"{{id: {candidate_guideline.id}, "
            f"guideline: When {candidate_guideline.predicate}, then {candidate_guideline.content}}}"
        )
        return f"""
### Definition of Temporal Contradiction:

Temporal Contradiction occurs when guidelines dependent on timing or sequence overlap in a way that leads to contradictions.
This arises from a lack of clear prioritization or differentiation between actions required at the same time.

**Objective**: Evaluate potential temporal contradictions between sets of guidelines that are based on timing.

**Task Description**:
1. **Input**:
   - Foundational Guidelines: {foundational_guidelines_string}
   - Candidate Guideline: {candidate_guideline_string}

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
                 "candidate_guideline_id": "<ID of the candidate guideline in the contradiction>",
                 "severity_level": "<Contradiction Level (1-10): Measures the degree of contradiction due to timing overlap>",
                 "rationale": "<Brief explanation of why the two guidelines are in temporal contradiction or why they are not>"
             }}
         ]
     }}
     ```

### Examples of Evaluations:

#### Example #1:
- **Foundational guideline**: {{"id": 1, "guideline": "When it is the holiday season, Then apply discounts."}}
- **Candidate guideline**: {{"id": 2, "guideline": "When it is the end-of-year sale period, Then apply no discounts."}}
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
- **Candidate guideline**: {{"id": 4, "guideline": "When a promotional campaign is active, Then maintain standard pricing to maximize campaign impact."}}
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
- **Candidate guideline**: {{"id": 6, "guideline": "When a major sales event is planned, Then ensure maximum operational capacity."}}
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
- **Candidate guideline**: {{"id": 8, "guideline": "When a new product launch is scheduled, Then prepare customer service for increased inquiries."}}
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

    async def _generate_llm_response(
        self,
        prompt: str,
    ) -> Iterable[CoherenceContradiction]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["temporal_contradictions"]

        contradictions = [
            CoherenceContradiction(
                coherence_contradiction_type=CoherenceContradictionType.TEMPORAL,
                reference_guideline_id=json_contradiction["reference_guideline_id"],
                candidate_guideline_id=json_contradiction["candidate_guideline_id"],
                severity_level=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
            )
            for json_contradiction in json_content
        ]

        return contradictions


class ContextualContradictionEvaluator(CoherenceContradictionEvaluator):
    def __init__(self) -> None:
        self.coherence_contradiction_type = CoherenceContradictionType.CONTEXTUAL
        self._llm_client = make_llm_client("openai")

    async def evaluate(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> Iterable[CoherenceContradiction]:
        prompt = self._format_contextual_contradiction_evaluation_prompt(
            foundational_guidelines,
            candidate_guideline,
        )
        contradictions: Iterable[CoherenceContradiction] = await self._generate_llm_response(prompt)
        return contradictions

    def _format_contextual_contradiction_evaluation_prompt(
        self,
        foundational_guidelines: Iterable[Guideline],
        candidate_guideline: Guideline,
    ) -> str:
        foundational_guidelines_string = "\n".join(
            f"{i}) {{id: {g.id}, guideline: When {g.predicate}, then {g.content}}}"
            for i, g in enumerate(foundational_guidelines, start=1)
        )
        candidate_guideline_string = (
            f"{{id: {candidate_guideline.id}, "
            f"guideline: When {candidate_guideline.predicate}, then {candidate_guideline.content}}}"
        )
        return f"""
### Definition of Contextual Contradiction:

Contextual Contradiction occurs when external conditions or operational contexts lead to contradictory actions.
These conflicts arise from different but potentially overlapping circumstances requiring actions that are valid under each specific context yet oppose each other.

**Objective**: Evaluate potential contextual contradictions between sets of guidelines that are influenced by external or operational conditions.

**Task Description**:
1. **Input**:
   - Foundational Guidelines: {foundational_guidelines_string}
   - Candidate Guideline: {candidate_guideline_string}

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
                 "candidate_guideline_id": "<ID of the candidate guideline in the contradiction>",
                 "severity_level": "<Contradiction Level (1-10): Measures the degree of contradiction due to conflicting contexts>",
                 "rationale": "<Brief explanation of why the two guidelines are in contextual contradiction or why they are not>"
             }}
         ]
     }}
     ```

### Examples of Evaluations:

#### Example #1:
- **Foundational guideline**: {{"id": 1, "guideline": "When operating in urban areas, Then offer free shipping."}}
- **Candidate guideline**: {{"id": 2, "guideline": "When operational costs need to be minimized, Then restrict free shipping."}}
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
- **Candidate guideline**: {{"id": 4, "guideline": "When cost considerations drive decisions, Then continue using less expensive, traditional materials."}}
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
- **Candidate guideline**: {{"id": 6, "guideline": "When internal strategy targets mass market appeal, Then increase production of lower-cost items."}}
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
- **Candidate guideline**: {{"id": 8, "guideline": "When a new software update is released, Then send notifications to existing customers to encourage updates."}}
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

    async def _generate_llm_response(
        self,
        prompt: str,
    ) -> Iterable[CoherenceContradiction]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["contextual_contradictions"]

        contradictions = [
            CoherenceContradiction(
                coherence_contradiction_type=CoherenceContradictionType.CONTEXTUAL,
                reference_guideline_id=json_contradiction["reference_guideline_id"],
                candidate_guideline_id=json_contradiction["candidate_guideline_id"],
                severity_level=json_contradiction["severity_level"],
                rationale=json_contradiction["rationale"],
            )
            for json_contradiction in json_content
        ]

        return contradictions


class CoherenceChecker:
    def __init__(self) -> None:
        self._llm_client = make_llm_client("openai")

    def evaluate_coherence(
        self,
        guidelines_to_evaluate: Iterable[Guideline],
        based_guidelines: Iterable[Guideline],
    ) -> str:
        return ""

    async def _generate_llm_response(self, prompt: str) -> str:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content or ""
