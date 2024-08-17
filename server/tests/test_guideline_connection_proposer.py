from dataclasses import dataclass
from lagom import Container
from pytest import fixture, mark

from emcie.server.core.agents import AgentId, AgentStore
from emcie.server.core.guidelines import Guideline, GuidelineStore

from emcie.server.guideline_connection_proposer import GuidelineConnectionProposer
from emcie.server.logger import Logger
from tests.test_utilities import SyncAwaiter


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
    source_guideline_definition: dict[str, str],
    target_guideline_definition: dict[str, str],
) -> None:
    guideline_store = context.container[GuidelineStore]

    source_guideline = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate=source_guideline_definition["predicate"],
            content=source_guideline_definition["content"],
        )
    )
    target_guideline = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate=target_guideline_definition["predicate"],
            content=target_guideline_definition["content"],
        )
    )

    connection_proposer = GuidelineConnectionProposer(context.container[Logger])

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                [source_guideline, target_guideline],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline.id
    assert connection_propositions[0].target == target_guideline.id
    assert connection_propositions[0].kind == "entails"


@mark.parametrize(
    (
        "source_guideline_definition",
        "target_guideline_definition",
    ),
    [
        (
            {
                "predicate": "The user requests technical support",
                "content": "provide the support contact details",
            },
            {
                "predicate": "providing support contact details",
                "content": "consider checking the troubleshooting guide first",
            },
        ),
        (
            {
                "predicate": "The user inquires about office hours",
                "content": "tell them the office hours",
            },
            {
                "predicate": "mentioning office hours",
                "content": "suggest the best time to visit for quicker service",
            },
        ),
    ],
)
def test_that_a_suggestion_connection_is_proposed_for_two_guidelines_where_the_content_of_one_suggests_a_follow_up_to_the_predicate_of_the_other(
    context: _TestContext,
    source_guideline_definition: dict[str, str],
    target_guideline_definition: dict[str, str],
) -> None:
    guideline_store = context.container[GuidelineStore]

    source_guideline = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate=source_guideline_definition["predicate"],
            content=source_guideline_definition["content"],
        )
    )
    target_guideline = context.sync_await(
        guideline_store.create_guideline(
            context.agent_id,
            target_guideline_definition["predicate"],
            target_guideline_definition["content"],
        )
    )

    connection_proposer = GuidelineConnectionProposer(context.container[Logger])
    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                [source_guideline, target_guideline],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline.id
    assert connection_propositions[0].target == target_guideline.id
    assert connection_propositions[0].kind == "suggests"


def test_that_multiple_connections_are_detected_and_proposed_at_the_same_time(
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

    introduced_guidelines = list(
        map(
            lambda g: create_guideline(
                g["when"],
                g["then"],
            ),
            [
                {
                    "when": "The user requests technical support",
                    "then": "provide the support contact details",
                },
                {
                    "when": "providing support contact details",
                    "then": "consider checking the troubleshooting guide first",
                },
                {
                    "when": "The user inquires about office hours",
                    "then": "tell them the office hours",
                },
                {
                    "when": "mentioning office hours",
                    "then": "suggest the best time to visit for quicker service",
                },
                {
                    "when": "The user asks about the weather",
                    "then": "provide the current weather update",
                },
                {
                    "when": "providing the weather update",
                    "then": "mention the best time to go for a walk",
                },
                {
                    "when": "The user asks about nearby restaurants",
                    "then": "provide a list of popular restaurants",
                },
                {
                    "when": "listing restaurants",
                    "then": "highlight the one with the best reviews",
                },
            ],
        )
    )

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
        assert connection.source == pairs[i][0].id
        assert connection.target == pairs[i][1].id


def test_that_possible_connections_between_existing_guidelines_are_not_proposed(
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

    existing_guidelines = list(
        map(
            lambda g: create_guideline(
                predicate=g["when"],
                content=g["then"],
            ),
            [
                {
                    "when": "The user requests technical support",
                    "then": "provide the support contact details",
                },
                {
                    "when": "providing support contact details",
                    "then": "consider checking the troubleshooting guide first",
                },
                {
                    "when": "The user inquires about office hours",
                    "then": "tell them the office hours",
                },
                {
                    "when": "mentioning office hours",
                    "then": "suggest the best time to visit for quicker service",
                },
                {
                    "when": "The user asks about the weather",
                    "then": "provide the current weather update",
                },
                {
                    "when": "providing the weather update",
                    "then": "mention the best time to go for a walk",
                },
                {
                    "when": "The user asks about nearby restaurants",
                    "then": "provide a list of popular restaurants",
                },
                {
                    "when": "listing restaurants",
                    "then": "highlight the one with the best reviews",
                },
            ],
        )
    )

    connection_proposer = GuidelineConnectionProposer(context.container[Logger])

    connection_propositions = list(
        context.sync_await(connection_proposer.propose_connections([], existing_guidelines))
    )

    assert len(connection_propositions) == 0
