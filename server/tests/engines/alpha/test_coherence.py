from lagom import Container
from pytest import mark

from emcie.server.core.guidelines import GuidelineStore
from emcie.server.engines.alpha.coherence_checker import (
    CoherenceContradictionType,
    ContextualContradictionEvaluator,
    HierarchicalContradictionEvaluator,
    ParallelContradictionEvaluator,
    TemporalContradictionEvaluator,
)
from tests.test_utilities import SyncAwaiter, nlp_test


@mark.parametrize(
    (
        "reference_guideline_predicate",
        "reference_guideline_content",
        "candidate_guideline_predicate",
        "candidate_guideline_content",
        "expected_contradiction",
    ),
    [
        (
            "Any customer requests a feature not available in the current version",
            "Inform them about the product roadmap and upcoming features",
            "A VIP customer requests a specific feature that aligns with their business needs but"
            " is not on the current product roadmap",
            "Escalate the request to product management for special consideration",
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
    contradiction_result = list(
        sync_await(
            hierarchical_contradiction_evaluator.evaluate(
                [reference_guideline],
                candidate_guideline,
            )
        )
    )[0]
    assert (
        contradiction_result.coherence_contradiction_type == CoherenceContradictionType.HIERARCHICAL
    )
    if expected_contradiction:
        assert contradiction_result.contradiction_level >= 8
        assert nlp_test(
            "Given the following two rules:\n"
            f"1. {contradiction_result.reference_guideline_id}\n"
            f"2. {contradiction_result.candidate_guideline_id}\n"
            "Following rationale if the two rules have a hierarchical coherence contradiction:\n"
            f"{contradiction_result.rationale}",
            "Contradiction has been found and an explanation is provided as to why it is a "
            "hierarchical contradiction",
        )
    else:
        assert contradiction_result.contradiction_level < 8
        assert nlp_test(
            contradiction_result.rationale, "No significant contradiction has been found."
        )


@mark.parametrize(
    (
        "reference_guideline_predicate",
        "reference_guideline_content",
        "candidate_guideline_predicate",
        "candidate_guideline_content",
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
    contradiction_result = list(
        sync_await(
            parallel_contradiction_evaluator.evaluate(
                [reference_guideline],
                candidate_guideline,
            )
        )
    )[0]
    assert contradiction_result.coherence_contradiction_type == CoherenceContradictionType.PARALLEL
    if expected_contradiction:
        assert contradiction_result.contradiction_level >= 8
        assert nlp_test(
            "Given the following two rules:\n"
            f"1. {contradiction_result.reference_guideline_id}\n"
            f"2. {contradiction_result.candidate_guideline_id}\n"
            "Following rationale if the two rules have a parallel coherence contradiction:\n"
            f"{contradiction_result.rationale}",
            "Contradiction has been found and an explanation is "
            "provided as to why it is a parallel contradiction",
        )
    else:
        assert contradiction_result.contradiction_level < 8
        assert nlp_test(
            contradiction_result.rationale, "No significant contradiction has been found."
        )


@mark.parametrize(
    (
        "reference_guideline_predicate",
        "reference_guideline_content",
        "candidate_guideline_predicate",
        "candidate_guideline_content",
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
    temporal_contradiction_evaluator = TemporalContradictionEvaluator()
    contradiction_result = list(
        sync_await(
            temporal_contradiction_evaluator.evaluate(
                [reference_guideline],
                candidate_guideline,
            )
        )
    )[0]
    assert contradiction_result.coherence_contradiction_type == CoherenceContradictionType.TEMPORAL
    if expected_contradiction:
        assert contradiction_result.contradiction_level >= 8
        assert nlp_test(
            "Given the following two rules:\n"
            f"1. {contradiction_result.reference_guideline_id}\n"
            f"2. {contradiction_result.candidate_guideline_id}\n"
            "Following rationale if the two rules have a temporal coherence contradiction:\n"
            f"{contradiction_result.rationale}",
            "Contradiction has been found and an explanation "
            "is provided as to why it is a temporal contradiction",
        )
    else:
        assert contradiction_result.contradiction_level < 8
        assert nlp_test(
            contradiction_result.rationale, "No significant contradiction has been found."
        )


@mark.parametrize(
    (
        "reference_guideline_predicate",
        "reference_guideline_content",
        "candidate_guideline_predicate",
        "candidate_guideline_content",
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
    reference_guideline_id = sync_await(
        guideline_store.create_guideline(
            agent_id, reference_guideline_predicate, reference_guideline_content
        )
    )
    candidate_guideline_id = sync_await(
        guideline_store.create_guideline(
            agent_id, candidate_guideline_predicate, candidate_guideline_content
        )
    )
    contextual_contradiction_evaluator = ContextualContradictionEvaluator()
    contradiction_result = list(
        sync_await(
            contextual_contradiction_evaluator.evaluate(
                [reference_guideline_id],
                candidate_guideline_id,
            )
        )
    )[0]
    assert (
        contradiction_result.coherence_contradiction_type == CoherenceContradictionType.CONTEXTUAL
    )
    if expected_contradiction:
        assert contradiction_result.contradiction_level >= 8
        assert nlp_test(
            "Given the following two rules:\n"
            f"1. {contradiction_result.reference_guideline_id}\n"
            f"2. {contradiction_result.candidate_guideline_id}\n"
            "Following rationale if the two rules have a contexutal coherence contradiction:\n"
            f"{contradiction_result.rationale}",
            "Contradiction has been found and an explanation is provided as to why it is a contexutal contradiction",  # noqa
        )
    else:
        assert contradiction_result.contradiction_level < 8
        assert nlp_test(
            "Rationale provided for the contextual coherence check between two rules:"
            f"\n{contradiction_result.rationale}",
            "No significant contradiction has been found.",
        )
