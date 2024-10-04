from dataclasses import dataclass
from typing import Sequence
from lagom import Container
from pytest import fixture, mark
from emcie.server.core.agents import Agent
from emcie.server.core.guideline_connections import ConnectionKind
from emcie.server.core.guidelines import GuidelineContent
from emcie.server.core.services.indexing.guideline_connection_proposer import (
    GuidelineConnectionProposer,
)
from emcie.server.core.terminology import TerminologyStore
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


def _create_guideline_content(
    predicate: str,
    action: str,
) -> GuidelineContent:
    return GuidelineContent(predicate=predicate, action=action)


@mark.parametrize(
    (
        "source_guideline_definition",
        "target_guideline_definition",
    ),
    [
        (
            {
                "predicate": "the user asks about the weather",
                "action": "provide the current weather update",
            },
            {
                "predicate": "providing the weather update",
                "action": "mention the best time to go for a walk",
            },
        ),
        (
            {
                "predicate": "the user asks about nearby restaurants",
                "action": "provide a list of popular restaurants",
            },
            {
                "predicate": "listing restaurants",
                "action": "highlight the one with the best reviews",
            },
        ),
    ],
)
def test_that_an_entailment_connection_is_proposed_for_two_guidelines_where_the_content_of_one_entails_the_predicate_of_the_other(
    context: _TestContext,
    agent: Agent,
    source_guideline_definition: dict[str, str],
    target_guideline_definition: dict[str, str],
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        source_guideline_definition["predicate"],
        source_guideline_definition["action"],
    )

    target_guideline_content = _create_guideline_content(
        target_guideline_definition["predicate"],
        target_guideline_definition["action"],
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [target_guideline_content, source_guideline_content],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_content
    assert connection_propositions[0].target == target_guideline_content
    assert connection_propositions[0].kind == ConnectionKind.ENTAILS


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
                "action": "provide the support contact details",
            },
            {
                "guideline_set": "test-agent",
                "predicate": "providing support contact details",
                "action": "consider checking the troubleshooting guide first",
            },
        ),
        (
            {
                "guideline_set": "test-agent",
                "predicate": "the user inquires about office hours",
                "action": "tell them the office hours",
            },
            {
                "guideline_set": "test-agent",
                "predicate": "mentioning office hours",
                "action": "you may suggest the best time to visit for quicker service",
            },
        ),
    ],
)
def test_that_a_suggestion_connection_is_proposed_for_two_guidelines_where_the_content_of_one_suggests_a_follow_up_to_the_predicate_of_the_other(
    context: _TestContext,
    agent: Agent,
    source_guideline_definition: dict[str, str],
    target_guideline_definition: dict[str, str],
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        source_guideline_definition["predicate"],
        source_guideline_definition["action"],
    )

    target_guideline_content = _create_guideline_content(
        target_guideline_definition["predicate"],
        target_guideline_definition["action"],
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [
                    source_guideline_content,
                    target_guideline_content,
                ],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_content
    assert connection_propositions[0].target == target_guideline_content
    assert connection_propositions[0].kind == ConnectionKind.SUGGESTS


def test_that_multiple_connections_are_detected_and_proposed_at_the_same_time(
    context: _TestContext,
    agent: Agent,
) -> None:
    introduced_guidelines: Sequence[GuidelineContent] = [
        GuidelineContent(predicate=i["predicate"], action=i["action"])
        for i in [
            {
                "predicate": "the user requests technical support",
                "action": "provide the support contact details",
            },
            {
                "predicate": "providing support contact details",
                "action": "consider checking the troubleshooting guide first",
            },
            {
                "predicate": "the user inquires about office hours",
                "action": "tell them the office hours",
            },
            {
                "predicate": "mentioning office hours",
                "action": "suggest the best time to visit for quicker service",
            },
            {
                "predicate": "the user asks about the weather",
                "action": "provide the current weather update",
            },
            {
                "predicate": "providing the weather update",
                "action": "mention the best time to go for a walk",
            },
            {
                "predicate": "the user asks about nearby restaurants",
                "action": "provide a list of popular restaurants",
            },
            {
                "predicate": "listing restaurants",
                "action": "highlight the one with the best reviews",
            },
        ]
    ]

    connection_proposer = context.container[GuidelineConnectionProposer]

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(agent, introduced_guidelines, [])
        )
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
    agent: Agent,
) -> None:
    existing_guidelines: Sequence[GuidelineContent] = [
        GuidelineContent(predicate=i["predicate"], action=i["action"])
        for i in [
            {
                "predicate": "the user requests technical support",
                "action": "provide the support contact details",
            },
            {
                "predicate": "providing support contact details",
                "action": "consider checking the troubleshooting guide first",
            },
            {
                "predicate": "the user inquires about office hours",
                "action": "tell them the office hours",
            },
            {
                "predicate": "mentioning office hours",
                "action": "suggest the best time to visit for quicker service",
            },
            {
                "predicate": "the user asks about the weather",
                "action": "provide the current weather update",
            },
            {
                "predicate": "providing the weather update",
                "action": "mention the best time to go for a walk",
            },
            {
                "predicate": "the user asks about nearby restaurants",
                "action": "provide a list of popular restaurants",
            },
            {
                "predicate": "listing restaurants",
                "action": "highlight the one with the best reviews",
            },
        ]
    ]

    connection_proposer = context.container[GuidelineConnectionProposer]

    connection_propositions = list(
        context.sync_await(connection_proposer.propose_connections(agent, [], existing_guidelines))
    )

    assert len(connection_propositions) == 0


