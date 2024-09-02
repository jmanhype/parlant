from dataclasses import dataclass
from typing import Sequence
from lagom import Container
from pytest import fixture, mark
from emcie.server.core.guidelines import GuidelineData
from emcie.server.indexing.guideline_connection_proposer import GuidelineConnectionProposer
from emcie.server.logger import Logger
from tests.test_utilities import SyncAwaiter


@dataclass
class _TestContext:
    sync_await: SyncAwaiter
    container: Container


@fixture
def context(
    sync_await: SyncAwaiter,
    container: Container,
) -> _TestContext:
    return _TestContext(sync_await, container)


@mark.parametrize(
    (
        "source_guideline_definition",
        "target_guideline_definition",
    ),
    [
        (
            {
                "predicate": "the user asks about the weather",
                "content": "provide the current weather update",
            },
            {
                "predicate": "providing the weather update",
                "content": "mention the best time to go for a walk",
            },
        ),
        (
            {
                "predicate": "the user asks about nearby restaurants",
                "content": "provide a list of popular restaurants",
            },
            {
                "predicate": "listing restaurants",
                "content": "highlight the one with the best reviews",
            },
        ),
    ],
)
def test_that_an_entailment_connection_is_proposed_for_two_guidelines_where_the_content_of_one_entails_the_predicate_of_the_other(
    context: _TestContext,
    source_guideline_definition: GuidelineData,
    target_guideline_definition: GuidelineData,
) -> None:
    connection_proposer = GuidelineConnectionProposer(context.container[Logger])

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                [source_guideline_definition, target_guideline_definition],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_definition
    assert connection_propositions[0].target == target_guideline_definition
    assert connection_propositions[0].kind == "entails"


@mark.parametrize(
    (
        "source_guideline_definition",
        "target_guideline_definition",
    ),
    [
        (
            {
                "guideline_set": "test-agent",
                "predicate": "the user requests technical support",
                "content": "provide the support contact details",
            },
            {
                "guideline_set": "test-agent",
                "predicate": "providing support contact details",
                "content": "consider checking the troubleshooting guide first",
            },
        ),
        (
            {
                "guideline_set": "test-agent",
                "predicate": "the user inquires about office hours",
                "content": "tell them the office hours",
            },
            {
                "guideline_set": "test-agent",
                "predicate": "mentioning office hours",
                "content": "suggest the best time to visit for quicker service",
            },
        ),
    ],
)
def test_that_a_suggestion_connection_is_proposed_for_two_guidelines_where_the_content_of_one_suggests_a_follow_up_to_the_predicate_of_the_other(
    context: _TestContext,
    source_guideline_definition: GuidelineData,
    target_guideline_definition: GuidelineData,
) -> None:
    connection_proposer = GuidelineConnectionProposer(context.container[Logger])
    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                [source_guideline_definition, target_guideline_definition],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_definition
    assert connection_propositions[0].target == target_guideline_definition
    assert connection_propositions[0].kind == "suggests"


def test_that_multiple_connections_are_detected_and_proposed_at_the_same_time(
    context: _TestContext,
) -> None:
    introduced_guidelines: Sequence[GuidelineData] = [
        GuidelineData(predicate=i["predicate"], content=i["content"])
        for i in [
            {
                "predicate": "the user requests technical support",
                "content": "provide the support contact details",
            },
            {
                "predicate": "providing support contact details",
                "content": "consider checking the troubleshooting guide first",
            },
            {
                "predicate": "the user inquires about office hours",
                "content": "tell them the office hours",
            },
            {
                "predicate": "mentioning office hours",
                "content": "suggest the best time to visit for quicker service",
            },
            {
                "predicate": "the user asks about the weather",
                "content": "provide the current weather update",
            },
            {
                "predicate": "providing the weather update",
                "content": "mention the best time to go for a walk",
            },
            {
                "predicate": "the user asks about nearby restaurants",
                "content": "provide a list of popular restaurants",
            },
            {
                "predicate": "listing restaurants",
                "content": "highlight the one with the best reviews",
            },
        ]
    ]

    connection_proposer = GuidelineConnectionProposer(context.container[Logger])

    connection_propositions = list(
        context.sync_await(connection_proposer.propose_connections(introduced_guidelines, []))
    )

    assert len(connection_propositions) == len(introduced_guidelines) // 2

    pairs = [
        (introduced_guidelines[i], introduced_guidelines[i + 1])
        for i in range(0, len(introduced_guidelines), 2)
    ]

    for i, connection in enumerate(connection_propositions):
        assert connection.source == pairs[i][0]
        assert connection.target == pairs[i][1]


def test_that_possible_connections_between_existing_guidelines_are_not_proposed(
    context: _TestContext,
) -> None:
    existing_guidelines: Sequence[GuidelineData] = [
        GuidelineData(predicate=i["predicate"], content=i["content"])
        for i in [
            {
                "predicate": "the user requests technical support",
                "content": "provide the support contact details",
            },
            {
                "predicate": "providing support contact details",
                "content": "consider checking the troubleshooting guide first",
            },
            {
                "predicate": "the user inquires about office hours",
                "content": "tell them the office hours",
            },
            {
                "predicate": "mentioning office hours",
                "content": "suggest the best time to visit for quicker service",
            },
            {
                "predicate": "the user asks about the weather",
                "content": "provide the current weather update",
            },
            {
                "predicate": "providing the weather update",
                "content": "mention the best time to go for a walk",
            },
            {
                "predicate": "the user asks about nearby restaurants",
                "content": "provide a list of popular restaurants",
            },
            {
                "predicate": "listing restaurants",
                "content": "highlight the one with the best reviews",
            },
        ]
    ]

    connection_proposer = GuidelineConnectionProposer(context.container[Logger])

    connection_propositions = list(
        context.sync_await(connection_proposer.propose_connections([], existing_guidelines))
    )

    assert len(connection_propositions) == 0
