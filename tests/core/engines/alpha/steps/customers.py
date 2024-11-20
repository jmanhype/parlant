from pytest_bdd import given, parsers

from parlant.core.customers import CustomerStore, CustomerId
from parlant.core.sessions import SessionStore, SessionId
from parlant.core.tags import TagStore
from tests.core.engines.alpha.utils import ContextOfTest, step


@step(given, parsers.parse('an end customer with the name "{name}"'))
def given_an_customer(
    context: ContextOfTest,
    name: str,
) -> CustomerId:
    customer_store = context.container[CustomerStore]

    customer = context.sync_await(customer_store.create_customer(name))

    return customer.id


@step(given, parsers.parse('an customer tagged as "{tag_name}"'))
def given_a_customer_tag(
    context: ContextOfTest,
    session_id: SessionId,
    tag_name: str,
) -> None:
    session_store = context.container[SessionStore]
    customer_store = context.container[CustomerStore]
    tag_store = context.container[TagStore]

    tag = context.sync_await(tag_store.create_tag(tag_name))

    customer_id = context.sync_await(session_store.read_session(session_id)).customer_id

    context.sync_await(
        customer_store.add_tag(
            customer_id=customer_id,
            tag_id=tag.id,
        )
    )