def test_that_a_connection_is_proposed_based_on_given_terminology(
    context: _TestContext,
    agent: Agent,
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]
    terminology_store = context.container[TerminologyStore]

    context.sync_await(
        terminology_store.create_term(
            term_set=agent.id,
            name="walnut",
            description="walnut is an altcoin",
        )
    )

    source_guideline_content = _create_guideline_content(
        "the user asks about walnut prices",
        "provide the current walnut prices",
    )

    target_guideline_content = _create_guideline_content(
        "providing altcoin prices",
        "mention that between exchanges, there can be minor differences",
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_content
    assert connection_propositions[0].target == target_guideline_content
    assert connection_propositions[0].kind == ConnectionKind.ENTAILS


def test_that_a_connection_is_proposed_based_on_multiple_terminology_terms(
    context: _TestContext,
    agent: Agent,
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]
    terminology_store = context.container[TerminologyStore]

    context.sync_await(
        terminology_store.create_term(
            term_set=agent.id,
            name="walnut",
            description="walnut is an altcoin",
        )
    )
    context.sync_await(
        terminology_store.create_term(
            term_set=agent.id,
            name="the tall tree",
            description="the tall tree is a German website for purchasing virtual goods",
        )
    )

    source_guideline_content = _create_guideline_content(
        "the user asks about getting walnuts",
        "reply that the user can buy walnuts from the tall tree",
    )

    target_guideline_content = _create_guideline_content(
        "offering to purchase altcoins from a european service",
        "warn about EU regulations",
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_content
    assert connection_propositions[0].target == target_guideline_content
    assert connection_propositions[0].kind == ConnectionKind.ENTAILS


def test_that_one_guideline_can_entail_multiple_guidelines(
    context: _TestContext,
    agent: Agent,
) -> None:
    introduced_guidelines: Sequence[GuidelineContent] = [
        _create_guideline_content(predicate=i["predicate"], action=i["action"])
        for i in [
            {
                "predicate": "the user asks for our catalouge",
                "action": "list the store's product and their pricings",
            },
            {
                "predicate": "listing store items",
                "action": "recommend promoted items",
            },
            {
                "predicate": "mentioning an item's price",
                "action": "remind the user about our summer discounts",
            },
        ]
    ]

    connection_proposer = context.container[GuidelineConnectionProposer]

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(agent, introduced_guidelines, [])
        )
    )
    assert len(connection_propositions) == 2
    assert connection_propositions[0].source == introduced_guidelines[0]
    assert connection_propositions[0].target == introduced_guidelines[1]
    assert connection_propositions[0].kind == ConnectionKind.ENTAILS
    assert connection_propositions[1].source == introduced_guidelines[0]
    assert connection_propositions[1].target == introduced_guidelines[2]
    assert connection_propositions[1].kind == ConnectionKind.ENTAILS


