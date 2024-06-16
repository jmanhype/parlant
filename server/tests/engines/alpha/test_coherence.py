from lagom import Container
from pytest import fixture, mark

from emcie.server.core.guidelines import Guideline, GuidelineStore
from emcie.server.engines.alpha.coherence_checker import (
    CoherenceChecker,
    ContradictionType,
    ContextualContradictionEvaluator,
    HierarchicalContradictionEvaluator,
    ParallelContradictionEvaluator,
    TemporalContradictionEvaluator,
)
from tests.test_utilities import SyncAwaiter, nlp_test


@mark.parametrize(
    (
        "candidate_guideline_predicate",
        "candidate_guideline_content",
        "reference_guideline_predicate",
        "reference_guideline_content",
        "expected_contradiction",
    ),
    [
        (
            "A VIP customer requests a specific feature that aligns with their business needs but is not on the current product roadmap",  # noqa
            "Escalate the request to product management for special consideration",
            "Any customer requests a feature not available in the current version",
            "Inform them about the product roadmap and upcoming features",
            True,
        ),
        (
            "Any customer reports a technical issue",
            "Queue the issue for resolution according to standard support protocols",
            "The issue reported affects a critical operational feature for multiple clients",
            "Escalate immediately to the highest priority for resolution",
            True,
        ),
        (
            "A customer inquires about upgrading their service package",
            "Provide information on available upgrade options and benefits",
            "A customer needs assistance with understanding their billing statements",
            "Guide them through the billing details and explain any charges",
            False,
        ),
        (
            "when a customer expresses satisfaction with the service",
            "encourage them to leave a review or testimonial",
            "when a customer refers another potential client",
            "initiate the referral rewards process",
            False,
        ),
    ],
)
def test_hierarchical_contradiction(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: str,
    reference_guideline_predicate: str,
    reference_guideline_content: str,
    candidate_guideline_predicate: str,
    candidate_guideline_content: str,
    expected_contradiction: bool,
) -> None:
    guideline_store = container.resolve(GuidelineStore)
    reference_guideline = sync_await(
        guideline_store.create_guideline(
            agent_id, reference_guideline_predicate, reference_guideline_content
        )
    )
    candidate_guideline = sync_await(
        guideline_store.create_guideline(
            agent_id, candidate_guideline_predicate, candidate_guideline_content
        )
    )
    hierarchical_contradiction_evaluator = HierarchicalContradictionEvaluator()
    contradiction_results = list(
        sync_await(
            hierarchical_contradiction_evaluator.evaluate(
                [candidate_guideline, reference_guideline],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.coherence_contradiction_type == ContradictionType.HIERARCHICAL
    if expected_contradiction:
        assert contradiction.severity >= 7
        assert nlp_test(
            "Given the following two rules:\n"
            f"1. {contradiction.reference_guideline_id}\n"
            f"2. {contradiction.checked_guideline_id}\n"
            "Following rationale if the two rules have a hierarchical coherence contradiction:\n"
            f"{contradiction.rationale}",
            "Contradiction has been found and an explanation is provided as to why it is a "
            "hierarchical contradiction",
        )
    else:
        assert contradiction.severity < 7
        assert nlp_test(contradiction.rationale, "No significant contradiction has been found.")


@mark.parametrize(
    (
        "candidate_guideline_predicate",
        "candidate_guideline_content",
        "reference_guideline_predicate",
        "reference_guideline_content",
        "expected_contradiction",
    ),
    [
        (
            "A customer exceeds their data storage limit",
            "Prompt them to upgrade their subscription plan",
            "Promoting customer retention and satisfaction",
            "Offer a temporary data limit extension without requiring an upgrade",
            True,
        ),
        (
            "Receiving feedback on a new feature",
            "encourage users to adopt and adapt to the change as part of ongoing product",
            "Users express significant resistance to a new feature",
            "Roll back or offer the option to revert to previous settings",
            True,
        ),
        (
            "A customer asks about the security of their data",
            "Provide detailed information about the company’s security measures and certifications",
            "A customer inquires about compliance with specific regulations",
            "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
            False,
        ),
        (
            "A customer requests faster support response times",
            "Explain the standard response times and efforts to improve them",
            "A customer compliments the service on social media",
            "Thank them publicly and encourage them to share more about their positive experience",
            False,
        ),
    ],
)
def test_parallel_contradiction(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: str,
    reference_guideline_predicate: str,
    reference_guideline_content: str,
    candidate_guideline_predicate: str,
    candidate_guideline_content: str,
    expected_contradiction: bool,
) -> None:
    guideline_store = container.resolve(GuidelineStore)
    reference_guideline = sync_await(
        guideline_store.create_guideline(
            agent_id, reference_guideline_predicate, reference_guideline_content
        )
    )
    candidate_guideline = sync_await(
        guideline_store.create_guideline(
            agent_id, candidate_guideline_predicate, candidate_guideline_content
        )
    )
    parallel_contradiction_evaluator = ParallelContradictionEvaluator()
    contradiction_results = list(
        sync_await(
            parallel_contradiction_evaluator.evaluate(
                [candidate_guideline, reference_guideline],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.coherence_contradiction_type == ContradictionType.PARALLEL
    if expected_contradiction:
        assert contradiction.severity >= 7
        assert nlp_test(
            "Given the following two rules:\n"
            f"1. {contradiction.reference_guideline_id}\n"
            f"2. {contradiction.checked_guideline_id}\n"
            "Following rationale if the two rules have a parallel coherence contradiction:\n"
            f"{contradiction.rationale}",
            "Contradiction has been found and an explanation is "
            "provided as to why it is a parallel contradiction",
        )
    else:
        assert contradiction.severity < 7
        assert nlp_test(contradiction.rationale, "No significant contradiction has been found.")


@mark.parametrize(
    (
        "candidate_guideline_predicate",
        "candidate_guideline_content",
        "reference_guideline_predicate",
        "reference_guideline_content",
        "expected_contradiction",
    ),
    [
        (
            "A new software update is scheduled for release",
            "Roll it out to all users to ensure everyone has the latest version",
            "Key clients are in the middle of a critical project",
            "Delay software updates to avoid disrupting their operations",
            True,
        ),
        (
            "The financial quarter ends",
            "Finalize all pending transactions and close the books",
            "A new financial regulation is implemented at the end of the quarter",
            "re-evaluate all transactions from that quarter before closing the books",
            True,
        ),
        (
            "A customer asks about the security of their data",
            "Provide detailed information about the company’s security measures and certifications",
            "A customer inquires about compliance with specific regulations",
            "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
            False,
        ),
        (
            "A customer requests faster support response times",
            "Explain the standard response times and efforts to improve them",
            "A customer compliments the service on social media",
            "Thank them publicly and encourage them to share more about their positive experience",
            False,
        ),
    ],
)
def test_temporal_contradiction(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: str,
    candidate_guideline_predicate: str,
    candidate_guideline_content: str,
    reference_guideline_predicate: str,
    reference_guideline_content: str,
    expected_contradiction: bool,
) -> None:
    guideline_store = container.resolve(GuidelineStore)
    reference_guideline = sync_await(
        guideline_store.create_guideline(
            agent_id, reference_guideline_predicate, reference_guideline_content
        )
    )
    candidate_guideline = sync_await(
        guideline_store.create_guideline(
            agent_id, candidate_guideline_predicate, candidate_guideline_content
        )
    )
    temporal_contradiction_evaluator = TemporalContradictionEvaluator()
    contradiction_results = list(
        sync_await(
            temporal_contradiction_evaluator.evaluate(
                [candidate_guideline, reference_guideline],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.coherence_contradiction_type == ContradictionType.TEMPORAL
    if expected_contradiction:
        assert contradiction.severity >= 7
        assert nlp_test(
            "Given the following two rules:\n"
            f"1. {contradiction.reference_guideline_id}\n"
            f"2. {contradiction.checked_guideline_id}\n"
            "Following rationale if the two rules have a temporal coherence contradiction:\n"
            f"{contradiction.rationale}",
            "Contradiction has been found and an explanation "
            "is provided as to why it is a temporal contradiction",
        )
    else:
        assert contradiction.severity < 7
        assert nlp_test(contradiction.rationale, "No significant contradiction has been found.")


@mark.parametrize(
    (
        "candidate_guideline_predicate",
        "candidate_guideline_content",
        "reference_guideline_predicate",
        "reference_guideline_content",
        "expected_contradiction",
    ),
    [
        (
            "A customer is located in a region with strict data sovereignty laws",
            "Store and process all customer data locally as required by law",
            "The company's policy is to centralize data processing in a single, cost-effective location",  # noqa
            "Consolidate data handling to enhance efficiency",
            True,
        ),
        (
            "A customer's contract is up for renewal during a market downturn",
            "Offer discounts and incentives to ensure renewal",
            "The company’s financial performance targets require maximizing revenue",
            "avoid discounts and push for higher-priced contracts",
            True,
        ),
        (
            "A customer asks about the security of their data",
            "Provide detailed information about the company’s security measures and certifications",
            "A customer inquires about compliance with specific regulations",
            "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
            False,
        ),
        (
            "A customer requests faster support response times",
            "Explain the standard response times and efforts to improve them",
            "A customer compliments the service on social media",
            "Thank them publicly and encourage them to share more about their positive experience",
            False,
        ),
    ],
)
def test_contexual_contradiction(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: str,
    reference_guideline_predicate: str,
    reference_guideline_content: str,
    candidate_guideline_predicate: str,
    candidate_guideline_content: str,
    expected_contradiction: bool,
) -> None:
    guideline_store = container.resolve(GuidelineStore)
    reference_guideline = sync_await(
        guideline_store.create_guideline(
            agent_id, reference_guideline_predicate, reference_guideline_content
        )
    )
    candidate_guideline = sync_await(
        guideline_store.create_guideline(
            agent_id, candidate_guideline_predicate, candidate_guideline_content
        )
    )
    contextual_contradiction_evaluator = ContextualContradictionEvaluator()
    contradiction_results = list(
        sync_await(
            contextual_contradiction_evaluator.evaluate(
                [candidate_guideline, reference_guideline],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.coherence_contradiction_type == ContradictionType.CONTEXTUAL
    if expected_contradiction:
        assert contradiction.severity >= 7
        assert nlp_test(
            "Given the following two rules:\n"
            f"1. {contradiction.reference_guideline_id}\n"
            f"2. {contradiction.checked_guideline_id}\n"
            "Following rationale if the two rules have a contexutal coherence contradiction:\n"
            f"{contradiction.rationale}",
            "Contradiction has been found and an explanation is provided as to why it is a contexutal contradiction",  # noqa
        )
    else:
        assert contradiction.severity < 7
        assert nlp_test(
            "Rationale provided for the contextual coherence check between two rules:"
            f"\n{contradiction.rationale}",
            "No significant contradiction has been found.",
        )


@fixture
def guidelines_with_contradictions(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: str,
) -> list[Guideline]:
    guideline_store = container[GuidelineStore]

    async def create_guideline(predicate: str, content: str) -> Guideline:
        return await guideline_store.create_guideline(
            guideline_set=agent_id,
            predicate=predicate,
            content=content,
        )

    guidelines: list[Guideline] = []

    for guideline_params in [
        {
            "predicate": "A VIP customer requests a specific feature that aligns with their business needs but is not on the current product roadmap",  # noqa
            "content": "Escalate the request to product management for special consideration",
        },
        {
            "predicate": "Any customer requests a feature not available in the current version",
            "content": "Inform them about the product roadmap and upcoming features",
        },
        {
            "predicate": "Any customer reports a technical issue",
            "content": "Queue the issue for resolution according to standard support protocols",
        },
        {
            "predicate": "The issue reported affects a critical operational feature for multiple clients",  # noqa
            "content": "Escalate immediately to the highest priority for resolution",
        },
        {
            "predicate": "A customer inquires about upgrading their service package",
            "content": "Provide information on available upgrade options and benefits",
        },
        # {
        #     "predicate": "A customer needs assistance with understanding their billing statements", # noqa
        #     "content": "Guide them through the billing details and explain any charges",
        # },
        # {
        #     "predicate": "A customer expresses satisfaction with the service",
        #     "content": "encourage them to leave a review or testimonial",
        # },
        # {
        #     "predicate": "A customer refers another potential client",
        #     "content": "initiate the referral rewards process",
        # },
        # {
        #     "predicate": "A customer exceeds their data storage limit",
        #     "content": "Prompt them to upgrade their subscription plan",
        # },
        # {
        #     "predicate": "Promoting customer retention and satisfaction",
        #     "content": "Offer a temporary data limit extension without requiring an upgrade",
        # },
        # {
        #     "predicate": "Receiving feedback on a new feature",
        #     "content": "encourage users to adopt and adapt to the change as part of ongoing product",  # noqa
        # },
        # {
        #     "predicate": "Users express significant resistance to a new feature",
        #     "content": "Roll back or offer the option to revert to previous settings",
        # },
        # {
        #     "predicate": "A new software update is scheduled for release",
        #     "content": "Roll it out to all users to ensure everyone has the latest version",
        # },
        # {
        #     "predicate": "Key clients are in the middle of a critical project",
        #     "content": "Delay software updates to avoid disrupting their operations",
        # },
        # {
        #     "predicate": "The financial quarter ends",
        #     "content": "Finalize all pending transactions and close the books",
        # },
        # {
        #     "predicate": "A new financial regulation is implemented at the end of the quarter",
        #     "content": "re-evaluate all transactions from that quarter before closing the books",
        # },
        # {
        #     "predicate": "A customer is located in a region with strict data sovereignty laws",
        #     "content": "Store and process all customer data locally as required by law",
        # },
        # {
        #     "predicate": "The company's policy is to centralize data processing in a single, cost-effective location",  # noqa
        #     "content": "Consolidate data handling to enhance efficiency",
        # },
        # {
        #     "predicate": "A customer's contract is up for renewal during a market downturn",
        #     "content": "Offer discounts and incentives to ensure renewal",
        # },
        # {
        #     "predicate": "The company’s financial performance targets require maximizing revenue",
        #     "content": "avoid discounts and push for higher-priced contracts",
        # },
    ]:
        guidelines.append(sync_await(create_guideline(**guideline_params)))

    return guidelines


@fixture
def guidelines_without_contradictions(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: str,
) -> list[Guideline]:
    guideline_store = container[GuidelineStore]

    async def create_guideline(predicate: str, content: str) -> Guideline:
        return await guideline_store.create_guideline(
            guideline_set=agent_id,
            predicate=predicate,
            content=content,
        )

    guidelines: list[Guideline] = []

    for guideline_params in [
        {
            "predicate": "A customer inquires about upgrading their service package",
            "content": "Provide information on available upgrade options and benefits",
        },
        {
            "predicate": "A customer needs assistance with understanding their billing statements",
            "content": "Guide them through the billing details and explain any charges",
        },
        {
            "predicate": "A customer expresses satisfaction with the service",
            "content": "encourage them to leave a review or testimonial",
        },
        {
            "predicate": "A customer refers another potential client",
            "content": "initiate the referral rewards process",
        },
        # {
        #     "predicate": "A customer asks about the security of their data",
        #     "content": "Provide detailed information about the company’s security measures and certifications",  # noqa
        # },
        # {
        #     "predicate": "A customer inquires about compliance with specific regulations",
        #     "content": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
        # },
        # {
        #     "predicate": "A customer requests faster support response times",
        #     "content": "Explain the standard response times and efforts to improve them",
        # },
        # {
        #     "predicate": "A customer compliments the service on social media",
        #     "content": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
        # },
        # {
        #     "predicate": "A customer asks about the security of their data",
        #     "content": "Provide detailed information about the company’s security measures and certifications",  # noqa
        # },
        # {
        #     "predicate": "A customer inquires about compliance with specific regulations",
        #     "content": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
        # },
        # {
        #     "predicate": "A customer requests faster support response times",
        #     "content": "Explain the standard response times and efforts to improve them",
        # },
        # {
        #     "predicate": "A customer compliments the service on social media",
        #     "content": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
        # },
        # {
        #     "predicate": "A customer asks about the security of their data",
        #     "content": "Provide detailed information about the company’s security measures and certifications",  # noqa
        # },
        # {
        #     "predicate": "A customer inquires about compliance with specific regulations",
        #     "content": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
        # },
        # {
        #     "predicate": "A customer requests faster support response times",
        #     "content": "Explain the standard response times and efforts to improve them",
        # },
        # {
        #     "predicate": "A customer compliments the service on social media",
        #     "content": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
        # },
    ]:
        guidelines.append(sync_await(create_guideline(**guideline_params)))

    return guidelines


def test_no_contradictions_found(
    sync_await: SyncAwaiter,
    guidelines_without_contradictions: list[Guideline],
) -> None:
    coherence_checker = CoherenceChecker()
    result = sync_await(coherence_checker.evaluate_coherence(guidelines_without_contradictions, []))
    assert nlp_test(
        f"Given the result of evaluate coherence for a set of guidelines:\n {result}",
        "No coherence contradictions have been found.",
    )


def test_multiple_contradictions_found(
    sync_await: SyncAwaiter,
    guidelines_with_contradictions: list[Guideline],
) -> None:
    coherence_checker = CoherenceChecker()
    result = sync_await(coherence_checker.evaluate_coherence(guidelines_with_contradictions, []))
    assert nlp_test(
        f"Given the result of evaluate coherence for a set of guidelines:\n {result}",
        "10 contradictions have been found.",
    )
