from datetime import datetime, timezone
from dataclasses import dataclass
from lagom import Container
from pytest import fixture, mark

from emcie.server.core.agents import Agent, AgentId, AgentStore

# from emcie.server.core.nlp.generation import SchematicGenerator
from emcie.server.core.guidelines import GuidelineContent
from emcie.server.core.terminology import TerminologyStore

# from emcie.server.core.logging import Logger
from emcie.server.core.services.indexing.coherence_checker import (
    CoherenceChecker,
    IncoherenceKind,
)

from tests.test_utilities import SyncAwaiter, nlp_test


@fixture
def agent_id(
    container: Container,
    sync_await: SyncAwaiter,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent(name="test-agent"))
    return agent.id


@dataclass
class _TestContext:
    sync_await: SyncAwaiter
    container: Container
    agent_id: AgentId


@fixture
def context(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: AgentId,
) -> _TestContext:
    return _TestContext(sync_await, container, agent_id)


@fixture
def guidelines_with_contradictions() -> list[GuidelineContent]:
    guidelines: list[GuidelineContent] = []

    for guideline_params in [
        {
            "predicate": "Asked for UPS shipping",  # noqa
            "action": "Send UPS a request and inform the client that the order would arrive in a few days",
        },
        {
            "predicate": "Asked for express shipping",  # noqa
            "action": "register the order and inform the client that the order would arrive tomorrow",
        },
        {
            "predicate": "Asked for delayed shipping",
            "action": "inform the client that the order would arrive in the next calandar year",
        },
        {
            "predicate": "The client stops responding midorder",  # noqa
            "action": "save the client's order and notify them that it has not be shipped yet",
        },
        {
            "predicate": "The client refuses to give their address",
            "action": "cancel the order and notify the client",  # noqa
        },
    ]:
        guidelines.append(
            GuidelineContent(
                predicate=guideline_params["predicate"], action=guideline_params["action"]
            )
        )

    return guidelines