@mark.parametrize(
    (
        "source_guideline_definition",
        "target_guideline_definition",
    ),
    [
        (
            {
                "predicate": "the user places an order",
                "action": "direct the user to the electronic store",
            },
            {
                "predicate": "the user is ordering electronic goods",
                "action": "remind the user about our discounts",
            },
        ),
        (
            {
                "predicate": "asked about supported languages",
                "action": "explain that English is the only supported language",
            },
            {
                "predicate": "the user uses a language other than English",
                "action": "refer them to our international website",
            },
        ),
    ],
)
def test_that_entailing_whens_are_not_connected(
    context: _TestContext,
    agent: Agent,
    source_guideline_definition: dict[str, str],
    target_guideline_definition: dict[str, str],
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        source_guideline_definition["predicate"],
        source_guideline_definition["action"],
    )

    target_guideline_content = _create_guideline_content(
        target_guideline_definition["predicate"],
        target_guideline_definition["action"],
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [
                    source_guideline_content,
                    target_guideline_content,
                ],
            )
        )
    )

    assert len(connection_propositions) == 0


@mark.parametrize(
    (
        "source_guideline_definition",
        "target_guideline_definition",
    ),
    [
        (
            {
                "predicate": "mentioning office hours",
                "action": "clarify that the store is closed on weekends",
            },
            {
                "predicate": "attempting to make an order on Saturday",
                "action": "clarify that the store is closed on Saturdays",
            },
        ),
        (
            {
                "predicate": "asked if an item is available in red",
                "action": "mention that the color could be changed by request",
            },
            {
                "predicate": "Asked if an item can be colored green",
                "action": "explain that it can be colored green",
            },
        ),
    ],
)
def test_that_entailing_thens_are_not_connected(
    context: _TestContext,
    agent: Agent,
    source_guideline_definition: dict[str, str],
    target_guideline_definition: dict[str, str],
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        source_guideline_definition["predicate"],
        source_guideline_definition["action"],
    )

    target_guideline_content = _create_guideline_content(
        target_guideline_definition["predicate"],
        target_guideline_definition["action"],
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [
                    source_guideline_content,
                    target_guideline_content,
                ],
            )
        )
    )

    assert len(connection_propositions) == 0


def test_that_connection_is_proposed_for_a_sequence_where_each_guideline_entails_the_next_one_using_pronouns_from_then_to_when(
    context: _TestContext,
    agent: Agent,
) -> None:
    introduced_guidelines: Sequence[GuidelineContent] = [
        GuidelineContent(predicate=i["predicate"], action=i["action"])
        for i in [
            {
                "predicate": "the user says hello",
                "action": "say you like bananas",
            },
            {
                "predicate": "talking about bananas",
                "action": "say that they're tasty",
            },
            {
                "predicate": "you say that bananas are tasty",
                "action": "say they're better than mangoes",
            },
        ]
    ]

    connection_proposer = context.container[GuidelineConnectionProposer]

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(agent, introduced_guidelines, [])
        )
    )

    assert len(connection_propositions) == 2
    assert connection_propositions[0].source == introduced_guidelines[0]
    assert connection_propositions[0].target == introduced_guidelines[1]
    assert connection_propositions[0].kind == ConnectionKind.ENTAILS
    assert connection_propositions[1].source == introduced_guidelines[1]
    assert connection_propositions[1].target == introduced_guidelines[2]
    assert connection_propositions[1].kind == ConnectionKind.ENTAILS


