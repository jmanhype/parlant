import asyncio
from dataclasses import dataclass
from lagom import Container
from pytest import fixture

from parlant.server.core.async_utils import Timeout
from parlant.server.core.mc import MC
from parlant.server.core.agents import AgentId, AgentStore
from parlant.server.core.end_users import EndUserId, EndUserStore
from parlant.server.core.guidelines import GuidelineStore
from parlant.server.core.sessions import Session, SessionStore
from tests.test_utilities import nlp_test

REASONABLE_AMOUNT_OF_TIME = 10


@dataclass
class ContextOfTest:
    container: Container
    mc: MC
    end_user_id: EndUserId


@fixture
async def context(
    container: Container,
    end_user_id: EndUserId,
) -> ContextOfTest:
    return ContextOfTest(
        container=container,
        mc=container[MC],
        end_user_id=end_user_id,
    )


@fixture
async def agent_id(container: Container) -> AgentId:
    store = container[AgentStore]
    agent = await store.create_agent(name="test-agent")
    return agent.id


@fixture
async def proactive_agent_id(
    container: Container,
    agent_id: AgentId,
) -> AgentId:
    await container[GuidelineStore].create_guideline(
        guideline_set=agent_id,
        predicate="The user hasn't engaged yet",
        action="Greet the user",
    )

    return agent_id


@fixture
async def session(
    container: Container,
    end_user_id: EndUserId,
    agent_id: AgentId,
) -> Session:
    store = container[SessionStore]
    session = await store.create_session(
        end_user_id=end_user_id,
        agent_id=agent_id,
    )
    return session


@fixture
async def end_user_id(container: Container) -> EndUserId:
    store = container[EndUserStore]
    user = await store.create_end_user("Larry David", email="larry@seinfeld.com")
    return user.id


async def test_that_a_new_end_user_session_can_be_created(
    context: ContextOfTest,
    agent_id: AgentId,
) -> None:
    created_session = await context.mc.create_end_user_session(
        end_user_id=context.end_user_id,
        agent_id=agent_id,
    )

    session_in_db = await context.container[SessionStore].read_session(
        created_session.id,
    )

    assert created_session == session_in_db


async def test_that_a_new_user_session_with_a_proactive_agent_contains_a_message(
    context: ContextOfTest,
    proactive_agent_id: AgentId,
) -> None:
    session = await context.mc.create_end_user_session(
        end_user_id=context.end_user_id,
        agent_id=proactive_agent_id,
        allow_greeting=True,
    )

    assert await context.mc.wait_for_update(
        session_id=session.id,
        min_offset=0,
        kinds=["message"],
        timeout=Timeout(REASONABLE_AMOUNT_OF_TIME),
    )

    events = list(await context.container[SessionStore].list_events(session.id))

    assert len([e for e in events if e.kind == "message"]) == 1


async def test_that_when_a_client_event_is_posted_then_new_server_events_are_emitted(
    context: ContextOfTest,
    session: Session,
) -> None:
    event = await context.mc.post_event(
        session_id=session.id,
        kind="message",
        data={"message": "Hey there"},
    )

    await context.mc.wait_for_update(
        session_id=session.id,
        min_offset=1 + event.offset,
        kinds=[],
        timeout=Timeout(REASONABLE_AMOUNT_OF_TIME),
    )

    events = list(await context.container[SessionStore].list_events(session.id))

    assert len(events) > 1


async def test_that_a_session_update_is_detected_as_soon_as_a_client_event_is_posted(
    context: ContextOfTest,
    session: Session,
) -> None:
    event = await context.mc.post_event(
        session_id=session.id,
        kind="message",
        data={"message": "Hey there"},
    )

    assert await context.mc.wait_for_update(
        session_id=session.id,
        min_offset=event.offset,
        kinds=[],
        timeout=Timeout.none(),
    )


async def test_that_when_a_user_quickly_posts_more_than_one_message_then_only_one_message_is_emitted_as_a_reply_to_the_last_message(
    context: ContextOfTest,
    session: Session,
) -> None:
    messages = [
        "What are bananas?",
        "Scratch that; what are apples?",
        "Actually scratch that too. What are pineapples?",
    ]

    for m in messages:
        await context.mc.post_event(
            session_id=session.id,
            kind="message",
            data={"message": m},
        )

        await asyncio.sleep(1)

    await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    events = list(await context.container[SessionStore].list_events(session.id))
    message_events = [e for e in events if e.kind == "message"]

    assert len(message_events) == 4
    assert await nlp_test(str(message_events[-1].data), "It talks about pineapples")
