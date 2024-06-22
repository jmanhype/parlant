from dataclasses import dataclass
from lagom import Container
from pytest import fixture, mark
from emcie.server.core.agents import AgentId
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


@dataclass
class _TestContext:
    sync_await: SyncAwaiter
    container: Container
    agent_id: AgentId


@fixture
def context(sync_await: SyncAwaiter, container: Container, agent_id: AgentId) -> _TestContext:
    return _TestContext(sync_await, container, agent_id)


@fixture
def guidelines_with_contradictions(
    context: _TestContext,
) -> list[Guideline]:
    guideline_store = context.container[GuidelineStore]

    def create_guideline(predicate: str, content: str) -> Guideline:
        return context.sync_await(
            guideline_store.create_guideline(
                guideline_set=context.agent_id,
                predicate=predicate,
                content=content,
            )
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
        {
            "predicate": "A customer needs assistance with understanding their billing statements",  # noqa
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
        {
            "predicate": "A customer exceeds their data storage limit",
            "content": "Prompt them to upgrade their subscription plan",
        },
        {
            "predicate": "Promoting customer retention and satisfaction",
            "content": "Offer a temporary data limit extension without requiring an upgrade",
        },
        {
            "predicate": "Receiving feedback on a new feature",
            "content": "encourage users to adopt and adapt to the change as part of ongoing product",  # noqa
        },
    ]:
        guidelines.append(create_guideline(**guideline_params))

    return guidelines


@fixture
def guidelines_without_contradictions(
    context: _TestContext,
) -> list[Guideline]:
    guideline_store = context.container[GuidelineStore]

    def create_guideline(predicate: str, content: str) -> Guideline:
        return context.sync_await(
            guideline_store.create_guideline(
                guideline_set=context.agent_id,
                predicate=predicate,
                content=content,
            )
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
        {
            "predicate": "A customer asks about the security of their data",
            "content": "Provide detailed information about the company’s security measures and certifications",  # noqa
        },
        {
            "predicate": "A customer inquires about compliance with specific regulations",
            "content": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
        },
        {
            "predicate": "A customer requests faster support response times",
            "content": "Explain the standard response times and efforts to improve them",
        },
        {
            "predicate": "A customer compliments the service on social media",
            "content": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
        },
        {
            "predicate": "A customer asks about the security of their data",
            "content": "Provide detailed information about the company’s security measures and certifications",  # noqa
        },
        {
            "predicate": "A customer inquires about compliance with specific regulations",
            "content": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
        },
    ]:
        guidelines.append(create_guideline(**guideline_params))

    return guidelines


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A VIP customer requests a specific feature that aligns with their business needs but is not on the current product roadmap",  # noqa
                "content": "Escalate the request to product management for special consideration",
            },
            {
                "predicate": "Any customer requests a feature not available in the current version",
                "content": "Inform them about the product roadmap and upcoming features",
            },
        ),
        (
            {
                "predicate": "Any customer reports a technical issue",
                "content": "Queue the issue for resolution according to standard support protocols",
            },
            {
                "predicate": "The issue reported affects a critical operational feature for multiple clients",  # noqa
                "content": "Escalate immediately to the highest priority for resolution",
            },
        ),
    ],
)
def test_that_hierarchical_evaluator_detects_contradictions(
    context: _TestContext,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    guideline_store = context.container.resolve(GuidelineStore)
    guideline_a = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_a_definition["predicate"], guideline_a_definition["content"]
        )
    )
    guideline_b = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_b_definition["predicate"], guideline_b_definition["content"]
        )
    )
    hierarchical_contradiction_evaluator = HierarchicalContradictionEvaluator()
    contradiction_results = list(
        context.sync_await(
            hierarchical_contradiction_evaluator.evaluate(
                [guideline_a, guideline_b],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.contradiction_type == ContradictionType.HIERARCHICAL.value  # type: ignore
    assert contradiction.severity >= 5
    assert nlp_test(
        f"Here is an explanation of what {hierarchical_contradiction_evaluator.contradiction_type} type is:"  # noqa
        f"{hierarchical_contradiction_evaluator._format_contradiction_type_definition()}"
        "Here are two behavioral guidelines:"
        "a semantic contradiction test was conducted, regarding the following two behavioral guidelines:"  # noqa
        f"1. {contradiction.existing_guideline_id}\n"
        f"2. {contradiction.proposed_guideline_id}\n"
        "Here is the output explanation generated by the contradiction test:"
        f"{contradiction.rationale}",
        "A contradiction has been found and an explanation is provided as to why it is a "
        "hierarchical contradiction",
    )


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer inquires about upgrading their service package",
                "content": "Provide information on available upgrade options and benefits",
            },
            {
                "predicate": "A customer needs assistance with understanding their billing statements",  # noqa
                "content": "Guide them through the billing details and explain any charges",
            },
        ),
        (
            {
                "predicate": "A customer expresses satisfaction with the service",
                "content": "encourage them to leave a review or testimonial",
            },
            {
                "predicate": "A customer refers another potential client",
                "content": "initiate the referral rewards process",
            },
        ),
    ],
)
def test_that_hierarchical_evaluator_does_not_produce_false_positives(
    context: _TestContext,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    guideline_store = context.container.resolve(GuidelineStore)
    guideline_a = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_a_definition["predicate"], guideline_a_definition["content"]
        )
    )
    guideline_b = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_b_definition["predicate"], guideline_b_definition["content"]
        )
    )
    hierarchical_contradiction_evaluator = HierarchicalContradictionEvaluator()
    contradiction_results = list(
        context.sync_await(
            hierarchical_contradiction_evaluator.evaluate(
                [guideline_a, guideline_b],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.contradiction_type == ContradictionType.HIERARCHICAL.value  # type: ignore
    assert contradiction.severity < 5
    assert nlp_test(
        f"Here is an explanation of what {hierarchical_contradiction_evaluator.contradiction_type} type is:"  # noqa
        f"{hierarchical_contradiction_evaluator._format_contradiction_type_definition()}"
        "Here are two behavioral guidelines:"
        "a semantic contradiction test was conducted, regarding the following two behavioral guidelines:"  # noqa
        f"1. {contradiction.existing_guideline_id}\n"
        f"2. {contradiction.proposed_guideline_id}\n"
        "Here is the output explanation generated by the contradiction test:"
        f"{contradiction.rationale}",
        "No contradiction has been found between the two behavioral guidelines",
    )


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer exceeds their data storage limit",
                "content": "Prompt them to upgrade their subscription plan",
            },
            {
                "predicate": "Promoting customer retention and satisfaction",
                "content": "Offer a temporary data limit extension without requiring an upgrade",
            },
        ),
        (
            {
                "predicate": "Receiving feedback on a new feature",
                "content": "encourage users to adopt and adapt to the change as part of ongoing product",  # noqa
            },
            {
                "predicate": "Users express significant resistance to a new feature",
                "content": "Roll back or offer the option to revert to previous settings",
            },
        ),
    ],
)
def test_that_parallel_evaluator_detects_contradictions(
    context: _TestContext,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    guideline_store = context.container.resolve(GuidelineStore)
    guideline_a = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_a_definition["predicate"], guideline_a_definition["content"]
        )
    )
    guideline_b = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_b_definition["predicate"], guideline_b_definition["content"]
        )
    )
    parallel_contradiction_evaluator = ParallelContradictionEvaluator()
    contradiction_results = list(
        context.sync_await(
            parallel_contradiction_evaluator.evaluate(
                [guideline_a, guideline_b],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.contradiction_type == ContradictionType.PARALLEL.value  # type: ignore
    assert contradiction.severity >= 5
    assert nlp_test(
        f"Here is an explanation of what {parallel_contradiction_evaluator.contradiction_type.value} type is:"  # noqa
        f"{parallel_contradiction_evaluator._format_contradiction_type_definition()}"
        "Here are two behavioral guidelines:"
        "a semantic contradiction test was conducted, regarding the following two behavioral guidelines:"  # noqa
        f"1. {contradiction.existing_guideline_id}\n"
        f"2. {contradiction.proposed_guideline_id}\n"
        "Here is the output explanation generated by the contradiction test:"
        f"{contradiction.rationale}",
        "A contradiction has been found and an explanation is provided as to why it is a "
        "parallel contradiction",
    )


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer asks about the security of their data",
                "content": "Provide detailed information about the company’s security measures and certifications",  # noqa
            },
            {
                "predicate": "A customer inquires about compliance with specific regulations",
                "content": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
            },  # noqa
        ),
        (
            {
                "predicate": "A customer requests faster support response times",
                "content": "Explain the standard response times and efforts to improve them",
            },
            {
                "predicate": "A customer compliments the service on social media",
                "content": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
            },
        ),
    ],
)
def test_that_parallel_evaluator_does_not_produce_false_positives(
    context: _TestContext,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    guideline_store = context.container.resolve(GuidelineStore)
    guideline_a = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_a_definition["predicate"], guideline_a_definition["content"]
        )
    )
    guideline_b = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_b_definition["predicate"], guideline_b_definition["content"]
        )
    )
    parallel_contradiction_evaluator = ParallelContradictionEvaluator()
    contradiction_results = list(
        context.sync_await(
            parallel_contradiction_evaluator.evaluate(
                [guideline_a, guideline_b],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.contradiction_type == ContradictionType.PARALLEL.value  # type: ignore
    assert contradiction.severity < 5
    assert nlp_test(
        f"Here is an explanation of what {parallel_contradiction_evaluator.contradiction_type.value} type is:"  # noqa
        f"{parallel_contradiction_evaluator._format_contradiction_type_definition()}"
        "Here are two behavioral guidelines:"
        "a semantic contradiction test was conducted, regarding the following two behavioral guidelines:"  # noqa
        f"1. {contradiction.existing_guideline_id}\n"
        f"2. {contradiction.proposed_guideline_id}\n"
        "Here is the output explanation generated by the contradiction test:"
        f"{contradiction.rationale}",
        "No contradiction has been found between the two behavioral guidelines",
    )


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A new software update is scheduled for release",
                "content": "Roll it out to all users to ensure everyone has the latest version",
            },
            {
                "predicate": "Key clients are in the middle of a critical project",
                "content": "Delay software updates to avoid disrupting their operations",
            },
        ),
        (
            {
                "predicate": "The financial quarter ends",
                "content": "Finalize all pending transactions and close the books",
            },
            {
                "predicate": "A new financial regulation is implemented at the end of the quarter",
                "content": "re-evaluate all transactions from that quarter before closing the books",  # noqa
            },
        ),
    ],
)
def test_that_temporal_evaluator_detects_contradictions(
    context: _TestContext,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    guideline_store = context.container.resolve(GuidelineStore)
    guideline_a = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_a_definition["predicate"], guideline_a_definition["content"]
        )
    )
    guideline_b = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_b_definition["predicate"], guideline_b_definition["content"]
        )
    )
    temporal_contradiction_evaluator = TemporalContradictionEvaluator()
    contradiction_results = list(
        context.sync_await(
            temporal_contradiction_evaluator.evaluate(
                [guideline_a, guideline_b],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.contradiction_type == ContradictionType.TEMPORAL.value  # type: ignore
    assert contradiction.severity >= 5
    assert nlp_test(
        f"Here is an explanation of what {temporal_contradiction_evaluator.contradiction_type.value} type is:\n"  # noqa
        f"{temporal_contradiction_evaluator._format_contradiction_type_definition()}"
        "Here are two behavioral guidelines:"
        "a semantic contradiction test was conducted, regarding the following two behavioral guidelines:"  # noqa
        f"1. {contradiction.existing_guideline_id}\n"
        f"2. {contradiction.proposed_guideline_id}\n"
        "Here is the output explanation generated by the contradiction test:"
        f"{contradiction.rationale}",
        "A contradiction has been found and an explanation is provided as to why it is a "
        "temporal contradiction",
    )


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer asks about the security of their data",
                "content": "Provide detailed information about the company’s security measures and certifications",  # noqa
            },
            {
                "predicate": "A customer inquires about compliance with specific regulations",
                "content": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
            },  # noqa
        ),
        (
            {
                "predicate": "A customer requests faster support response times",
                "content": "Explain the standard response times and efforts to improve them",
            },
            {
                "predicate": "A customer compliments the service on social media",
                "content": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
            },
        ),
    ],
)
def test_that_temporal_evaluator_does_not_produce_false_positives(
    context: _TestContext,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    guideline_store = context.container.resolve(GuidelineStore)
    guideline_a = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_a_definition["predicate"], guideline_a_definition["content"]
        )
    )
    guideline_b = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_b_definition["predicate"], guideline_b_definition["content"]
        )
    )
    temporal_contradiction_evaluator = TemporalContradictionEvaluator()
    contradiction_results = list(
        context.sync_await(
            temporal_contradiction_evaluator.evaluate(
                [guideline_a, guideline_b],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.contradiction_type == ContradictionType.TEMPORAL.value  # type: ignore
    assert contradiction.severity < 5
    assert nlp_test(
        f"Here is an explanation of what {temporal_contradiction_evaluator.contradiction_type.value} type is:"  # noqa
        f"{temporal_contradiction_evaluator._format_contradiction_type_definition()}"
        "Here are two behavioral guidelines:"
        "a semantic contradiction test was conducted, regarding the following two behavioral guidelines:"  # noqa
        f"1. {contradiction.existing_guideline_id}\n"
        f"2. {contradiction.proposed_guideline_id}\n"
        "Here is the output explanation generated by the contradiction test:"
        f"{contradiction.rationale}",
        "No contradiction has been found between the two behavioral guidelines",
    )


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer is located in a region with strict data sovereignty laws",
                "content": "Store and process all customer data locally as required by law",
            },
            {
                "predicate": "The company's policy is to centralize data processing in a single, cost-effective location",  # noqa
                "content": "Consolidate data handling to enhance efficiency",
            },
        ),
        (
            {
                "predicate": "A customer's contract is up for renewal during a market downturn",
                "content": "Offer discounts and incentives to ensure renewal",
            },
            {
                "predicate": "The company’s financial performance targets require maximizing revenue",  # noqa
                "content": "avoid discounts and push for higher-priced contracts",
            },
        ),
    ],
)
def test_that_contextual_evaluator_detects_contradictions(
    context: _TestContext,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    guideline_store = context.container.resolve(GuidelineStore)
    guideline_a = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_a_definition["predicate"], guideline_a_definition["content"]
        )
    )
    guideline_b = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_b_definition["predicate"], guideline_b_definition["content"]
        )
    )
    contextual_contradiction_evaluator = ContextualContradictionEvaluator()
    contradiction_results = list(
        context.sync_await(
            contextual_contradiction_evaluator.evaluate(
                [guideline_a, guideline_b],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.contradiction_type == ContradictionType.CONTEXTUAL.value  # type: ignore
    assert contradiction.severity >= 5
    assert nlp_test(
        f"Here is an explanation of what {contextual_contradiction_evaluator.contradiction_type} type is:"  # noqa
        f"{contextual_contradiction_evaluator._format_contradiction_type_definition()}"
        "Here are two behavioral guidelines:"
        "a semantic contradiction test was conducted, regarding the following two behavioral guidelines:"  # noqa
        f"1. {contradiction.existing_guideline_id}\n"
        f"2. {contradiction.proposed_guideline_id}\n"
        "Here is the output explanation generated by the contradiction test:"
        f"{contradiction.rationale}",
        "A contradiction has been found and an explanation is provided as to why it is a "
        "contextual contradiction",
    )


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer asks about the security of their data",
                "content": "Provide detailed information about the company’s security measures and certifications",  # noqa
            },
            {
                "predicate": "A customer inquires about compliance with specific regulations",
                "content": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
            },
        ),
        (
            {
                "predicate": "A customer requests faster support response times",
                "content": "Explain the standard response times and efforts to improve them",
            },
            {
                "predicate": "A customer compliments the service on social media",
                "content": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
            },
        ),
    ],
)
def test_that_contextual_evaluator_does_not_produce_false_positives(
    context: _TestContext,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    guideline_store = context.container.resolve(GuidelineStore)
    guideline_a = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_a_definition["predicate"], guideline_a_definition["content"]
        )
    )
    guideline_b = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id, guideline_b_definition["predicate"], guideline_b_definition["content"]
        )
    )
    contextual_contradiction_evaluator = ContextualContradictionEvaluator()
    contradiction_results = list(
        context.sync_await(
            contextual_contradiction_evaluator.evaluate(
                [guideline_a, guideline_b],
                [],
            )
        )
    )
    assert len(contradiction_results) == 1
    contradiction = contradiction_results[0]
    assert contradiction.contradiction_type == ContradictionType.CONTEXTUAL.value  # type: ignore
    assert contradiction.severity < 5
    assert nlp_test(
        "Here are two behavioral guidelines:"
        "a semantic contradiction test was conducted, regarding the following two behavioral guidelines:"  # noqa
        f"1. {contradiction.existing_guideline_id}\n"
        f"2. {contradiction.proposed_guideline_id}\n"
        "Here is the output explanation generated by the contradiction test:"
        f"{contradiction.rationale}",
        "No contradiction has been found between the two behavioral guidelines",
    )


