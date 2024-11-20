from pytest_bdd import given, parsers

from parlant.core.end_users import EndUserStore, EndUserId
from parlant.core.sessions import SessionStore, SessionId
from parlant.core.tags import TagStore
from tests.core.engines.alpha.utils import ContextOfTest, step


@step(given, parsers.parse('an end user with the name "{name}"'))
def given_an_end_user(
    context: ContextOfTest,
    name: str,
) -> EndUserId:
    end_user_store = context.container[EndUserStore]

    end_user = context.sync_await(end_user_store.create_end_user(name))

    return end_user.id


@step(given, parsers.parse('an end-user tagged as "{tag_name}"'))
def given_a_user_tag(
    context: ContextOfTest,
    session_id: SessionId,
    tag_name: str,
) -> None:
    session_store = context.container[SessionStore]
    end_user_store = context.container[EndUserStore]
    tag_store = context.container[TagStore]

    tag = context.sync_await(tag_store.create_tag(tag_name))

    end_user_id = context.sync_await(session_store.read_session(session_id)).end_user_id

    context.sync_await(
        end_user_store.add_tag(
            end_user_id=end_user_id,
            tag_id=tag.id,
        )
    )