@fixture
def guidelines_without_contradictions() -> list[GuidelineContent]:
    guidelines: list[GuidelineContent] = []

    for guideline_params in [
        {
            "predicate": "A customer inquires about upgrading their service package",
            "action": "Provide information on available upgrade options and benefits",
        },
        {
            "predicate": "A customer needs assistance with understanding their billing statements",
            "action": "Guide them through the billing details and explain any charges",
        },
        {
            "predicate": "A customer expresses satisfaction with the service",
            "action": "encourage them to leave a review or testimonial",
        },
        {
            "predicate": "A customer refers another potential client",
            "action": "initiate the referral rewards process",
        },
        {
            "predicate": "A customer asks about the security of their data",
            "action": "Provide detailed information about the company’s security measures and certifications",  # noqa
        },
        {
            "predicate": "A customer inquires about compliance with specific regulations",
            "action": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
        },
        {
            "predicate": "A customer requests faster support response times",
            "action": "Explain the standard response times and efforts to improve them",
        },
        {
            "predicate": "A customer compliments the service on social media",
            "action": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
        },
        {
            "predicate": "A customer asks about the security of their data",
            "action": "Provide detailed information about the company’s security measures and certifications",  # noqa
        },
        {
            "predicate": "A customer inquires about compliance with specific regulations",
            "action": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
        },
    ]:
        guidelines.append(
            GuidelineContent(
                predicate=guideline_params["predicate"], action=guideline_params["action"]
            )
        )

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
                "action": "Escalate the request to product management for special consideration",
            },
            {
                "predicate": "Any customer requests a feature not available in the current version",
                "action": "Inform them that upcoming features are added only according to the roadmap",
            },
        ),
        (
            {
                "predicate": "Any customer reports a technical issue",
                "action": "Queue the issue for resolution according to standard support protocols",
            },
            {
                "predicate": "An issue which affects a critical operational feature for multiple clients is reported",  # noqa
                "action": "Escalate immediately to the highest priority for resolution",
            },
        ),
    ],
)
def test_that_contradicting_guidelines_with_hierarchical_whens_are_detected(
    context: _TestContext,
    agent: Agent,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate=guideline_a_definition["predicate"], action=guideline_a_definition["action"]
    )

    guideline_b = GuidelineContent(
        predicate=guideline_b_definition["predicate"], action=guideline_b_definition["action"]
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.STRICT


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer exceeds their data storage limit",
                "action": "Prompt them to upgrade their subscription plan",
            },
            {
                "predicate": "Promoting customer retention and satisfaction",
                "action": "Offer a temporary data limit extension without requiring an upgrade",
            },
        ),
        (
            {
                "predicate": "A user expresses dissatisfaction with our new design",
                "action": "encourage users to adopt and adapt to the change as part of ongoing product",
            },
            {
                "predicate": "A user requests a feature that is no longer available",
                "action": "Roll back or offer the option to revert to previous settings",
            },
        ),
    ],
)
def test_that_potential_contradictions_are_detected(
    context: _TestContext,
    agent: Agent,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate=guideline_a_definition["predicate"], action=guideline_a_definition["action"]
    )

    guideline_b = GuidelineContent(
        predicate=guideline_b_definition["predicate"], action=guideline_b_definition["action"]
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.CONTINGENT


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A new software update is scheduled for release during the latter half of the year",
                "action": "Roll it out to all users to ensure everyone has the latest version",
            },
            {
                "predicate": "The month is Novemeber",
                "action": "Delay software updates to avoid disrupting their operations",
            },
        ),
        (
            {
                "predicate": "The financial quarter ends",
                "action": "Finalize all pending transactions and close the books",
            },
            {
                "predicate": "A new financial regulation is implemented at the end of the quarter",
                "action": "re-evaluate all transactions from that quarter before closing the books",  # noqa
            },
        ),
    ],
)
def test_that_temporal_contradictions_are_detected(
    context: _TestContext,
    agent: Agent,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate=guideline_a_definition["predicate"], action=guideline_a_definition["action"]
    )

    guideline_b = GuidelineContent(
        predicate=guideline_b_definition["predicate"], action=guideline_b_definition["action"]
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.STRICT


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer is located in a region with strict data sovereignty laws",
                "action": "Store and process all customer data locally as required by law",
            },
            {
                "predicate": "The company's policy is to centralize data processing in a single, cost-effective location",  # noqa
                "action": "Consolidate data handling to enhance efficiency",
            },
        ),
        (
            {
                "predicate": "A customer's contract is up for renewal during a market downturn",
                "action": "Offer discounts and incentives to ensure renewal",
            },
            {
                "predicate": "The company’s financial performance targets require maximizing revenue",  # noqa
                "action": "avoid discounts and push for higher-priced contracts",
            },
        ),
    ],
)
def test_that_contextual_contradictions_are_detected_as_contingent_incoherence(
    context: _TestContext,
    agent: Agent,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate=guideline_a_definition["predicate"], action=guideline_a_definition["action"]
    )

    guideline_b = GuidelineContent(
        predicate=guideline_b_definition["predicate"], action=guideline_b_definition["action"]
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.CONTINGENT


@mark.parametrize(
    (
        "guideline_a_definition",
        "guideline_b_definition",
    ),
    [
        (
            {
                "predicate": "A customer asks about the security of their data",
                "action": "Provide detailed information about the company’s security measures and certifications",  # noqa
            },
            {
                "predicate": "A customer inquires about compliance with specific regulations",
                "action": "Direct them to documentation detailing the company’s compliance with those regulations",  # noqa
            },
        ),
        (
            {
                "predicate": "A customer requests faster support response times",
                "action": "Explain the standard response times and efforts to improve them",
            },
            {
                "predicate": "A customer compliments the service on social media",
                "action": "Thank them publicly and encourage them to share more about their positive experience",  # noqa
            },
        ),
    ],
)
def test_that_non_contradicting_guidelines_arent_detected(
    context: _TestContext,
    agent: Agent,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate=guideline_a_definition["predicate"], action=guideline_a_definition["action"]
    )

    guideline_b = GuidelineContent(
        predicate=guideline_b_definition["predicate"], action=guideline_b_definition["action"]
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 0


def test_that_suggestive_predicates_with_contradicting_actions_are_detected_as_contingent_incoherencies(
    context: _TestContext,
    agent: Agent,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate="Recommending pizza toppings", action="Recommend mushrooms as they are healthy"
    )

    guideline_b = GuidelineContent(
        predicate="Asked for our pizza topping selection",
        action="list the possible toppings and recommend olives",
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.CONTINGENT


def test_that_logically_contradicting_actions_are_detected_as_incoherencies(
    context: _TestContext,
    agent: Agent,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate="Recommending pizza toppings", action="Recommend tomatoes"
    )

    guideline_b = GuidelineContent(
        predicate="asked about our toppings while inventory indicates that we are almost out of tomatoes",
        action="mention that we are out of tomatoes",
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.CONTINGENT


def test_that_entailing_predicates_with_unrelated_actions_arent_false_positives(
    context: _TestContext,
    agent: Agent,
    guideline_a_definition: dict[str, str],
    guideline_b_definition: dict[str, str],
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate="ordering tickets for a movie",
        action="check if the customer is eligible for a discount",
    )

    guideline_b = GuidelineContent(
        predicate="buying tickets for rated R movies",
        action="ask the customer for identification",
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 0


def test_that_contradicting_actions_that_are_contextualized_by_their_prediates_are_detected(
    context: _TestContext,
    agent: Agent,
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate="asked to schedule an appointment for the weekend",
        action="alert the customer about our weekend hours and schedule the appointment",
    )

    guideline_b = GuidelineContent(
        predicate="asked for an appointment with a physician",
        action="schedule a physician appointment for the next available Monday",
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.CONTINGENT


def test_that_many_non_contradicting_guidelines_are_not_causing_false_positive(
    context: _TestContext,
    agent: Agent,
    guidelines_without_contradictions: list[GuidelineContent],
) -> None:
    coherence_checker = context.container[CoherenceChecker]

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                guidelines_without_contradictions,
            )
        )
    )

    assert len(contradiction_results) == 0


def test_that_many_contradicting_guidelines_are_detected(
    context: _TestContext,
    agent: Agent,
    guidelines_with_contradictions: list[GuidelineContent],
) -> None:
    coherence_checker = context.container[CoherenceChecker]

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                guidelines_with_contradictions,
            )
        )
    )

    n = len(guidelines_with_contradictions)
    assert len(contradiction_results) == n * (n + 1)

    # Tests that there's exactly 1 contradiction per pair of guidelines
    expected_pairs = set()
    for i, g1 in enumerate(guidelines_with_contradictions):
        for g2 in guidelines_with_contradictions[i + 1 :]:
            expected_pairs.add((g1, g2))

    for contradiction in contradiction_results:
        if (contradiction.guideline_a, contradiction.guideline_b) in expected_pairs:
            expected_pairs.remove((contradiction.guideline_a, contradiction.guideline_b))
        elif (contradiction.guideline_b, contradiction.guideline_a) in expected_pairs:
            expected_pairs.remove((contradiction.guideline_b, contradiction.guideline_a))
        else:
            raise AssertionError("Invalid contradiction returned from coherence checker")

    assert len(contradiction_results) == 0