def test_that_coherence_check_does_not_produce_false_positives(
    sync_await: SyncAwaiter,
    guidelines_without_contradictions: list[Guideline],
) -> None:
    coherence_checker = CoherenceChecker()
    contradiction_results = sync_await(
        coherence_checker.evaluate_coherence(guidelines_without_contradictions, [])
    )
    assert len(list(filter(lambda c: c.severity >= 5, contradiction_results))) == 0


def test_that_coherence_check_produces_multiple_contradictions(
    sync_await: SyncAwaiter,
    guidelines_with_contradictions: list[Guideline],
) -> None:
    coherence_checker = CoherenceChecker()
    contradiction_results = sync_await(
        coherence_checker.evaluate_coherence(guidelines_with_contradictions, [])
    )
    assert len(list(filter(lambda c: c.severity >= 5, contradiction_results))) == 12


def test_that_existing_guidelines_are_not_evaluated_as_proposed_guidelines(
    context: _TestContext,
) -> None:
    guideline_store = context.container[GuidelineStore]

    def create_guideline(predicate: str, content: str) -> Guideline:
        return context.sync_await(
            guideline_store.create_guideline(
                guideline_set=context.agent_id,
                predicate=predicate,
                content=content,
            )
        )

    proposed_guideline_definiton = {
        "predicate": "A VIP customer requests a specific feature that aligns with their business needs but is not on the current product roadmap",  # noqa
        "content": "Escalate the request to product management for special consideration",
    }
    existing_guideline_definiton_1 = {
        "predicate": "Any customer requests a feature not available in the current version",
        "content": "Inform them about the product roadmap and upcoming features",
    }
    existing_guideline_definiton_2 = {
        "predicate": "A customer with low ranking requests a specific feature that does not aligns the current product roadmap",  # noqa
        "content": "Inform them about the current roadmap and advise them to inquire again in one year.",  # noqa
    }
    proposed_guideline = create_guideline(**proposed_guideline_definiton)
    existing_guideline_1 = create_guideline(**existing_guideline_definiton_1)
    existing_guideline_2 = create_guideline(**existing_guideline_definiton_2)

    coherence_checker = CoherenceChecker()
    contradiction_results = list(
        context.sync_await(
            coherence_checker.evaluate_coherence(
                [proposed_guideline], [existing_guideline_1, existing_guideline_2]
            )
        )
    )
    # Hierarchical and contradiction between each existing guideline, but not between them both.
    assert contradiction_results[0].proposed_guideline_id == proposed_guideline.id
    assert contradiction_results[1].proposed_guideline_id == proposed_guideline.id
    assert contradiction_results[0].existing_guideline_id == existing_guideline_1.id
    assert contradiction_results[1].existing_guideline_id == existing_guideline_2.id