def test_that_connection_is_proposed_for_a_sequence_where_each_guideline_entails_the_next_one(
    context: _TestContext,
    agent: Agent,
) -> None:
    introduced_guidelines: Sequence[GuidelineContent] = [
        GuidelineContent(predicate=i["predicate"], action=i["action"])
        for i in [
            {
                "predicate": "directing the user to a guide",
                "action": "explain how our guides directory works",
            },
            {
                "predicate": "mentioning our guide directory",
                "action": "check the operational guide",
            },
            {
                "predicate": "checking a guide",
                "action": "Make sure that the guide was updated within the last year",
            },
        ]
    ]

    connection_proposer = context.container[GuidelineConnectionProposer]

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(agent, introduced_guidelines, [])
        )
    )

    assert len(connection_propositions) == 2
    assert connection_propositions[0].source == introduced_guidelines[0]
    assert connection_propositions[0].target == introduced_guidelines[1]
    assert connection_propositions[0].kind == ConnectionKind.ENTAILS
    assert connection_propositions[1].source == introduced_guidelines[1]
    assert connection_propositions[1].target == introduced_guidelines[2]
    assert connection_propositions[1].kind == ConnectionKind.ENTAILS


def test_that_connection_is_proposed_for_a_sequence_where_each_guideline_suggests_the_next_one(
    context: _TestContext,
    agent: Agent,
) -> None:
    introduced_guidelines: Sequence[GuidelineContent] = [
        GuidelineContent(predicate=i["predicate"], action=i["action"])
        for i in [
            {
                "predicate": "discussing sandwiches",
                "action": "recommend the daily specials",
            },
            {
                "predicate": "listing the daily specials",
                "action": "consider mentioning ingredients that may cause allergic reactions",
            },
            {
                "predicate": "discussing anything related to a food allergies",
                "action": "you may note that all dishes may contain peanut residues",
            },
        ]
    ]

    connection_proposer = context.container[GuidelineConnectionProposer]

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(agent, introduced_guidelines, [])
        )
    )

    assert len(connection_propositions) == 2
    assert connection_propositions[0].source == introduced_guidelines[0]
    assert connection_propositions[0].target == introduced_guidelines[1]
    assert connection_propositions[0].kind == ConnectionKind.SUGGESTS
    assert connection_propositions[1].source == introduced_guidelines[1]
    assert connection_propositions[1].target == introduced_guidelines[2]
    assert connection_propositions[1].kind == ConnectionKind.SUGGESTS


def test_that_circular_connection_is_proposed_for_three_guidelines_where_each_action_entails_the_following_predicate(
    context: _TestContext,
    agent: Agent,
) -> None:
    introduced_guidelines: Sequence[GuidelineContent] = [
        GuidelineContent(predicate=i["predicate"], action=i["action"])
        for i in [
            {
                "predicate": "referencing a guide to the user",
                "action": "explain how our guides directory works",
            },
            {
                "predicate": "mentioning our guide directory",
                "action": "check the operational guide",
            },
            {
                "predicate": "checking a guide",
                "action": "direct the user to the guide when replying",
            },
        ]
    ]

    connection_proposer = context.container[GuidelineConnectionProposer]

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(agent, introduced_guidelines, [])
        )
    )

    correct_propositions_set = {
        (introduced_guidelines[i], introduced_guidelines[(i + 1) % 3]) for i in range(3)
    }
    suggested_propositions_set = {(p.source, p.target) for p in connection_propositions}
    assert correct_propositions_set == suggested_propositions_set