def test_that_existing_guidelines_are_not_checked_against_each_other(
    context: _TestContext,
    agent: Agent,
) -> None:
    coherence_checker = context.container[CoherenceChecker]
    guideline_to_evaluate = GuidelineContent(
        predicate="a document is being discussed",
        action="provide the full document to the user",
    )

    first_guideline_to_compare = GuidelineContent(
        predicate="a client asks to summarize a document",
        action="provide a summary of the document in 100 words or less",
    )

    second_guideline_to_compare = GuidelineContent(
        predicate="the client asks for a summary of another user's medical document",
        action="refuse to share the document or its summary",
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_to_evaluate],
                [first_guideline_to_compare, second_guideline_to_compare],
            )
        )
    )

    assert len(contradiction_results) == 2
    assert contradiction_results[0].guideline_a == guideline_to_evaluate
    assert contradiction_results[0].guideline_b == first_guideline_to_compare
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.STRICT
    assert contradiction_results[1].guideline_a == guideline_to_evaluate
    assert contradiction_results[1].guideline_b == second_guideline_to_compare
    assert contradiction_results[1].ContradictionKind == IncoherenceKind.STRICT


def test_that_a_terminology_based_contradiciton_is_detected(
    context: _TestContext,
    agent: Agent,
) -> None:
    terminology_store = context.container[TerminologyStore]

    context.sync_await(
        terminology_store.create_term(
            term_set=agent.id,
            name="PAP",
            description="Pineapple pizza - a pizza topped with pineapples",
            synonyms=["PP", "pap"],
        )
    )

    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate="the client asks our recommendation",
        action="add one pap to the order",
    )

    guideline_b = GuidelineContent(
        predicate="the client asks for a specific pizza topping",
        action="Add the pizza to the order unless a fruit-based topping is requested",
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.CONTINGENT


def test_that_an_agent_description_based_contradiciton_is_detected(
    context: _TestContext,
) -> None:  # TODO ask Dor how to initiate agent
    agent = Agent(
        id=AgentId("abcd"),
        name="sparkling-water-agent",
        description="You are a helpful AI assistant for a sparkling water company. All of our products are named after famous mountians. Our competitors products are all named after bodies of water.",
        creation_utc=datetime.now(timezone.utc),
    )

    coherence_checker = context.container[CoherenceChecker]
    guideline_a = GuidelineContent(
        predicate="the client asks our recommendation",
        action="add one pap to the order",
    )

    guideline_b = GuidelineContent(
        predicate="the client asks for a specific pizza topping",
        action="Add the pizza to the order unless a fruit-based topping is requested",
    )

    contradiction_results = list(
        context.sync_await(
            coherence_checker.propose_incoherencies(
                agent,
                [guideline_a, guideline_b],
            )
        )
    )

    assert len(contradiction_results) == 1

    correct_guidelines_option_1 = (contradiction_results[0].guideline_a == guideline_a) and (
        contradiction_results[0].guideline_b == guideline_b
    )
    correct_guidelines_option_2 = (contradiction_results[0].guideline_b == guideline_a) and (
        contradiction_results[0].guideline_a == guideline_b
    )
    assert correct_guidelines_option_1 or correct_guidelines_option_2
    assert contradiction_results[0].ContradictionKind == IncoherenceKind.CONTINGENT