@mark.parametrize(
    (
        "source_guideline_definition",
        "target_guideline_definition",
    ),
    [
        (
            {
                "predicate": "user is asking for specific instructions",
                "action": "consider redirecting the user to our video guides",
            },
            {
                "predicate": "mentioning a video",
                "action": "notify the user about supported video formats",
            },
        ),
        (
            {
                "guideline_set": "test-agent",
                "predicate": "the user asks for express shipping",
                "action": "check if express delivery is avialable and reply positively only if it is",  # Keeping the mispelling intentionally
            },
            {
                "guideline_set": "test-agent",
                "predicate": "offering express delivery",
                "action": "mention it takes up to 48 hours",
            },
        ),
    ],
)
def test_that_a_suggestive_guideline_which_entails_another_guideline_are_connected_as_suggestive(
    context: _TestContext,
    agent: Agent,
    source_guideline_definition: dict[str, str],
    target_guideline_definition: dict[str, str],
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        source_guideline_definition["predicate"],
        source_guideline_definition["action"],
    )

    target_guideline_content = _create_guideline_content(
        target_guideline_definition["predicate"],
        target_guideline_definition["action"],
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_content
    assert connection_propositions[0].target == target_guideline_content
    assert connection_propositions[0].kind == ConnectionKind.SUGGESTS


def test_that_no_connection_is_made_for_a_guidelines_whose_predicate_entails_another_guidelines_predicate(
    context: _TestContext,
    agent: Agent,
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        "the user refers to a past interaction",
        "ask for the date of this previous interaction",
    )

    target_guideline_content = _create_guideline_content(
        "the user refers to a quota offered in a past interaction",
        "answer that that quota is no longer relevant",
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )
    assert len(connection_propositions) == 0


def test_that_no_connection_is_made_for_a_guideline_which_implies_but_not_causes_another_guideline(
    context: _TestContext,
    agent: Agent,
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        "The user complains that the phrases in the photograph are blurry",
        "clarify what the unclear phrases mean",
    )

    target_guideline_content = _create_guideline_content(
        "a word is misunderstood",
        "reply with its dictionary definition",
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )
    assert len(connection_propositions) == 0


def test_that_guidelines_with_similar_thens_arent_connected(  # Tests both that entailing predicates and entailing actions aren't connected
    context: _TestContext,
    agent: Agent,
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        "the user refers to a past interaction",
        "ask the user for the date of this interaction",
    )

    target_guideline_content = _create_guideline_content(
        "the user asks about a solution suggested in a previous interaction",
        "ask when that conversation occurred",
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )
    assert len(connection_propositions) == 0


def test_that_identical_actions_arent_connected(  # Tests both that entailing predicates and entailing actions aren't connected
    context: _TestContext,
    agent: Agent,
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        "asked about pizza toppings",
        "list our pizza toppings",
    )

    target_guideline_content = _create_guideline_content(
        "asked about our menu",
        "list our pizza toppings",
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )
    assert len(connection_propositions) == 0


def test_that_misspelled_entailing_guidelines_are_connected(
    context: _TestContext,
    agent: Agent,
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]
    terminology_store = context.container[TerminologyStore]

    context.sync_await(
        terminology_store.create_term(
            term_set=agent.id,
            name="walnut",
            description="walnut is an altcoin",
        )
    )

    source_guideline_content = _create_guideline_content(
        "the user ask about wallnut prices",
        "provide the curent walnut prices",
    )

    target_guideline_content = _create_guideline_content(
        "provding altcoinn prices",
        "mention that between exchanges, there can be minor differences",
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )

    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_content
    assert connection_propositions[0].target == target_guideline_content
    assert connection_propositions[0].kind == ConnectionKind.ENTAILS


def test_that_try_actions_are_connected_but_not_suggestive(  # Tests both that entailing predicates and entailing actions aren't connected
    context: _TestContext,
    agent: Agent,
) -> None:
    connection_proposer = context.container[GuidelineConnectionProposer]

    source_guideline_content = _create_guideline_content(
        "the user complains that a suggested solution did not work",
        "reply in a hostile manner",
    )

    target_guideline_content = _create_guideline_content(
        "the conversational tone is hostile",
        "try to de-escalate the situation",
    )

    connection_propositions = list(
        context.sync_await(
            connection_proposer.propose_connections(
                agent,
                [source_guideline_content, target_guideline_content],
            )
        )
    )
    assert len(connection_propositions) == 1
    assert connection_propositions[0].source == source_guideline_content
    assert connection_propositions[0].target == target_guideline_content
    assert connection_propositions[0].kind == ConnectionKind.ENTAILS
